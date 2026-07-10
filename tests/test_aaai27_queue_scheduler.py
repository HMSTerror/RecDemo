import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
for path in (REPO_ROOT / "scripts", REPO_ROOT / "tests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from aaai27_queue.models import GateSnapshot, QueueManifest, TaskRecord
from aaai27_queue.scheduler import IntegrityError, choose_ready_tasks, group_status, select_active_branch
from aaai27_queue_testdata import make_manifest, make_task, valid_pilots


def record(task_id: str, status: str = "passed", attempt: int = 1, gpu_id: int | None = None) -> TaskRecord:
    return TaskRecord(
        task_id=task_id,
        status=status,
        attempt=attempt,
        pid=None,
        process_start_time=None,
        gpu_id=gpu_id,
        started_at="start",
        ended_at="end" if status != "running" else None,
        exit_code=0 if status == "passed" else None,
        gpu_seconds=0.0,
        reason=None,
    )


def manifest_with(*extra: dict) -> QueueManifest:
    return QueueManifest.from_dict(make_manifest([*valid_pilots(), *extra]))


def passed_pilot_records(manifest: QueueManifest) -> dict[str, TaskRecord]:
    return {
        task.task_id: record(task.task_id)
        for task in manifest.tasks
        if task.phase == "pilot"
    }


class QueueSchedulerTests(unittest.TestCase):
    def test_selects_only_approved_branches(self) -> None:
        self.assertEqual("common", select_active_branch(GateSnapshot(None, None)))
        self.assertEqual("e1_pass", select_active_branch(GateSnapshot("pass", None)))
        self.assertEqual("e1_fail_audit", select_active_branch(GateSnapshot("fail", None)))
        self.assertEqual("method_pass", select_active_branch(GateSnapshot("pass", "risk_gated_method")))
        self.assertEqual("terminal_stop", select_active_branch(GateSnapshot("pass", "audit_only")))
        self.assertEqual("terminal_stop", select_active_branch(GateSnapshot("fail", "submission_stop")))
        with self.assertRaisesRegex(IntegrityError, "E1 pass"):
            select_active_branch(GateSnapshot("fail", "risk_gated_method"))

    def test_dependencies_and_attempt_one_records_block_dispatch(self) -> None:
        dependency = make_task(task_id="common.lock", kind="cpu", gpu_slots=0, seed=None)
        candidate = make_task(
            task_id="method.run",
            ledger_id="RISK-13",
            phase="continuation",
            branch="method_pass",
            dependencies=["common.lock"],
        )
        manifest = manifest_with(dependency, candidate)
        records = passed_pilot_records(manifest)
        gates = GateSnapshot("pass", "risk_gated_method")

        self.assertNotIn("method.run", [task.task_id for task in choose_ready_tasks(manifest, records, gates, 0.0, 80.0, set())])
        records["common.lock"] = record("common.lock")
        self.assertIn("method.run", [task.task_id for task in choose_ready_tasks(manifest, records, gates, 0.0, 80.0, set())])
        records["method.run"] = record("method.run", status="failed")
        self.assertNotIn("method.run", [task.task_id for task in choose_ready_tasks(manifest, records, gates, 0.0, 80.0, set())])

    def test_budget_is_reserved_across_selected_wave(self) -> None:
        first = make_task(
            task_id="method.first",
            ledger_id="RISK-13",
            phase="continuation",
            branch="method_pass",
            priority=0,
            gpu_hours_high=6.0,
        )
        second = make_task(
            task_id="method.second",
            ledger_id="RISK-14",
            phase="continuation",
            branch="method_pass",
            priority=1,
            gpu_hours_high=5.0,
        )
        manifest = manifest_with(first, second)
        records = passed_pilot_records(manifest)

        ready = choose_ready_tasks(
            manifest,
            records,
            GateSnapshot("pass", "risk_gated_method"),
            actual_gpu_hours=158.0,
            free_disk_gib=80.0,
            busy_gpu_ids=set(),
        )

        self.assertEqual(["method.first"], [task.task_id for task in ready])

    def test_disk_terminal_and_busy_gpu_blocks_new_gpu_work(self) -> None:
        candidate = make_task(task_id="method.run", ledger_id="RISK-13", phase="continuation", branch="method_pass")
        manifest = manifest_with(candidate)
        records = passed_pilot_records(manifest)
        method = GateSnapshot("pass", "risk_gated_method")

        self.assertEqual([], choose_ready_tasks(manifest, records, method, 0.0, 39.9, set()))
        self.assertEqual([], choose_ready_tasks(manifest, records, GateSnapshot("pass", "audit_only"), 0.0, 80.0, set()))
        self.assertEqual([], choose_ready_tasks(manifest, records, method, 0.0, 80.0, {0, 1}))

    def test_group_status_requires_every_member_to_pass(self) -> None:
        tasks = tuple(
            QueueManifest.from_dict(
                make_manifest(
                    [
                        make_task(
                            task_id=f"sasrec.{dataset}",
                            ledger_id="RISK-10",
                            model="SASRec",
                            dataset=dataset,
                            atomic_group="sasrec.four-domain",
                        )
                        for dataset in ("Steam", "ML1M", "Beauty", "ATG")
                    ]
                )
            ).tasks
        )
        records = {task.task_id: record(task.task_id) for task in tasks}
        self.assertEqual("passed", group_status(records, tasks, "sasrec.four-domain"))
        records[tasks[-1].task_id] = record(tasks[-1].task_id, status="failed")
        self.assertEqual("incomplete", group_status(records, tasks, "sasrec.four-domain"))


if __name__ == "__main__":
    unittest.main()
