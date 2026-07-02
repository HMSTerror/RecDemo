import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script_module():
    script_path = REPO_ROOT / "scripts" / "launch_gate0_tmux.py"
    spec = importlib.util.spec_from_file_location("launch_gate0_tmux", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class LaunchGate0TmuxTests(unittest.TestCase):
    def test_build_remote_gate0_command_targets_repo_datasets_and_report_dir(self) -> None:
        module = load_script_module()
        command = module.build_remote_gate0_command(
            remote_repo_root=Path("/data/Zijian/goal/RecDemo"),
            output_dir=Path("/data/Zijian/goal/RecDemo/docs/reports/data/2026-07-02-gate0"),
        )

        self.assertIn("python3 /data/Zijian/goal/RecDemo/scripts/build_gate0_utilde_report.py", command)
        self.assertIn("--dataset ML1M=/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/ML1M", command)
        self.assertIn("--dataset Steam=/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/Steam", command)
        self.assertIn("--dataset Beauty=/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/Beauty", command)
        self.assertIn("--dataset ATG=/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/ATG", command)
        self.assertIn("--output-dir /data/Zijian/goal/RecDemo/docs/reports/data/2026-07-02-gate0", command)

    def test_default_dataset_dir_map_targets_remote_paper_raw_layout(self) -> None:
        module = load_script_module()
        self.assertEqual(
            {
                "ML1M": "dataset/paper_raw_v1/ML1M",
                "Steam": "dataset/paper_raw_v1/Steam",
                "Beauty": "dataset/paper_raw_v1/Beauty",
                "ATG": "dataset/paper_raw_v1/ATG",
            },
            module.DEFAULT_DATASET_DIRS,
        )

    def test_build_tmux_ssh_command_wraps_remote_command(self) -> None:
        module = load_script_module()
        remote_command = "cd /data/Zijian/goal/RecDemo && python3 scripts/build_gate0_utilde_report.py"
        ssh_command = module.build_tmux_ssh_command(
            host="l20",
            session_name="gate0_utilde",
            remote_command=remote_command,
        )

        self.assertIn("ssh", ssh_command)
        self.assertIn("l20", ssh_command)
        self.assertIn("tmux new-session -d -s gate0_utilde", ssh_command)
        self.assertIn("tmux kill-session -t gate0_utilde", ssh_command)
        self.assertIn(remote_command, ssh_command)

    def test_build_ssh_argv_avoids_windows_shell_quoting(self) -> None:
        module = load_script_module()
        remote_command = "cd /data/Zijian/goal/RecDemo && python3 scripts/build_gate0_utilde_report.py"
        argv = module.build_ssh_argv(
            host="l20",
            session_name="gate0_utilde",
            remote_command=remote_command,
        )

        self.assertEqual("ssh", argv[0])
        self.assertEqual("l20", argv[1])
        self.assertIn("tmux new-session -d -s gate0_utilde", argv[2])
        self.assertIn(remote_command, argv[2])


if __name__ == "__main__":
    unittest.main()
