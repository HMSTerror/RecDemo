import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script_module():
    script_path = REPO_ROOT / "scripts" / "sync_remote_recdemo_code.py"
    spec = importlib.util.spec_from_file_location("sync_remote_recdemo_code", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class SyncRemoteRecDemoCodeTests(unittest.TestCase):
    def test_build_sync_pairs_map_local_files_to_remote_repo(self) -> None:
        module = load_script_module()

        pairs = module.build_sync_pairs(
            repo_root=Path("/work/PreferGrow"),
            remote_repo_root=Path("/data/Zijian/goal/RecDemo"),
            rel_paths=("scripts/build_gate0_utilde_report.py", "model/text_side.py"),
        )

        self.assertEqual(Path("/work/PreferGrow/scripts/build_gate0_utilde_report.py"), pairs[0][0])
        self.assertEqual("/data/Zijian/goal/RecDemo/scripts/build_gate0_utilde_report.py", str(pairs[0][1]))
        self.assertEqual("/data/Zijian/goal/RecDemo/model/text_side.py", str(pairs[1][1]))

    def test_build_sync_argv_uses_shell_free_ssh_with_timeout(self) -> None:
        module = load_script_module()

        argv = module.build_sync_argv(
            host="l20",
            remote_repo_root=Path("/data/Zijian/goal/RecDemo"),
            rel_paths=("scripts/build_gate0_utilde_report.py",),
            connect_timeout=9,
            verify=True,
        )

        self.assertEqual("ssh", argv[0])
        self.assertEqual("-o", argv[1])
        self.assertEqual("ConnectTimeout=9", argv[2])
        self.assertEqual("l20", argv[3])
        self.assertIn("tar -xf - -C /data/Zijian/goal/RecDemo", argv[4])
        self.assertIn("python3 -m py_compile /data/Zijian/goal/RecDemo/scripts/build_gate0_utilde_report.py", argv[4])

    def test_build_archive_payload_contains_requested_files(self) -> None:
        module = load_script_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / "scripts").mkdir()
            (repo_root / "scripts" / "build_gate0_utilde_report.py").write_text("print('ok')\n", encoding="utf-8")

            payload = module.build_archive_payload(
                repo_root=repo_root,
                rel_paths=("scripts/build_gate0_utilde_report.py",),
            )

            self.assertGreater(len(payload), 0)
            self.assertIn(b"build_gate0_utilde_report.py", payload)

    def test_sync_remote_code_runs_remote_py_compile_verification(self) -> None:
        module = load_script_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / "scripts").mkdir()
            (repo_root / "model").mkdir()
            (repo_root / "scripts" / "build_gate0_utilde_report.py").write_text("print('ok')\n", encoding="utf-8")
            (repo_root / "model" / "text_side.py").write_text("print('ok')\n", encoding="utf-8")
            runner = mock.Mock(return_value=subprocess.CompletedProcess(args=["ssh"], returncode=0))

            module.sync_remote_code(
                repo_root=repo_root,
                remote_repo_root=Path("/data/Zijian/goal/RecDemo"),
                host="l20",
                rel_paths=("scripts/build_gate0_utilde_report.py", "model/text_side.py"),
                runner=runner,
                sleeper=mock.Mock(),
            )

            self.assertEqual(1, runner.call_count)
            verify_argv = runner.call_args_list[-1].args[0]
            self.assertEqual("ssh", verify_argv[0])
            self.assertIn("tar -xf - -C /data/Zijian/goal/RecDemo", verify_argv[4])
            self.assertIn("python3 -m py_compile", verify_argv[4])
            self.assertIn("/data/Zijian/goal/RecDemo/scripts/build_gate0_utilde_report.py", verify_argv[4])
            self.assertIn("/data/Zijian/goal/RecDemo/model/text_side.py", verify_argv[4])

    def test_sync_remote_code_retries_archive_push_after_transient_failure(self) -> None:
        module = load_script_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / "scripts").mkdir()
            (repo_root / "scripts" / "build_gate0_utilde_report.py").write_text("print('ok')\n", encoding="utf-8")
            sleeper = mock.Mock()
            runner = mock.Mock(
                side_effect=[
                    subprocess.CalledProcessError(returncode=255, cmd=["ssh"]),
                    subprocess.CompletedProcess(args=["ssh"], returncode=0),
                ]
            )

            module.sync_remote_code(
                repo_root=repo_root,
                remote_repo_root=Path("/data/Zijian/goal/RecDemo"),
                host="l20",
                rel_paths=("scripts/build_gate0_utilde_report.py",),
                retries=2,
                retry_delay_seconds=7,
                runner=runner,
                sleeper=sleeper,
            )

            self.assertEqual(2, runner.call_count)
            sleeper.assert_called_once_with(7)

    def test_format_sync_plan_lists_sync_targets_and_verify_step(self) -> None:
        module = load_script_module()
        local_path = Path("/work/PreferGrow/scripts/build_gate0_utilde_report.py")

        plan = module.format_sync_plan(
            repo_root=Path("/work/PreferGrow"),
            remote_repo_root=Path("/data/Zijian/goal/RecDemo"),
            host="l20",
            rel_paths=("scripts/build_gate0_utilde_report.py",),
            verify=True,
            connect_timeout=15,
        )

        self.assertIn(
            f"SYNC {local_path} -> l20:/data/Zijian/goal/RecDemo/scripts/build_gate0_utilde_report.py",
            plan,
        )
        self.assertIn("SYNC+VERIFY ssh -o ConnectTimeout=15 l20", plan)


if __name__ == "__main__":
    unittest.main()
