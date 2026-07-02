import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script_module():
    script_path = REPO_ROOT / "scripts" / "launch_beauty_text_side_tmux.py"
    spec = importlib.util.spec_from_file_location("launch_beauty_text_side_tmux", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class LaunchBeautyTextSideTmuxTests(unittest.TestCase):
    def test_build_remote_beauty_command_targets_repo_dataset_model_and_v2_overrides(self) -> None:
        module = load_script_module()
        command = module.build_remote_beauty_command(
            remote_repo_root=Path("/data/Zijian/goal/RecDemo"),
            dataset_dir=Path("/data/Zijian/goal/RecDemo/dataset/Beauty"),
            model_path=Path("/data/models/sentence-transformers/sentence-t5-xl"),
            python_bin=Path("/data/Zijian/goal/PreferGrow/.venv/bin/python3"),
            run_dir=Path("/data/Zijian/goal/RecDemoRuns/beauty_fallback_safe"),
            gpu_id=1,
        )

        self.assertIn("cd /data/Zijian/goal/RecDemo", command)
        self.assertIn("scripts/build_text_side_embeddings.py", command)
        self.assertIn("--dataset-dir /data/Zijian/goal/RecDemo/dataset/Beauty", command)
        self.assertIn("--model-path /data/models/sentence-transformers/sentence-t5-xl", command)
        self.assertIn("scripts/build_agreement_null_curves.py", command)
        self.assertIn("single_train.py", command)
        self.assertIn("cuda=1", command)
        self.assertIn("training.data=Beauty", command)
        self.assertIn("data.Beauty.path=/data/Zijian/goal/RecDemo/dataset/Beauty", command)
        self.assertIn("text_side.enabled=True", command)
        self.assertIn(
            "text_side.embeddings_path=/data/Zijian/goal/RecDemo/dataset/Beauty/sentence_t5_xl_item_emb.pt",
            command,
        )
        self.assertIn(
            "text_side.agreement_null_curve_path=/data/Zijian/goal/RecDemo/dataset/Beauty/agreement_null_curves.json",
            command,
        )
        self.assertIn("text_side.kernel_version=v2", command)
        self.assertIn("work_dir=/data/Zijian/goal/RecDemoRuns/beauty_fallback_safe", command)

    def test_build_tmux_ssh_command_wraps_remote_command(self) -> None:
        module = load_script_module()
        remote_command = "cd /data/Zijian/goal/RecDemo && python3 -u single_train.py training.data=Beauty"
        ssh_command = module.build_tmux_ssh_command(
            host="l20",
            session_name="beauty_fallback_safe",
            remote_command=remote_command,
        )

        self.assertIn("ssh", ssh_command)
        self.assertIn("l20", ssh_command)
        self.assertIn("tmux new-session -d -s beauty_fallback_safe", ssh_command)
        self.assertIn("tmux kill-session -t beauty_fallback_safe", ssh_command)
        self.assertIn(remote_command, ssh_command)


if __name__ == "__main__":
    unittest.main()
