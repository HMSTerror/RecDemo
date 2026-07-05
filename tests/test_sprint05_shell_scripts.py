import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class Sprint05ShellScriptsTests(unittest.TestCase):
    def test_orchestrator_contains_frozen_launch_flags_and_helper_snapshot(self) -> None:
        text = (REPO_ROOT / "scripts" / "sprint05_official_orchestrator.sh").read_text(encoding="utf-8")
        self.assertIn("FORCE=1", text)
        self.assertIn("SKIP_EXISTING=0", text)
        self.assertIn("REQUIRE_SUMMARY=1", text)
        self.assertIn("TEXT_KERNEL_VERSION=v2", text)
        self.assertIn("TEXT_G_MAX=0.5", text)
        self.assertIn("TEXT_AGREEMENT_K=2.0", text)
        self.assertIn("capture_text_side_main_table_snapshot.py", text)

    def test_watchdog_uses_snapshot_helper_in_official_mode(self) -> None:
        text = (REPO_ROOT / "scripts" / "sprint05_watchdog.sh").read_text(encoding="utf-8")
        self.assertIn("capture_text_side_main_table_snapshot.py", text)
        self.assertIn("--official-mode", text)
        self.assertIn("--official-repo-root", text)
        self.assertIn("captured wave1_started snapshot", text)
        self.assertIn("captured final snapshot", text)


if __name__ == "__main__":
    unittest.main()
