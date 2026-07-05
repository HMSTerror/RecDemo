import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script_module():
    script_path = REPO_ROOT / "scripts" / "launch_sprint05_official_tmux.py"
    spec = importlib.util.spec_from_file_location("launch_sprint05_official_tmux", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class LaunchSprint05OfficialTmuxTests(unittest.TestCase):
    def test_build_remote_command_targets_repo_scripts_and_sessions(self) -> None:
        module = load_script_module()
        command = module.build_remote_command(
            remote_base=Path("/data/Zijian/goal/RecDemo_clean_main"),
            old_root=Path("/data/Zijian/goal/RecDemo"),
            run_root=Path("/data/Zijian/goal/RecDemoRuns/main_table_text_side"),
            python_bin=Path("/data/Zijian/goal/PreferGrow/.venv/bin/python"),
            report_dir=Path("/data/Zijian/goal/RecDemo_clean_main/docs/reports/data/2026-07-05-sprint05"),
            snapshot_root=Path("/data/Zijian/goal/RecDemo_clean_main/docs/reports/data/2026-07-05-sprint05-watchdog"),
            orchestrator_session="sprint05_official_orchestrator",
            watchdog_session="sprint05_watchdog",
            log_path=Path("/data/Zijian/goal/RecDemoRuns/main_table_text_side/sprint05_watchdog.log"),
        )

        self.assertIn("scripts/sprint05_official_orchestrator.sh", command)
        self.assertIn("scripts/sprint05_watchdog.sh", command)
        self.assertIn("tmux new-session -d -s sprint05_official_orchestrator", command)
        self.assertIn("tmux new-session -d -s sprint05_watchdog", command)
        self.assertIn("REPORT_DIR=/data/Zijian/goal/RecDemo_clean_main/docs/reports/data/2026-07-05-sprint05", command)
        self.assertIn("SNAPSHOT_ROOT=/data/Zijian/goal/RecDemo_clean_main/docs/reports/data/2026-07-05-sprint05-watchdog", command)

    def test_build_ssh_argv_avoids_windows_shell_quoting(self) -> None:
        module = load_script_module()
        argv = module.build_ssh_argv(host="l20", remote_command="cd /data/Zijian/goal/RecDemo_clean_main")
        self.assertEqual("ssh", argv[0])
        self.assertEqual("l20", argv[1])
        self.assertEqual("cd /data/Zijian/goal/RecDemo_clean_main", argv[2])

    def test_launch_remote_sprint05_print_only_excludes_host_from_remote_builder(self) -> None:
        module = load_script_module()
        command = module.launch_remote_sprint05(
            host="l20",
            remote_base=Path("/data/Zijian/goal/RecDemo_clean_main"),
            old_root=Path("/data/Zijian/goal/RecDemo"),
            run_root=Path("/data/Zijian/goal/RecDemoRuns/main_table_text_side"),
            python_bin=Path("/data/Zijian/goal/PreferGrow/.venv/bin/python"),
            report_dir=Path("/data/Zijian/goal/RecDemo_clean_main/docs/reports/data/2026-07-05-sprint05"),
            snapshot_root=Path("/data/Zijian/goal/RecDemo_clean_main/docs/reports/data/2026-07-05-sprint05-watchdog"),
            orchestrator_session="sprint05_official_orchestrator",
            watchdog_session="sprint05_watchdog",
            log_path=Path("/data/Zijian/goal/RecDemoRuns/main_table_text_side/sprint05_watchdog.log"),
            print_only=True,
        )

        self.assertTrue(command.startswith("ssh l20 "))
        self.assertIn("scripts/sprint05_official_orchestrator.sh", command)
        self.assertIn("scripts/sprint05_watchdog.sh", command)


if __name__ == "__main__":
    unittest.main()
