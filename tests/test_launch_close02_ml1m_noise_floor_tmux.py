import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script_module():
    script_path = REPO_ROOT / "scripts" / "launch_close02_ml1m_noise_floor_tmux.py"
    spec = importlib.util.spec_from_file_location("launch_close02_ml1m_noise_floor_tmux", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class LaunchClose02Ml1mNoiseFloorTmuxTests(unittest.TestCase):
    def test_build_seed_inner_command_uses_hybrid_core_protocol_and_p5_selector(self) -> None:
        module = load_script_module()
        command = module.build_seed_inner_command(
            remote_base=Path("/data/Zijian/goal/RecDemo_clean_main"),
            run_root=Path("/data/Zijian/goal/RecDemoRuns/close02_ml1m_noise_floor"),
            python_bin=Path("/data/Zijian/goal/PreferGrow/.venv/bin/python"),
            dataset_dir=Path("/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/ML1M"),
            seed=101,
            gpu_id=1,
        )

        self.assertIn("graph.type=hybrid", command)
        self.assertIn("training.early_stop_strength=p5", command)
        self.assertIn("text_side.enabled=False", command)
        self.assertIn("random_seed=101", command)
        self.assertIn("write_best_checkpoint=True", command)
        self.assertIn("write_snapshot_checkpoint=True", command)
        self.assertIn("existing_summary", command)

    def test_build_session_inner_command_loops_over_requested_seeds(self) -> None:
        module = load_script_module()
        command = module.build_session_inner_command(
            remote_base=Path("/data/Zijian/goal/RecDemo_clean_main"),
            run_root=Path("/data/Zijian/goal/RecDemoRuns/close02_ml1m_noise_floor"),
            python_bin=Path("/data/Zijian/goal/PreferGrow/.venv/bin/python"),
            dataset_dir=Path("/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/ML1M"),
            gpu_id=0,
            seeds=(100, 102),
            force=True,
            skip_existing=False,
        )

        self.assertIn("ml1m_core_seed100", command)
        self.assertIn("ml1m_core_seed102", command)
        self.assertIn("rm -rf", command)
        self.assertNotIn("existing_summary", command)

    def test_build_remote_command_wraps_inner_command_in_tmux(self) -> None:
        module = load_script_module()
        command = module.build_remote_command(
            remote_base=Path("/data/Zijian/goal/RecDemo_clean_main"),
            run_root=Path("/data/Zijian/goal/RecDemoRuns/close02_ml1m_noise_floor"),
            python_bin=Path("/data/Zijian/goal/PreferGrow/.venv/bin/python"),
            dataset_dir=Path("/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/ML1M"),
            session_name="close02_ml1m_noise_floor",
            gpu_id=1,
        )

        self.assertIn("tmux new-session -d -s close02_ml1m_noise_floor", command)
        self.assertIn("tmux kill-session -t close02_ml1m_noise_floor", command)
        self.assertIn("single_train.py", command)

    def test_build_ssh_argv_avoids_windows_shell_quoting(self) -> None:
        module = load_script_module()
        argv = module.build_ssh_argv(host="l20", remote_command="cd /data/Zijian/goal/RecDemo_clean_main")
        self.assertEqual("ssh", argv[0])
        self.assertEqual("l20", argv[1])
        self.assertEqual("cd /data/Zijian/goal/RecDemo_clean_main", argv[2])


if __name__ == "__main__":
    unittest.main()
