from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.aaai27_queue.models import QueueManifest, TaskRecord
from scripts.aaai27_queue.storage import sha256_file
from scripts.aaai27_r7_resident_queue import (
    R7ControllerError,
    build_finalizer_config,
    maybe_finalize_r7,
    validate_finalizer_config,
)
from tests.aaai27_queue_testdata import make_manifest, valid_pilots


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "aaai27_r7_resident_queue.py"


def record(task_id: str, status: str, *, gpu_id: int | None = None) -> TaskRecord:
    return TaskRecord(
        task_id=task_id,
        status=status,
        attempt=1,
        pid=None,
        process_start_time=None,
        gpu_id=gpu_id,
        started_at="2026-07-12T08:00:00+00:00",
        ended_at=("2026-07-12T09:00:00+00:00" if status != "running" else None),
        exit_code=(0 if status == "passed" else 1 if status == "failed" else None),
        gpu_seconds=10.0,
        reason=("fixture failure" if status == "failed" else None),
    )


class R7ResidentControllerTests(unittest.TestCase):
    def _manifest(self, root: Path) -> tuple[QueueManifest, Path]:
        raw = make_manifest(
            valid_pilots(),
            run_root=root.as_posix(),
            source_root="/srv/source-r7",
            gpu_ids=[0, 1],
        )
        manifest = QueueManifest.from_dict(raw)
        path = root / "queue" / "queue_seed100.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(raw), encoding="utf-8")
        return manifest, path

    def _active_records(
        self, manifest: QueueManifest, *, status: str = "passed"
    ) -> dict[str, TaskRecord]:
        return {
            task.task_id: record(task.task_id, status)
            for task in manifest.tasks
            if task.phase == "pilot" and task.branch == "e1_pass"
        }

    def test_cli_exposes_prepare_validate_and_run_without_generic_shell_wrapper(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("prepare-finalizer", completed.stdout)
        self.assertIn("validate-finalizer", completed.stdout)
        self.assertIn("run", completed.stdout)

    def test_fourteen_passed_tasks_finalize_once_and_write_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, _ = self._manifest(root)
            calls: list[str] = []

            def finalizer() -> dict[str, object]:
                calls.append("called")
                return {
                    "exit": "risk_gated_method",
                    "pilot_report_sha256": "a" * 64,
                    "artifact_sha256": "b" * 64,
                }

            terminal = maybe_finalize_r7(
                root,
                manifest,
                self._active_records(manifest),
                stop_requested=False,
                finalizer=finalizer,
            )
            self.assertEqual("risk_gated_method", terminal["risk08_exit"])
            self.assertEqual(["called"], calls)
            terminal_path = root / "state" / "TERMINAL.json"
            self.assertTrue(terminal_path.is_file())

            repeated = maybe_finalize_r7(
                root,
                manifest,
                self._active_records(manifest),
                stop_requested=False,
                finalizer=finalizer,
            )
            self.assertEqual(terminal, repeated)
            self.assertEqual(["called"], calls)

    def test_partial_completion_waits_and_task_failure_is_terminal_without_rescue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, _ = self._manifest(root)
            records = self._active_records(manifest)
            records.pop(next(iter(records)))
            self.assertIsNone(
                maybe_finalize_r7(
                    root,
                    manifest,
                    records,
                    stop_requested=False,
                    finalizer=lambda: self.fail("partial queue must not finalize"),
                )
            )
            failed_id = next(iter(records))
            records[failed_id] = record(failed_id, "failed")
            terminal = maybe_finalize_r7(
                root,
                manifest,
                records,
                stop_requested=False,
                finalizer=lambda: self.fail("failed queue must not finalize"),
            )
            self.assertEqual("task_failure", terminal["outcome"])
            self.assertTrue(terminal["no_rescue"])
            self.assertIn(failed_id, terminal["failed_task_ids"])

    def test_stop_waits_for_running_child_then_writes_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, _ = self._manifest(root)
            task_id = next(
                task.task_id for task in manifest.tasks if task.branch == "e1_pass"
            )
            running = {task_id: record(task_id, "running", gpu_id=0)}
            self.assertIsNone(
                maybe_finalize_r7(
                    root,
                    manifest,
                    running,
                    stop_requested=True,
                    finalizer=lambda: self.fail("running stop must not finalize"),
                )
            )
            stopped = maybe_finalize_r7(
                root,
                manifest,
                {},
                stop_requested=True,
                finalizer=lambda: self.fail("requested stop must not finalize"),
            )
            self.assertEqual("stop_requested", stopped["outcome"])

    def test_inactive_branch_record_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, _ = self._manifest(root)
            inactive = next(task for task in manifest.tasks if task.branch == "e1_fail_audit")
            with self.assertRaisesRegex(R7ControllerError, "inactive"):
                maybe_finalize_r7(
                    root,
                    manifest,
                    {inactive.task_id: record(inactive.task_id, "passed")},
                    stop_requested=False,
                    finalizer=lambda: {},
                )

    def test_finalizer_config_binds_queue_risk05_preflight_and_source_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, manifest_path = self._manifest(root)
            markers = root / "markers"
            markers.mkdir()
            (markers / "RISK-02_PASS.json").write_text("{}\n", encoding="utf-8")
            risk05 = root / "external" / "risk05"
            (risk05 / "protocol").mkdir(parents=True)
            (risk05 / "risk05_bundle.json").write_text("{}\n", encoding="utf-8")
            (risk05 / "protocol" / "risk05_preregistration.json").write_text(
                "{}\n", encoding="utf-8"
            )
            preflight = root / "external" / "risk_preflight_report.json"
            preflight.write_text("{}\n", encoding="utf-8")

            config = build_finalizer_config(
                root,
                manifest_path=manifest_path,
                risk05_root=risk05,
                risk_preflight_path=preflight,
            )
            self.assertEqual(sha256_file(manifest_path), config["queue_manifest_sha256"])
            self.assertEqual("a" * 40, config["source_revision"])
            self.assertEqual(14, config["active_task_count"])
            self.assertTrue(config["no_rescue"])
            checked = validate_finalizer_config(
                root,
                manifest_path=manifest_path,
            )
            self.assertEqual(config, checked)

            preflight.write_text("tampered\n", encoding="utf-8")
            with self.assertRaisesRegex(R7ControllerError, "preflight.*hash"):
                validate_finalizer_config(root, manifest_path=manifest_path)


if __name__ == "__main__":
    unittest.main()
