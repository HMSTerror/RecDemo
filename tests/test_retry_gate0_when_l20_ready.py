import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script_module():
    script_path = REPO_ROOT / "scripts" / "retry_gate0_when_l20_ready.py"
    spec = importlib.util.spec_from_file_location("retry_gate0_when_l20_ready", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RetryGate0WhenL20ReadyTests(unittest.TestCase):
    def test_build_sync_command_targets_sync_script_with_retries(self) -> None:
        module = load_script_module()

        command = module.build_sync_command(
            Path("E:/anaco/python.exe"),
            sync_retries=5,
            sync_retry_delay_seconds=4,
            connect_timeout=9,
        )

        self.assertEqual(str(Path("E:/anaco/python.exe")), command[0])
        self.assertTrue(command[1].endswith("scripts\\sync_remote_recdemo_code.py"))
        self.assertIn("5", command)
        self.assertIn("4", command)
        self.assertIn("9", command)

    def test_build_launch_command_targets_gate0_launcher(self) -> None:
        module = load_script_module()

        command = module.build_launch_command(Path("E:/anaco/python.exe"))

        self.assertEqual(str(Path("E:/anaco/python.exe")), command[0])
        self.assertTrue(command[1].endswith("scripts\\launch_gate0_tmux.py"))

    def test_attempt_loop_retries_until_sync_then_launch_succeeds(self) -> None:
        module = load_script_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "gate0.log"
            runner = mock.Mock(
                side_effect=[
                    subprocess.CompletedProcess(args=["sync"], returncode=1),
                    subprocess.CompletedProcess(args=["sync"], returncode=0),
                    subprocess.CompletedProcess(args=["launch"], returncode=0),
                ]
            )
            sleeper = mock.Mock()

            ok = module.run_attempt_loop(
                python_bin=Path("E:/anaco/python.exe"),
                log_path=log_path,
                max_attempts=3,
                interval_seconds=11,
                sync_retries=3,
                sync_retry_delay_seconds=3,
                connect_timeout=8,
                runner=runner,
                sleeper=sleeper,
            )

            self.assertTrue(ok)
            self.assertEqual(3, runner.call_count)
            sleeper.assert_called_once_with(11)
            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn("sync failed", log_text)
            self.assertIn("Gate0 launch ok", log_text)

    def test_attempt_loop_fails_after_max_attempts(self) -> None:
        module = load_script_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "gate0.log"
            runner = mock.Mock(return_value=subprocess.CompletedProcess(args=["sync"], returncode=1))
            sleeper = mock.Mock()

            ok = module.run_attempt_loop(
                python_bin=Path("E:/anaco/python.exe"),
                log_path=log_path,
                max_attempts=2,
                interval_seconds=7,
                sync_retries=3,
                sync_retry_delay_seconds=3,
                connect_timeout=8,
                runner=runner,
                sleeper=sleeper,
            )

            self.assertFalse(ok)
            self.assertEqual(2, runner.call_count)
            sleeper.assert_called_once_with(7)
            self.assertIn("exhausted 2 attempts", log_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
