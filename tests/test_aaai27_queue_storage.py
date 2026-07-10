import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
for path in (REPO_ROOT / "scripts", REPO_ROOT / "tests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from aaai27_queue.models import TaskSpec
from aaai27_queue.storage import (
    append_event,
    atomic_create_json,
    atomic_write_json,
    load_exclusive_gate,
    load_json,
    require_within,
    sha256_file,
    validate_marker,
)
from aaai27_queue_testdata import make_task


def valid_marker(task: TaskSpec, artifact: str | None = None) -> dict:
    return {
        "schema_version": 1,
        "task_id": task.task_id,
        "ledger_id": task.ledger_id,
        "status": "pass",
        "created_at": "2026-07-10T22:50:00+08:00",
        "queue_manifest_sha256": "f" * 64,
        "code_revision": task.code_revision,
        "config_sha256": task.config_sha256,
        "split_sha256": task.split_sha256,
        "bank_sha256": task.bank_sha256,
        "exit_code": 0,
        "artifacts": [artifact or task.success_artifacts[0]],
        "validation": {"result": "pass", "checks": ["summary_exists"]},
    }


class QueueStorageTests(unittest.TestCase):
    def test_atomic_write_json_replaces_state_without_temporary_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state" / "controller.json"
            atomic_write_json(path, {"status": "one"})
            atomic_write_json(path, {"status": "two"})

            self.assertEqual({"status": "two"}, load_json(path))
            self.assertEqual([path], list(path.parent.iterdir()))

    def test_atomic_create_json_refuses_marker_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "markers" / "PASS.json"
            atomic_create_json(path, {"status": "pass"})

            with self.assertRaisesRegex(FileExistsError, "PASS.json"):
                atomic_create_json(path, {"status": "changed"})

            self.assertEqual({"status": "pass"}, load_json(path))

    def test_require_within_rejects_escape_and_accepts_child(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "queue"
            root.mkdir()
            self.assertEqual((root / "runs" / "x").resolve(), require_within(root / "runs" / "x", root))
            with self.assertRaisesRegex(ValueError, "outside allowed root"):
                require_within(root.parent / "frozen", root)

    def test_hash_and_jsonl_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "a.txt"
            source.write_bytes(b"abc")
            self.assertEqual(
                "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
                sha256_file(source),
            )
            events = root / "events.jsonl"
            append_event(events, {"event": "one"})
            append_event(events, {"event": "two"})
            self.assertEqual(
                [{"event": "one"}, {"event": "two"}],
                [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()],
            )

    def test_marker_validation_checks_identity_hashes_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            task = TaskSpec.from_dict(make_task())
            artifact = root / task.success_artifacts[0]
            artifact.parent.mkdir()
            artifact.write_text("{}\n", encoding="utf-8")
            marker = valid_marker(task)

            validate_marker(marker, task, "f" * 64, root)

            mutations = {
                "queue_manifest_sha256": "0" * 64,
                "task_id": "wrong",
                "config_sha256": "1" * 64,
                "split_sha256": "2" * 64,
                "exit_code": 1,
                "artifacts": ["artifacts/missing.json"],
                "validation": {"result": "fail", "checks": []},
            }
            for key, value in mutations.items():
                changed = dict(marker)
                changed[key] = value
                with self.subTest(key=key), self.assertRaises(ValueError):
                    validate_marker(changed, task, "f" * 64, root)

    def test_exclusive_gate_rejects_ambiguity(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            markers = root / "markers"
            markers.mkdir()
            (markers / "RISK-02_PASS.json").write_text("{}\n", encoding="utf-8")
            (markers / "RISK-02_FAIL.json").write_text("{}\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "ambiguous"):
                load_exclusive_gate(markers, "RISK-02_PASS.json", "RISK-02_FAIL.json")


if __name__ == "__main__":
    unittest.main()
