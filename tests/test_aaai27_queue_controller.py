import json
import sys
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
for path in (REPO_ROOT / "scripts", REPO_ROOT / "tests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from aaai27_queue.controller import QueueController
from aaai27_queue.models import QueueManifest, TaskRecord
from aaai27_queue.runtime import FinishedChild, StartedChild
from aaai27_queue.scheduler import IntegrityError
from aaai27_queue_testdata import make_manifest, make_task


def record(task_id: str, **overrides) -> TaskRecord:
    values = {
        "task_id": task_id,
        "status": "running",
        "attempt": 1,
        "pid": 123,
        "process_start_time": "stamp",
        "gpu_id": 0,
        "started_at": "start",
        "ended_at": None,
        "exit_code": None,
        "gpu_seconds": 0.0,
        "reason": None,
    }
    values.update(overrides)
    return TaskRecord(**values)


class FakeRuntime:
    def __init__(self, *, finished=None, start_result=None) -> None:
        self.finished = list(finished or [])
        self.start_result = start_result
        self.started = []

    def observe_finished(self):
        result, self.finished = self.finished, []
        return result

    def start_task(self, task, allowed_gpu_ids):
        self.started.append((task.task_id, tuple(allowed_gpu_ids)))
        return self.start_result


class QueueControllerTests(unittest.TestCase):
    def make_controller(self, root: Path, tasks, **kwargs) -> QueueController:
        manifest = QueueManifest.from_dict(make_manifest(tasks, run_root=str(root)))
        return QueueController.for_test(root, manifest, **kwargs)

    def test_orphaned_record_becomes_interrupted_without_retry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            controller = self.make_controller(root, [make_task(task_id="front.one")])
            controller.save_record(record("front.one"))

            controller.reconcile()

            revised = controller.load_records()["front.one"]
            self.assertEqual("interrupted_unverified", revised.status)
            self.assertEqual(1, revised.attempt)
            self.assertEqual([], controller.ready_tasks())

    def test_live_record_survives_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            controller = self.make_controller(
                root,
                [make_task(task_id="front.live")],
                live_process=lambda pid, started: pid == 321 and started == "token",
            )
            controller.save_record(record("front.live", pid=321, process_start_time="token"))
            controller.reconcile()
            self.assertEqual("running", controller.load_records()["front.live"].status)

    def test_unverified_recovery_fails_closed_without_liveness_probe(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            live_process = mock.Mock(side_effect=AssertionError("unverified token must not be probed"))
            controller = self.make_controller(
                root,
                [make_task(task_id="front.unverified")],
                live_process=live_process,
            )
            controller.save_record(
                record("front.unverified", pid=151, process_start_time="unverified:151")
            )

            controller.reconcile()

            revised = controller.load_records()["front.unverified"]
            self.assertEqual("interrupted_unverified", revised.status)
            self.assertEqual(1, revised.attempt)
            live_process.assert_not_called()

    def test_stop_file_prevents_new_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            controller = self.make_controller(root, [make_task(task_id="front.one")])
            (root / "state").mkdir(parents=True)
            (root / "state" / "STOP_AFTER_CURRENT").write_text("requested\n", encoding="utf-8")
            runtime = FakeRuntime(start_result=StartedChild("front.one", 1, "token", 0))

            controller.tick(runtime)

            self.assertEqual([], runtime.started)
            self.assertEqual({}, controller.load_records())

    def test_stop_file_allows_current_completion_without_new_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            controller = self.make_controller(root, [make_task(task_id="front.current")])
            controller.save_record(record("front.current"))
            (root / "state" / "STOP_AFTER_CURRENT").write_text("requested\n", encoding="utf-8")
            runtime = FakeRuntime(finished=[FinishedChild("front.current", 0, 4.0, True, None)])

            controller.tick(runtime)

            saved = controller.load_records()["front.current"]
            self.assertEqual("passed", saved.status)
            self.assertEqual([], runtime.started)

    def test_tick_persists_running_record_and_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            controller = self.make_controller(root, [make_task(task_id="front.one")])
            runtime = FakeRuntime(start_result=StartedChild("front.one", 456, "token-456", 1))

            controller.tick(runtime)

            saved = controller.load_records()["front.one"]
            self.assertEqual(("front.one", (0, 1)), runtime.started[0])
            self.assertEqual("running", saved.status)
            self.assertEqual(1, saved.attempt)
            self.assertEqual(456, saved.pid)
            self.assertEqual(1, saved.gpu_id)
            events = [json.loads(line) for line in (root / "logs" / "events.jsonl").read_text().splitlines()]
            self.assertEqual("running", events[-1]["to"])

    def test_runtime_task_identity_mismatch_is_rejected_before_persisting_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            controller = self.make_controller(root, [make_task(task_id="front.expected")])
            runtime = FakeRuntime(start_result=StartedChild("front.other", 457, "token-457", 0))

            with self.assertRaisesRegex(RuntimeError, "unexpected task"):
                controller.tick(runtime)

            self.assertEqual({}, controller.load_records())
            events_path = root / "logs" / "events.jsonl"
            self.assertFalse(events_path.exists())

    def test_unverified_child_stays_supervised_until_runtime_observes_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            live_process = mock.Mock(side_effect=AssertionError("supervised child must not be probed"))
            controller = self.make_controller(
                root,
                [make_task(task_id="front.unverified")],
                live_process=live_process,
            )
            runtime = FakeRuntime(
                start_result=StartedChild("front.unverified", 151, "unverified:151", 0)
            )

            controller.tick(runtime)
            controller.tick(runtime)

            saved = controller.load_records()["front.unverified"]
            self.assertEqual("running", saved.status)
            self.assertEqual(1, saved.attempt)
            self.assertEqual([("front.unverified", (0, 1))], runtime.started)
            live_process.assert_not_called()

    def test_valid_completion_passes_and_accounts_gpu_time(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            controller = self.make_controller(root, [make_task(task_id="front.done")])
            controller.save_record(record("front.done"))
            runtime = FakeRuntime(
                finished=[FinishedChild("front.done", 0, 37.5, True, None)],
                start_result=None,
            )

            controller.tick(runtime)

            saved = controller.load_records()["front.done"]
            self.assertEqual("passed", saved.status)
            self.assertEqual(37.5, saved.gpu_seconds)
            self.assertEqual(0, saved.exit_code)

    def test_tick_observes_supervised_completion_before_orphan_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            live_process = mock.Mock(side_effect=AssertionError("completed child was probed as orphan"))
            controller = self.make_controller(
                root,
                [make_task(task_id="front.finished")],
                live_process=live_process,
            )
            controller.save_record(record("front.finished", pid=808, process_start_time="token-808"))
            runtime = FakeRuntime(finished=[FinishedChild("front.finished", 0, 3.0, True, None)])

            controller.tick(runtime)

            saved = controller.load_records()["front.finished"]
            self.assertEqual("passed", saved.status)
            live_process.assert_not_called()
            events = [json.loads(line) for line in (root / "logs" / "events.jsonl").read_text().splitlines()]
            self.assertEqual(["passed"], [event["to"] for event in events])

    def test_process_or_artifact_failure_blocks_dependent(self) -> None:
        for finished in (
            FinishedChild("front.one", 7, 2.0, False, "exit_code=7"),
            FinishedChild("front.one", 0, 2.0, False, "missing_artifacts=done.json"),
        ):
            with self.subTest(reason=finished.reason), tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                first = make_task(task_id="front.one")
                second = make_task(task_id="front.two", dependencies=["front.one"])
                controller = self.make_controller(root, [first, second])
                controller.save_record(record("front.one"))

                controller.tick(FakeRuntime(finished=[finished]))

                saved = controller.load_records()["front.one"]
                self.assertEqual("failed", saved.status)
                self.assertEqual(finished.reason, saved.reason)
                self.assertEqual([], controller.ready_tasks())

    def test_ambiguous_or_impossible_gates_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            controller = self.make_controller(root, [make_task(task_id="front.one")])
            markers = root / "markers"
            markers.mkdir()
            (markers / "RISK-02_PASS.json").write_text("{}", encoding="utf-8")
            (markers / "RISK-02_FAIL.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "ambiguous"):
                controller.load_gates()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            controller = self.make_controller(root, [make_task(task_id="front.one")])
            markers = root / "markers"
            markers.mkdir()
            (markers / "RISK-02_FAIL.json").write_text("{}", encoding="utf-8")
            (markers / "RISK-08_EXIT.json").write_text('{"exit":"risk_gated_method"}', encoding="utf-8")
            with self.assertRaises(IntegrityError):
                controller.ready_tasks()

    def test_record_path_cannot_escape_queue_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            controller = self.make_controller(root, [make_task(task_id="front.one")])
            with self.assertRaisesRegex(ValueError, "unknown task"):
                controller.save_record(replace(record("front.one"), task_id="../../escape"))
            self.assertFalse((root.parent / "escape.json").exists())

    def test_known_task_id_with_traversal_is_encoded_inside_queue_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            root = temp_root / "nested" / "queue"
            root.mkdir(parents=True)
            task_id = "../../../escape"
            controller = self.make_controller(root, [make_task(task_id=task_id)])

            controller.save_record(record(task_id))

            self.assertEqual("running", controller.load_records()[task_id].status)
            self.assertFalse((root.parent / "escape.json").exists())
            record_files = list((root / "state" / "tasks").glob("*.json"))
            self.assertEqual(1, len(record_files))
            self.assertIn(root.resolve(), record_files[0].resolve().parents)

    def test_unknown_persisted_task_record_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            controller = self.make_controller(root, [make_task(task_id="front.one")])
            records_dir = root / "state" / "tasks"
            records_dir.mkdir(parents=True)
            (records_dir / "unknown.json").write_text(
                json.dumps(asdict(record("front.unknown"))),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "unknown task"):
                controller.load_records()


if __name__ == "__main__":
    unittest.main()
