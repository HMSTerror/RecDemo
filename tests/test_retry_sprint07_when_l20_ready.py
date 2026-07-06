import importlib.util
import types
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script_module():
    script_path = REPO_ROOT / "scripts" / "retry_sprint07_when_l20_ready.py"
    spec = importlib.util.spec_from_file_location("retry_sprint07_when_l20_ready", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RetrySprint07WhenL20ReadyTests(unittest.TestCase):
    def test_build_status_command_uses_shell_free_ssh_with_timeout(self) -> None:
        module = load_script_module()
        command = module.build_status_command(
            host="l20",
            remote_base="/data/Zijian/goal/RecDemo_clean_main",
            remote_python="/data/Zijian/goal/PreferGrow/.venv/bin/python",
            report_dir="/data/Zijian/goal/RecDemo_clean_main/docs/reports/data/2026-07-06-sprint07",
            connect_timeout=9,
        )

        self.assertEqual(["ssh", "-n", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=9", "l20"], command[:8])
        self.assertIn("build_sprint07_control_report.py", command[8])
        self.assertIn("sprint07_control_table.csv", command[8])

    def test_build_close02_launch_command_uses_local_python_and_seed_list(self) -> None:
        module = load_script_module()
        command = module.build_close02_launch_command(
            local_python=Path("E:/anaco/python.exe"),
            close02_seeds=(100, 101, 102),
        )

        self.assertEqual(Path("E:/anaco/python.exe"), Path(command[0]))
        self.assertIn("launch_close02_ml1m_noise_floor_tmux.py", command[1])
        self.assertEqual(["--seeds", "100", "101", "102"], command[2:])

    def test_build_close02_status_command_uses_shell_free_ssh_with_timeout_and_seeds(self) -> None:
        module = load_script_module()
        command = module.build_close02_status_command(
            host="l20",
            remote_base="/data/Zijian/goal/RecDemo_clean_main",
            remote_python="/data/Zijian/goal/PreferGrow/.venv/bin/python",
            close02_run_root="/data/Zijian/goal/RecDemoRuns/close02_ml1m_noise_floor",
            close02_report_dir="/data/Zijian/goal/RecDemo_clean_main/docs/reports/data/2026-07-06-close02-ml1m-noise-floor",
            close02_seeds=(100, 101, 102),
            connect_timeout=9,
        )

        self.assertEqual(["ssh", "-n", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=9", "l20"], command[:8])
        self.assertIn("build_close02_ml1m_noise_floor_report.py", command[8])
        self.assertIn("--run-root", command[8])
        self.assertIn("--seeds 100 101 102", command[8])
        self.assertIn("close02_ml1m_noise_floor_table.csv", command[8])

    def test_build_report_sync_commands_pull_expected_files(self) -> None:
        module = load_script_module()
        commands = module.build_report_sync_commands(
            host="l20",
            report_dir="/data/Zijian/goal/RecDemo_clean_main/docs/reports/data/2026-07-06-sprint07",
            local_report_dir=Path("E:/PreferGrow/docs/reports/data/2026-07-06-sprint07"),
            connect_timeout=8,
        )

        self.assertEqual(2, len(commands))
        self.assertEqual(["scp", "-B", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8"], commands[0][:6])
        self.assertIn("sprint07_control_table.csv", commands[0][6])
        self.assertTrue(commands[0][7].endswith("sprint07_control_table.csv"))
        self.assertIn("sprint07_control_report_zh.md", commands[1][6])
        self.assertTrue(commands[1][7].endswith("sprint07_control_report_zh.md"))

    def test_build_close02_report_sync_commands_pull_expected_files(self) -> None:
        module = load_script_module()
        commands = module.build_close02_report_sync_commands(
            host="l20",
            report_dir="/data/Zijian/goal/RecDemo_clean_main/docs/reports/data/2026-07-06-close02-ml1m-noise-floor",
            local_report_dir=Path("E:/PreferGrow/docs/reports/data/2026-07-06-close02-ml1m-noise-floor"),
            connect_timeout=8,
        )

        self.assertEqual(3, len(commands))
        self.assertEqual(["scp", "-B", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8"], commands[0][:6])
        self.assertIn("close02_ml1m_noise_floor_table.csv", commands[0][6])
        self.assertTrue(commands[0][7].endswith("close02_ml1m_noise_floor_table.csv"))
        self.assertIn("close02_ml1m_noise_floor_report.json", commands[1][6])
        self.assertTrue(commands[1][7].endswith("close02_ml1m_noise_floor_report.json"))
        self.assertIn("close02_ml1m_noise_floor_report_zh.md", commands[2][6])
        self.assertTrue(commands[2][7].endswith("close02_ml1m_noise_floor_report_zh.md"))

    def test_completion_state_requires_all_rows_completed(self) -> None:
        module = load_script_module()
        rows = []
        for dataset in module.TARGET_DATASETS:
            for arm in module.TARGET_ARMS:
                rows.append({"dataset": dataset, "arm": arm, "status": "completed", "last_logged_step": "10"})
        complete, incomplete = module.completion_state(rows)
        self.assertTrue(complete)
        self.assertEqual([], incomplete)

        rows[-1]["status"] = "running"
        complete, incomplete = module.completion_state(rows)
        self.assertFalse(complete)
        self.assertEqual("global_p", incomplete[0]["arm"])

    def test_close02_completion_state_requires_all_expected_seeds_completed(self) -> None:
        module = load_script_module()
        rows = [
            {"seed": "100", "status": "completed", "last_logged_step": "10"},
            {"seed": "101", "status": "completed", "last_logged_step": "11"},
            {"seed": "102", "status": "completed", "last_logged_step": "12"},
        ]
        complete, incomplete = module.close02_completion_state(rows, expected_seeds=(100, 101, 102))
        self.assertTrue(complete)
        self.assertEqual([], incomplete)

        rows[-1]["status"] = "running"
        complete, incomplete = module.close02_completion_state(rows, expected_seeds=(100, 101, 102))
        self.assertFalse(complete)
        self.assertEqual("102", incomplete[0]["seed"])

    def test_attempt_loop_retries_until_complete(self) -> None:
        module = load_script_module()
        complete_csv_lines = ["dataset,arm,status,last_logged_step"]
        for dataset in module.TARGET_DATASETS:
            for arm in module.TARGET_ARMS:
                complete_csv_lines.append(f"{dataset},{arm},completed,10")
        complete_csv = "\n".join(complete_csv_lines) + "\n"
        incomplete_csv = complete_csv.replace("Steam,global_p,completed,10", "Steam,global_p,running,30")

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "sprint07.log"
            runner = mock.Mock(
                side_effect=[
                    subprocess.CompletedProcess(args=["ssh"], returncode=255, stdout="", stderr="timeout"),
                    subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout=incomplete_csv, stderr=""),
                    subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout=complete_csv, stderr=""),
                ]
            )
            sleeper = mock.Mock()

            ok = module.run_attempt_loop(
                status_command=["ssh", "l20", "dummy"],
                log_path=log_path,
                max_attempts=4,
                interval_seconds=5,
                runner=runner,
                sleeper=sleeper,
            )

            self.assertTrue(ok)
            self.assertEqual(3, runner.call_count)
            self.assertEqual(2, sleeper.call_count)
            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn("query failed", log_text)
            self.assertIn("sprint07 incomplete", log_text)
            self.assertIn("sprint07 complete", log_text)

    def test_close02_attempt_loop_retries_until_complete(self) -> None:
        module = load_script_module()
        complete_csv = (
            "seed,status,last_logged_step\n"
            "100,completed,5000\n"
            "101,completed,6000\n"
            "102,completed,7000\n"
        )
        incomplete_csv = complete_csv.replace("102,completed,7000", "102,running,4000")

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "close02.log"
            runner = mock.Mock(
                side_effect=[
                    subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout=incomplete_csv, stderr=""),
                    subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout=complete_csv, stderr=""),
                ]
            )
            sleeper = mock.Mock()

            ok = module.run_close02_attempt_loop(
                status_command=["ssh", "l20", "dummy"],
                log_path=log_path,
                expected_seeds=(100, 101, 102),
                max_attempts=3,
                interval_seconds=5,
                runner=runner,
                sleeper=sleeper,
            )

            self.assertTrue(ok)
            self.assertEqual(2, runner.call_count)
            sleeper.assert_called_once_with(5)
            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn("close02 incomplete", log_text)
            self.assertIn("close02 complete", log_text)

    def test_attempt_loop_fails_after_max_attempts(self) -> None:
        module = load_script_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "sprint07.log"
            runner = mock.Mock(return_value=subprocess.CompletedProcess(args=["ssh"], returncode=255, stdout="", stderr="timeout"))
            sleeper = mock.Mock()

            ok = module.run_attempt_loop(
                status_command=["ssh", "l20", "dummy"],
                log_path=log_path,
                max_attempts=2,
                interval_seconds=7,
                runner=runner,
                sleeper=sleeper,
            )

            self.assertFalse(ok)
            self.assertEqual(2, runner.call_count)
            sleeper.assert_called_once_with(7)
            self.assertIn("exhausted 2 attempts", log_path.read_text(encoding="utf-8"))

    def test_launch_close02_followup_logs_success(self) -> None:
        module = load_script_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "sprint07.log"
            runner = mock.Mock(
                return_value=subprocess.CompletedProcess(
                    args=["python"],
                    returncode=0,
                    stdout="ssh l20 remote-command",
                    stderr="",
                )
            )

            ok = module.launch_close02_followup(
                command=["python", "scripts/launch_close02_ml1m_noise_floor_tmux.py", "--seeds", "100"],
                log_path=log_path,
                runner=runner,
            )

            self.assertTrue(ok)
            runner.assert_called_once()
            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn("launching CLOSE-02", log_text)
            self.assertIn("CLOSE-02 launch succeeded", log_text)

    def test_launch_close02_followup_treats_timeout_as_recoverable(self) -> None:
        module = load_script_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "sprint07.log"

            def runner(*args, **kwargs):
                raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"], output="ssh l20 remote-command")

            ok = module.launch_close02_followup(
                command=["python", "scripts/launch_close02_ml1m_noise_floor_tmux.py", "--seeds", "100"],
                log_path=log_path,
                timeout_seconds=3,
                runner=runner,
            )

            self.assertTrue(ok)
            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn("launching CLOSE-02", log_text)
            self.assertIn("launch timed out after 3s", log_text)

    def test_main_close02_only_skips_sprint07_and_syncs_close02(self) -> None:
        module = load_script_module()
        args = types.SimpleNamespace(
            log_path=Path("E:/PreferGrow/logs/close02.log"),
            max_attempts=10,
            interval_seconds=60,
            connect_timeout=8,
            host="l20",
            remote_base="/data/Zijian/goal/RecDemo_clean_main",
            remote_python="/data/Zijian/goal/PreferGrow/.venv/bin/python",
            report_dir="/data/Zijian/goal/RecDemo_clean_main/docs/reports/data/2026-07-06-sprint07",
            local_report_dir=Path("E:/PreferGrow/docs/reports/data/2026-07-06-sprint07"),
            local_python=Path("E:/anaco/python.exe"),
            close02_run_root="/data/Zijian/goal/RecDemoRuns/close02_ml1m_noise_floor",
            close02_report_dir="/data/Zijian/goal/RecDemo_clean_main/docs/reports/data/2026-07-06-close02-ml1m-noise-floor",
            local_close02_report_dir=Path("E:/PreferGrow/docs/reports/data/2026-07-06-close02-ml1m-noise-floor"),
            launch_close02_on_complete=False,
            close02_seeds=[100, 101, 102],
            close02_only=True,
            close02_launch_timeout_seconds=30,
            print_only=False,
        )

        with mock.patch.object(module, "parse_args", return_value=args), \
            mock.patch.object(module, "run_attempt_loop") as run_attempt_loop, \
            mock.patch.object(module, "run_close02_attempt_loop", return_value=True) as run_close02_attempt_loop, \
            mock.patch.object(module, "sync_close02_artifacts", return_value=True) as sync_close02_artifacts, \
            mock.patch.object(module, "launch_close02_followup") as launch_close02_followup:
            module.main()

        run_attempt_loop.assert_not_called()
        run_close02_attempt_loop.assert_called_once()
        sync_close02_artifacts.assert_called_once()
        launch_close02_followup.assert_not_called()

    def test_sync_sprint07_artifacts_logs_success(self) -> None:
        module = load_script_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            log_path = root / "sprint07.log"
            local_report_dir = root / "report"
            runner = mock.Mock(
                return_value=subprocess.CompletedProcess(
                    args=["scp"],
                    returncode=0,
                    stdout="",
                    stderr="",
                )
            )

            ok = module.sync_sprint07_artifacts(
                commands=[
                    ["scp", "l20:/tmp/a.csv", str(local_report_dir / "a.csv")],
                    ["scp", "l20:/tmp/b.md", str(local_report_dir / "b.md")],
                ],
                log_path=log_path,
                local_report_dir=local_report_dir,
                runner=runner,
            )

            self.assertTrue(ok)
            self.assertEqual(2, runner.call_count)
            self.assertTrue(local_report_dir.exists())
            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn("syncing artifacts", log_text)
            self.assertIn("artifact sync succeeded", log_text)

    def test_sync_sprint07_artifacts_logs_failure(self) -> None:
        module = load_script_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            log_path = root / "sprint07.log"
            local_report_dir = root / "report"
            runner = mock.Mock(
                return_value=subprocess.CompletedProcess(
                    args=["scp"],
                    returncode=1,
                    stdout="",
                    stderr="network down",
                )
            )

            ok = module.sync_sprint07_artifacts(
                commands=[["scp", "l20:/tmp/a.csv", str(local_report_dir / "a.csv")]],
                log_path=log_path,
                local_report_dir=local_report_dir,
                runner=runner,
            )

            self.assertFalse(ok)
            self.assertEqual(1, runner.call_count)
            self.assertIn("artifact sync failed", log_path.read_text(encoding="utf-8"))

    def test_sync_close02_artifacts_logs_success(self) -> None:
        module = load_script_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            log_path = root / "close02.log"
            local_report_dir = root / "report"
            runner = mock.Mock(
                return_value=subprocess.CompletedProcess(
                    args=["scp"],
                    returncode=0,
                    stdout="",
                    stderr="",
                )
            )

            ok = module.sync_close02_artifacts(
                commands=[
                    ["scp", "l20:/tmp/a.csv", str(local_report_dir / "a.csv")],
                    ["scp", "l20:/tmp/b.json", str(local_report_dir / "b.json")],
                    ["scp", "l20:/tmp/c.md", str(local_report_dir / "c.md")],
                ],
                log_path=log_path,
                local_report_dir=local_report_dir,
                runner=runner,
            )

            self.assertTrue(ok)
            self.assertEqual(3, runner.call_count)
            self.assertIn("close02 complete -> syncing artifacts", log_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
