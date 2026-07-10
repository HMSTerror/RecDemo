import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ENTRY = REPO_ROOT / "scripts" / "aaai27_resident_queue.py"

for path in (REPO_ROOT / "scripts", REPO_ROOT / "tests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from aaai27_queue_testdata import valid_pilots, make_manifest


def write_manifest(path: Path, *, run_root: str = "/srv/queue") -> None:
    path.write_text(
        json.dumps(make_manifest(valid_pilots(), run_root=run_root), indent=2),
        encoding="utf-8",
    )


class QueueCliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ENTRY), *args],
            capture_output=True,
            text=True,
        )

    def test_status_is_read_only_when_state_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "queue"
            result = self.run_cli("status", "--queue-root", str(root), "--json")

            self.assertEqual(2, result.returncode)
            self.assertFalse(root.exists())
            self.assertEqual("absent", json.loads(result.stdout)["status"])

    def test_request_stop_creates_only_stop_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "queue"
            root.mkdir()

            result = self.run_cli("request-stop", "--queue-root", str(root))

            self.assertEqual(0, result.returncode)
            self.assertTrue((root / "state" / "STOP_AFTER_CURRENT").is_file())
            self.assertEqual(["STOP_AFTER_CURRENT"], [path.name for path in (root / "state").iterdir()])

    def test_smoke_writes_marker_without_training(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "smoke"

            result = self.run_cli("smoke", "--queue-root", str(root))

            self.assertEqual(0, result.returncode)
            marker = json.loads((root / "markers" / "SMOKE_PASS.json").read_text(encoding="utf-8"))
            self.assertEqual("pass", marker["status"])
            self.assertFalse(marker["training_started"])
            self.assertFalse((root / "runs").exists())
            self.assertFalse(list(root.rglob("*.pth")))

    def test_smoke_rejects_nonempty_root_without_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "smoke"
            root.mkdir()
            sentinel = root / "sentinel.txt"
            sentinel.write_text("keep\n", encoding="utf-8")

            result = self.run_cli("smoke", "--queue-root", str(root))

            self.assertNotEqual(0, result.returncode)
            self.assertEqual("keep\n", sentinel.read_text(encoding="utf-8"))
            self.assertFalse((root / "markers").exists())

    def test_status_smoke_and_stop_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "smoke"
            smoke = self.run_cli("smoke", "--queue-root", str(root))
            self.assertEqual(0, smoke.returncode)

            first_status = self.run_cli("status", "--queue-root", str(root), "--json")
            self.assertEqual(0, first_status.returncode)
            first_payload = json.loads(first_status.stdout)
            self.assertEqual("smoke_pass", first_payload["status"])
            self.assertFalse(first_payload["stop_requested"])

            stop = self.run_cli("request-stop", "--queue-root", str(root))
            self.assertEqual(0, stop.returncode)
            second_status = self.run_cli("status", "--queue-root", str(root), "--json")
            self.assertEqual(0, second_status.returncode)
            second_payload = json.loads(second_status.stdout)
            self.assertTrue(second_payload["stop_requested"])
            self.assertFalse((root / "runs").exists())
            self.assertFalse(list(root.rglob("*.pth")))

    def test_status_reports_manifest_hash_branch_and_task_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "queue"
            manifest_path = root / "queue" / "queue_seed100.json"
            manifest_path.parent.mkdir(parents=True)
            write_manifest(manifest_path)

            result = self.run_cli("status", "--queue-root", str(root), "--json")

            self.assertEqual(0, result.returncode)
            payload = json.loads(result.stdout)
            self.assertEqual("present", payload["status"])
            self.assertTrue(payload["manifest_present"])
            self.assertEqual(22, payload["task_count"])
            self.assertEqual("common", payload["branch"])
            self.assertEqual(22, payload["task_counts"]["pending"])
            self.assertEqual(0, payload["task_counts"]["running"])
            self.assertEqual(64, len(payload["manifest_sha256"]))

    def test_validate_is_read_only_and_reports_manifest_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "queue"
            manifest = Path(tmpdir) / "manifest.json"
            write_manifest(manifest)

            result = self.run_cli(
                "validate",
                "--queue-root",
                str(root),
                "--manifest",
                str(manifest),
                "--json",
            )

            self.assertEqual(0, result.returncode)
            payload = json.loads(result.stdout)
            self.assertEqual("valid", payload["status"])
            self.assertEqual(22, payload["task_count"])
            self.assertFalse(root.exists())

    def test_dry_run_reports_frozen_pass_and_audit_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "queue"
            manifest = Path(tmpdir) / "manifest.json"
            write_manifest(manifest)

            pass_run = self.run_cli(
                "dry-run",
                "--queue-root",
                str(root),
                "--manifest",
                str(manifest),
                "--e1-outcome",
                "pass",
                "--risk08-exit",
                "pending",
            )
            fail_run = self.run_cli(
                "dry-run",
                "--queue-root",
                str(root),
                "--manifest",
                str(manifest),
                "--e1-outcome",
                "fail",
                "--risk08-exit",
                "audit_only",
            )

            self.assertEqual(0, pass_run.returncode)
            self.assertEqual(0, fail_run.returncode)
            self.assertEqual(14, json.loads(pass_run.stdout)["selected_count"])
            fail_payload = json.loads(fail_run.stdout)
            self.assertEqual("terminal_stop", fail_payload["branch"])
            self.assertEqual(0, fail_payload["selected_count"])
            self.assertFalse(root.exists())

    def test_dry_run_rejects_method_pass_without_e1_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = Path(tmpdir) / "manifest.json"
            write_manifest(manifest)
            result = self.run_cli(
                "dry-run",
                "--queue-root",
                str(Path(tmpdir) / "queue"),
                "--manifest",
                str(manifest),
                "--e1-outcome",
                "fail",
                "--risk08-exit",
                "risk_gated_method",
            )

            self.assertNotEqual(0, result.returncode)
            self.assertIn("error", json.loads(result.stdout))


if __name__ == "__main__":
    unittest.main()
