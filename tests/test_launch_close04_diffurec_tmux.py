import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script_module():
    script_path = REPO_ROOT / "scripts" / "launch_close04_diffurec_tmux.py"
    spec = importlib.util.spec_from_file_location("launch_close04_diffurec_tmux", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class LaunchClose04DiffuRecTmuxTests(unittest.TestCase):
    def test_default_paths_use_closeout_chain_and_external_checkout(self) -> None:
        module = load_script_module()
        self.assertEqual(
            "/data/Zijian/goal/RecDemo_clean_closeout_chain",
            str(module.DEFAULT_REMOTE_BASE),
        )
        self.assertEqual(
            "/data/Zijian/goal/RecDemoExternal/DiffuRec",
            str(module.DEFAULT_UPSTREAM_ROOT),
        )

    def test_build_dataset_inner_command_clones_upstream_and_runs_wrapper(self) -> None:
        module = load_script_module()
        command = module.build_dataset_inner_command(
            remote_base=Path("/data/Zijian/goal/RecDemo_clean_closeout_chain"),
            dataset_root=Path("/data/Zijian/goal/RecDemo/dataset/paper_raw_v1"),
            run_root=Path("/data/Zijian/goal/RecDemoRuns/close04_diffurec"),
            python_bin=Path("/data/Zijian/goal/PreferGrow/.venv/bin/python"),
            upstream_root=Path("/data/Zijian/goal/RecDemoExternal/DiffuRec"),
            upstream_repo="https://github.com/WHUIR/DiffuRec.git",
            dataset="ML1M",
            gpu_id=1,
            random_seed=100,
        )

        self.assertIn("git clone https://github.com/WHUIR/DiffuRec.git", command)
        self.assertIn("run_close04_diffurec.py", command)
        self.assertIn("--dataset-name ML1M", command)
        self.assertIn("--cuda-visible-devices 1", command)
        self.assertIn("best_summary_diffurec.json", command)
        self.assertIn("diffurec_run_manifest.json", command)

    def test_build_session_inner_command_runs_requested_datasets_then_builds_table(self) -> None:
        module = load_script_module()
        command = module.build_session_inner_command(
            remote_base=Path("/data/Zijian/goal/RecDemo_clean_closeout_chain"),
            dataset_root=Path("/data/Zijian/goal/RecDemo/dataset/paper_raw_v1"),
            run_root=Path("/data/Zijian/goal/RecDemoRuns/close04_diffurec"),
            python_bin=Path("/data/Zijian/goal/PreferGrow/.venv/bin/python"),
            upstream_root=Path("/data/Zijian/goal/RecDemoExternal/DiffuRec"),
            upstream_repo="https://github.com/WHUIR/DiffuRec.git",
            output_dir=Path("/data/Zijian/goal/RecDemo_clean_closeout_chain/docs/reports/data/2026-07-07-close04-diffurec"),
            datasets=("Steam", "ML1M"),
            gpu_id=0,
        )

        self.assertIn("--dataset-name Steam", command)
        self.assertIn("--dataset-name ML1M", command)
        self.assertIn("build_close04_external_baseline_table.py", command)
        self.assertIn("--datasets Steam ML1M", command)

    def test_build_remote_command_wraps_inner_command_in_tmux(self) -> None:
        module = load_script_module()
        command = module.build_remote_command(
            remote_base=Path("/data/Zijian/goal/RecDemo_clean_closeout_chain"),
            dataset_root=Path("/data/Zijian/goal/RecDemo/dataset/paper_raw_v1"),
            run_root=Path("/data/Zijian/goal/RecDemoRuns/close04_diffurec"),
            python_bin=Path("/data/Zijian/goal/PreferGrow/.venv/bin/python"),
            upstream_root=Path("/data/Zijian/goal/RecDemoExternal/DiffuRec"),
            upstream_repo="https://github.com/WHUIR/DiffuRec.git",
            output_dir=Path("/data/Zijian/goal/RecDemo_clean_closeout_chain/docs/reports/data/2026-07-07-close04-diffurec"),
            session_name="close04_diffurec_gpu0",
            datasets=("Beauty",),
            gpu_id=0,
        )

        self.assertIn("tmux new-session -d -s close04_diffurec_gpu0", command)
        self.assertIn("tmux kill-session -t close04_diffurec_gpu0", command)
        self.assertIn("run_close04_diffurec.py", command)

    def test_build_ssh_argv_avoids_windows_shell_quoting(self) -> None:
        module = load_script_module()
        argv = module.build_ssh_argv(
            host="l20",
            remote_command="cd /data/Zijian/goal/RecDemo_clean_closeout_chain",
        )
        self.assertEqual("ssh", argv[0])
        self.assertEqual("l20", argv[1])
        self.assertEqual("cd /data/Zijian/goal/RecDemo_clean_closeout_chain", argv[2])


if __name__ == "__main__":
    unittest.main()
