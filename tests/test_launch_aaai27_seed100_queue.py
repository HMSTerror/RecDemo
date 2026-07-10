import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    path = REPO_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class QueueLaunchTests(unittest.TestCase):
    def test_local_launcher_uses_ssh_argv_and_batch_mode(self) -> None:
        module = load("launch_aaai27_seed100_queue")
        argv = module.build_ssh_argv(
            host="zijian@172.18.0.40",
            remote_python="/data/Zijian/goal/PreferGrow/.venv/bin/python",
            remote_entry="/data/Zijian/goal/aaai27_bundle/scripts/aaai27_remote_tmux_entry.py",
            queue_root="/data/Zijian/goal/RecDemoRuns/aaai27_seed100_resident_20260710-220000",
            manifest="/data/Zijian/goal/RecDemoRuns/aaai27_seed100_resident_20260710-220000/queue/queue_seed100.json",
            session="aaai27_seed100_queue",
        )
        self.assertEqual(["ssh", "-n", "-T", "-o", "BatchMode=yes"], argv[:5])
        self.assertEqual("zijian@172.18.0.40", argv[5])
        self.assertIn("aaai27_remote_tmux_entry.py", argv[6])
        self.assertNotIn("kill-session", argv[6])

    def test_print_only_does_not_spawn_and_keeps_remote_command_one_argument(self) -> None:
        module = load("launch_aaai27_seed100_queue")
        with mock.patch.object(module.subprocess, "run") as run:
            argv = module.launch_queue(
                host="zijian@172.18.0.40",
                remote_python="/data/with spaces/python",
                remote_entry="/data/with spaces/remote entry.py",
                queue_root="/data/with spaces/queue root",
                manifest="/data/with spaces/queue root/queue/seed100.json",
                session="aaai27_seed100_queue",
                print_only=True,
            )
        run.assert_not_called()
        self.assertEqual(7, len(argv))
        self.assertIn("/data/with spaces/remote entry.py", argv[6])
        self.assertNotIn("kill-session", argv[6])

    def test_remote_entry_returns_matching_live_session(self) -> None:
        module = load("aaai27_remote_tmux_entry")
        runner = mock.Mock(return_value=subprocess.CompletedProcess([], 0, "", ""))
        with mock.patch.object(module.socket, "gethostname", return_value="ubuntu"):
            result = module.ensure_session(
                session="aaai27_seed100_queue",
                queue_root=Path("/srv/queue"),
                manifest=Path("/srv/queue/queue/queue_seed100.json"),
                python_bin=Path("/opt/venv/bin/python"),
                controller_entry=Path("/srv/bundle/scripts/aaai27_resident_queue.py"),
                runner=runner,
                metadata={
                    "session": "aaai27_seed100_queue",
                    "queue_root": "/srv/queue",
                    "manifest_sha256": "a" * 64,
                },
                manifest_sha256="a" * 64,
            )
        self.assertEqual("already_running", result)
        self.assertFalse(any("kill-session" in item for call in runner.call_args_list for item in call.args[0]))

    def test_remote_entry_refuses_live_session_without_metadata(self) -> None:
        module = load("aaai27_remote_tmux_entry")
        runner = mock.Mock(return_value=subprocess.CompletedProcess([], 0, "", ""))
        with mock.patch.object(module.socket, "gethostname", return_value="ubuntu"):
            with self.assertRaisesRegex(RuntimeError, "metadata missing"):
                module.ensure_session(
                    session="aaai27_seed100_queue",
                    queue_root=Path("/srv/queue"),
                    manifest=Path("/srv/queue/queue/queue_seed100.json"),
                    python_bin=Path("/opt/venv/bin/python"),
                    controller_entry=Path("/srv/bundle/scripts/aaai27_resident_queue.py"),
                    runner=runner,
                    metadata=None,
                    manifest_sha256="a" * 64,
                )

    def test_remote_entry_rejects_mismatched_live_metadata(self) -> None:
        module = load("aaai27_remote_tmux_entry")
        runner = mock.Mock(return_value=subprocess.CompletedProcess([], 0, "", ""))
        with mock.patch.object(module.socket, "gethostname", return_value="ubuntu"):
            with self.assertRaisesRegex(RuntimeError, "metadata mismatch"):
                module.ensure_session(
                    session="aaai27_seed100_queue",
                    queue_root=Path("/srv/queue"),
                    manifest=Path("/srv/queue/queue/queue_seed100.json"),
                    python_bin=Path("/opt/venv/bin/python"),
                    controller_entry=Path("/srv/bundle/scripts/aaai27_resident_queue.py"),
                    runner=runner,
                    metadata={
                        "session": "other_session",
                        "queue_root": "/srv/queue",
                        "manifest_sha256": "a" * 64,
                    },
                    manifest_sha256="a" * 64,
                )
        runner.assert_not_called()

    def test_remote_entry_does_not_restart_terminal_queue(self) -> None:
        module = load("aaai27_remote_tmux_entry")
        runner = mock.Mock(return_value=subprocess.CompletedProcess([], 1, "", ""))
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "state").mkdir()
            (root / "state" / "TERMINAL.json").write_text(json.dumps({"status": "terminal"}), encoding="utf-8")
            with mock.patch.object(module.socket, "gethostname", return_value="ubuntu"):
                result = module.ensure_session(
                    session="aaai27_seed100_queue",
                    queue_root=root,
                    manifest=root / "queue.json",
                    python_bin=Path("/opt/venv/bin/python"),
                    controller_entry=Path("/srv/bundle/scripts/aaai27_resident_queue.py"),
                    runner=runner,
                    metadata={
                        "session": "aaai27_seed100_queue",
                        "queue_root": str(root),
                        "manifest_sha256": "a" * 64,
                    },
                    manifest_sha256="a" * 64,
                )
        self.assertEqual("terminal", result)
        runner.assert_called_once()
        self.assertNotIn("new-session", runner.call_args.args[0])

    def test_remote_entry_starts_missing_session_without_kill(self) -> None:
        module = load("aaai27_remote_tmux_entry")
        responses = [
            subprocess.CompletedProcess([], 1, "", "no session"),
            subprocess.CompletedProcess([], 0, "", ""),
        ]
        runner = mock.Mock(side_effect=responses)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with mock.patch.object(module.socket, "gethostname", return_value="ubuntu"):
                result = module.ensure_session(
                    session="aaai27_seed100_queue",
                    queue_root=root,
                    manifest=root / "queue.json",
                    python_bin=Path("/opt/venv/bin/python"),
                    controller_entry=Path("/srv/bundle/scripts/aaai27_resident_queue.py"),
                    runner=runner,
                    metadata={
                        "session": "aaai27_seed100_queue",
                        "queue_root": str(root),
                        "manifest_sha256": "a" * 64,
                    },
                    manifest_sha256="a" * 64,
                )
        self.assertEqual("started", result)
        new_session_argv = runner.call_args_list[1].args[0]
        self.assertEqual(["tmux", "new-session", "-d", "-s", "aaai27_seed100_queue"], new_session_argv[:5])
        self.assertNotIn("kill-session", " ".join(new_session_argv))


if __name__ == "__main__":
    unittest.main()
