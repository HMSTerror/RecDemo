import hashlib
import json
import os
import shutil
import shlex
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_text_side_main_table_tmux.sh"


def sha256_paths(*paths: Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def write_fake_single_train(path: Path) -> None:
    path.write_text(
        textwrap.dedent(
            """\
            import json
            import sys
            from pathlib import Path

            args = {}
            for raw_arg in sys.argv[1:]:
                if "=" not in raw_arg:
                    continue
                key, value = raw_arg.split("=", 1)
                args[key] = value

            work_dir = Path(args["work_dir"])
            dataset = args["training.data"]
            work_dir.mkdir(parents=True, exist_ok=True)
            (work_dir / "captured_args.txt").write_text("\\n".join(sys.argv[1:]) + "\\n", encoding="utf-8")

            summary_path = work_dir / "checkpoints-meta" / dataset / "best_summary_proposal_adaptive.json"
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_payload = {
                "best_step": 1234,
                "best_metric": 0.25,
                "validation": {
                    "p2": {"ndcg": [0.0, 0.0, 0.11]},
                    "p5": {"ndcg": [0.0, 0.0, 0.25]},
                    "p10": {"ndcg": [0.0, 0.0, 0.25]},
                },
                "test": {
                    "p2": {"ndcg": [0.0, 0.0, 0.22]},
                    "p5": {"ndcg": [0.0, 0.0, 0.33]},
                    "p10": {"ndcg": [0.0, 0.0, 0.44]},
                },
            }
            summary_path.write_text(json.dumps(summary_payload), encoding="utf-8")
            """
        ),
        encoding="utf-8",
    )


def to_wsl_path(path: Path) -> str:
    posix = path.resolve().as_posix()
    if len(posix) >= 3 and posix[1:3] == ":/":
        return f"/mnt/{posix[0].lower()}{posix[2:]}"
    return posix


def decode_output(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace").replace("\x00", "")


def build_bash_command(*, env_map: dict[str, str], repo_root: Path) -> str:
    env_prefix = " ".join(f"{key}={shlex.quote(value)}" for key, value in env_map.items())
    return f"{env_prefix} {shlex.quote(to_wsl_path(SCRIPT_PATH))} {shlex.quote(to_wsl_path(repo_root))}"


def base_script_env() -> dict[str, str]:
    return {
        "WRITE_SNAPSHOT_CHECKPOINT": "False",
        "WRITE_BEST_CHECKPOINT": "True",
        "EARLY_STOP_METRIC": "ndcg10",
        "EARLY_STOP_STRENGTH": "p5",
        "TEXT_KERNEL_VERSION": "v2",
        "TEXT_TEMPERATURE": "0.2",
        "TEXT_G_MAX": "0.5",
        "TEXT_AGREEMENT_K": "2.0",
        "TEXT_AGREEMENT_WEIGHT": "0.45",
        "TEXT_COMPLETENESS_WEIGHT": "0.15",
        "TEXT_HISTORY_RELIABILITY_WEIGHT": "0.40",
        "TEXT_ESS_WEIGHT": "0.20",
        "TEXT_RECENCY_WEIGHT": "0.30",
        "TEXT_STABILITY_WEIGHT": "0.50",
        "TEXT_MAX_TEMPERATURE_SCALE": "2.0",
        "TEXT_MIN_PSEUDO_MASS": "0.05",
        "TEXT_POPULARITY_MIX_SCALE": "1.0",
        "TEXT_POPULARITY_MIX_POWER": "1.0",
        "TEXT_PSEUDO_MASS_SCALE": "1.0",
        "TEXT_PSEUDO_MASS_POWER": "1.0",
        "TEXT_CENTER_EMBEDDINGS": "False",
        "TEXT_INJECTION_MODE": "kernel",
    }


class RunTextSideMainTableTmuxTests(unittest.TestCase):
    def test_dry_run_launcher_exports_text_ablation_mode(self) -> None:
        bash = shutil.which("bash")
        if bash is None:
            self.skipTest("bash is not available")

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            repo_root = root / "fake_repo"
            repo_root.mkdir()
            run_root = root / "runs"

            command = build_bash_command(
                env_map={
                    **base_script_env(),
                    "RUN_ROOT": to_wsl_path(run_root),
                    "SESSION_PREFIX": "ablationtest",
                    "GPU_IDS_CSV": "7",
                    "DATASETS_CSV": "ML1M",
                    "DRY_RUN": "1",
                    "TEXT_ABLATION_MODE": "u_shuffle",
                },
                repo_root=repo_root,
            )
            result = subprocess.run(
                [bash, "-lc", command],
                check=False,
                capture_output=True,
                cwd=REPO_ROOT,
            )

            self.assertEqual(0, result.returncode, decode_output(result.stderr) or decode_output(result.stdout))
            launcher_path = run_root / "ablationtest_gpu7" / "run_batch.sh"
            self.assertTrue(launcher_path.exists(), f"missing launcher: {launcher_path}")
            launcher_text = launcher_path.read_text(encoding="utf-8")
            self.assertIn('export TEXT_ABLATION_MODE="u_shuffle"', launcher_text)

    def test_inner_run_uses_text_ablation_mode_and_records_it_in_manifest(self) -> None:
        bash = shutil.which("bash")
        if bash is None:
            self.skipTest("bash is not available")

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            repo_root = root / "fake_repo"
            repo_root.mkdir()
            write_fake_single_train(repo_root / "single_train.py")

            dataset_root = root / "datasets"
            dataset_dir = dataset_root / "ML1M"
            dataset_dir.mkdir(parents=True)
            text_bank_path = dataset_dir / "text_bank.csv"
            embeddings_path = dataset_dir / "sentence_t5_xl_item_emb.pt"
            null_curve_path = dataset_dir / "agreement_null_curves.json"
            split_path = dataset_dir / "train_data.df"
            text_bank_path.write_text("item_id,text\n1,foo\n", encoding="utf-8")
            embeddings_path.write_bytes(b"embeddings")
            null_curve_path.write_text("{\"bins\": []}\n", encoding="utf-8")
            split_path.write_bytes(b"split")

            utility_report_path = root / "gate0_text_utility_report.json"
            utility_report_path.write_text(
                json.dumps(
                    {
                        "datasets": [
                            {
                                "dataset": "ML1M",
                                "bank_hash": sha256_paths(text_bank_path, embeddings_path),
                                "split_hash": sha256_paths(split_path),
                                "u_ds_popularity": 0.61,
                                "phi_u_ds": 0.0,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            run_root = root / "runs"
            command = build_bash_command(
                env_map={
                    **base_script_env(),
                    "INNER_RUN": "1",
                    "PYTHON_BIN": "python3",
                    "DATASET_ROOT": to_wsl_path(dataset_root),
                    "RUN_ROOT": to_wsl_path(run_root),
                    "GPU_IDS_CSV": "5",
                    "DATASETS_CSV": "ML1M",
                    "TEXT_UTILITY_REPORT_PATH": to_wsl_path(utility_report_path),
                    "TEXT_ABLATION_MODE": "global_p",
                },
                repo_root=repo_root,
            )
            result = subprocess.run(
                [bash, "-lc", command],
                check=False,
                capture_output=True,
                cwd=REPO_ROOT,
            )

            self.assertEqual(0, result.returncode, decode_output(result.stderr) or decode_output(result.stdout))
            run_dir = run_root / "ml1m_proposal_adaptive_mainpath"
            captured_args = (run_dir / "captured_args.txt").read_text(encoding="utf-8")
            self.assertIn("text_side.ablation_mode=global_p", captured_args)

            manifest_path = run_dir / "checkpoints-meta" / "ML1M" / "frozen_run_manifest.json"
            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("global_p", manifest_payload["frozen_config"]["ablation_mode"])
            self.assertEqual(
                to_wsl_path(repo_root),
                manifest_payload["provenance"]["repo_root"],
            )


if __name__ == "__main__":
    unittest.main()
