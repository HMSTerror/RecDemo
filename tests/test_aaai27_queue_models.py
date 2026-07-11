import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
for path in (REPO_ROOT / "scripts", REPO_ROOT / "tests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from aaai27_queue.models import QueueManifest, TaskSpec
from aaai27_queue_testdata import make_manifest, make_task


class QueueModelTests(unittest.TestCase):
    def test_task_round_trip_preserves_argv_and_hashes(self) -> None:
        raw = make_task(
            task_id="RISK-02.trace.seed100",
            ledger_id="RISK-02",
            dependencies=["RISK-01.lock"],
            required_markers=["RISK-01_PASS.json"],
        )

        task = TaskSpec.from_dict(raw)

        self.assertEqual(tuple(raw["argv"]), task.argv)
        self.assertEqual(raw, task.to_dict())

    def test_queue_round_trip_preserves_task_types(self) -> None:
        raw = make_manifest([make_task()])

        manifest = QueueManifest.from_dict(raw)

        self.assertIsInstance(manifest.tasks[0], TaskSpec)
        self.assertEqual((1,), manifest.gpu_ids)
        self.assertEqual(raw, manifest.to_dict())

    def test_task_rejects_unknown_and_missing_fields(self) -> None:
        unknown = make_task(extra=True)
        missing = make_task()
        missing.pop("task_id")

        with self.assertRaisesRegex(ValueError, "unknown task fields"):
            TaskSpec.from_dict(unknown)
        with self.assertRaisesRegex(ValueError, "missing task fields"):
            TaskSpec.from_dict(missing)

    def test_queue_rejects_unknown_and_missing_fields(self) -> None:
        unknown = make_manifest([make_task()], extra=True)
        missing = make_manifest([make_task()])
        missing.pop("queue_id")

        with self.assertRaisesRegex(ValueError, "unknown queue fields"):
            QueueManifest.from_dict(unknown)
        with self.assertRaisesRegex(ValueError, "missing queue fields"):
            QueueManifest.from_dict(missing)


if __name__ == "__main__":
    unittest.main()
