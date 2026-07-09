import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script_module():
    script_path = REPO_ROOT / "scripts" / "launch_close10_atg_noise_floor_tmux.py"
    spec = importlib.util.spec_from_file_location("launch_close10_atg_noise_floor_tmux", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class LaunchClose10AtgNoiseFloorTmuxTests(unittest.TestCase):
    def test_default_remote_base_uses_closeout_clean_root(self) -> None:
        module = load_script_module()
        self.assertEqual(
            "/data/Zijian/goal/RecDemo_clean_closeout_chain",
            str(module.DEFAULT_REMOTE_BASE),
        )

    def test_defaults_target_atg_two_seeds(self) -> None:
        module = load_script_module()
        self.assertEqual("close10_atg_noise_floor", module.DEFAULT_SESSION)
        self.assertEqual((100, 101), module.DEFAULT_SEEDS)
        self.assertEqual("ATG", module.DATASET_NAME)
        self.assertEqual(
            "/data/Zijian/goal/RecDemoRuns/close10_atg_noise_floor",
            str(module.DEFAULT_RUN_ROOT),
        )
        self.assertEqual(
            "/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/ATG",
            str(module.DEFAULT_DATASET_DIR),
        )

    def test_build_seed_inner_command_uses_atg_host_arm_and_p5_selector(self) -> None:
        module = load_script_module()
        command = module.build_seed_inner_command(
            remote_base=Path("/data/Zijian/goal/RecDemo_clean_closeout_chain"),
            run_root=Path("/data/Zijian/goal/RecDemoRuns/close10_atg_noise_floor"),
            python_bin=Path("/data/Zijian/goal/PreferGrow/.venv/bin/python"),
            dataset_dir=Path("/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/ATG"),
            seed=101,
            gpu_id=1,
        )

        # dataset dimension
        self.assertIn("training.data=ATG", command)
        self.assertIn("data.ATG.path=", command)
        self.assertIn("atg_core_seed101", command)
        self.assertIn("checkpoints-meta/ATG/best_summary_hybrid.json", command)
        # ATG host arm hyper-parameters
        self.assertIn("training.nonpreference_user_ratio=0.2", command)
        self.assertIn("optim.lr=0.001", command)
        self.assertIn("model.score_flag=True", command)
        self.assertIn("graph.gamma=0.9999", command)
        # frozen closeout protocol shared with CLOSE-02
        self.assertIn("graph.type=hybrid", command)
        self.assertIn("training.early_stop_strength=p5", command)
        self.assertIn("text_side.enabled=False", command)
        self.assertIn("random_seed=101", command)
        self.assertIn("write_best_checkpoint=True", command)
        self.assertIn("write_snapshot_checkpoint=True", command)
        self.assertIn("existing_summary", command)

    def test_build_seed_inner_command_never_references_ml1m(self) -> None:
        module = load_script_module()
        command = module.build_seed_inner_command(
            remote_base=Path("/data/Zijian/goal/RecDemo_clean_closeout_chain"),
            run_root=Path("/data/Zijian/goal/RecDemoRuns/close10_atg_noise_floor"),
            python_bin=Path("/data/Zijian/goal/PreferGrow/.venv/bin/python"),
            dataset_dir=Path("/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/ATG"),
            seed=100,
            gpu_id=1,
        )
        self.assertNotIn("ML1M", command)
        self.assertNotIn("ml1m", command)

    def test_build_session_inner_command_loops_over_requested_seeds(self) -> None:
        module = load_script_module()
        command = module.build_session_inner_command(
            remote_base=Path("/data/Zijian/goal/RecDemo_clean_closeout_chain"),
            run_root=Path("/data/Zijian/goal/RecDemoRuns/close10_atg_noise_floor"),
            python_bin=Path("/data/Zijian/goal/PreferGrow/.venv/bin/python"),
            dataset_dir=Path("/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/ATG"),
            gpu_id=0,
            seeds=(100, 101),
            force=True,
            skip_existing=False,
        )

        self.assertIn("atg_core_seed100", command)
        self.assertIn("atg_core_seed101", command)
        self.assertIn("rm -rf", command)
        self.assertNotIn("existing_summary", command)

    def test_build_remote_command_wraps_inner_command_in_tmux(self) -> None:
        module = load_script_module()
        command = module.build_remote_command(
            remote_base=Path("/data/Zijian/goal/RecDemo_clean_closeout_chain"),
            run_root=Path("/data/Zijian/goal/RecDemoRuns/close10_atg_noise_floor"),
            python_bin=Path("/data/Zijian/goal/PreferGrow/.venv/bin/python"),
            dataset_dir=Path("/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/ATG"),
            session_name="close10_atg_noise_floor",
            gpu_id=1,
        )

        self.assertIn("tmux new-session -d -s close10_atg_noise_floor", command)
        self.assertIn("tmux kill-session -t close10_atg_noise_floor", command)
        self.assertIn("single_train.py", command)

    def test_build_ssh_argv_avoids_windows_shell_quoting(self) -> None:
        module = load_script_module()
        argv = module.build_ssh_argv(host="l20", remote_command="cd /data/Zijian/goal/RecDemo_clean_closeout_chain")
        self.assertEqual("ssh", argv[0])
        self.assertEqual("l20", argv[1])
        self.assertEqual("cd /data/Zijian/goal/RecDemo_clean_closeout_chain", argv[2])


if __name__ == "__main__":
    unittest.main()
