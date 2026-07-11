import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class RepoReproContractTests(unittest.TestCase):
    def test_single_train_does_not_import_missing_local_module(self) -> None:
        source = (REPO_ROOT / "single_train.py").read_text(encoding="utf-8")

        missing_imports = []
        for module_name in re.findall(r"^from\s+([A-Za-z_][A-Za-z0-9_]*)\s+import\s+", source, re.MULTILINE):
            if module_name in {"itertools", "omegaconf", "torch", "model"}:
                continue

            module_path = REPO_ROOT / f"{module_name}.py"
            if not module_path.exists():
                missing_imports.append(module_name)

        self.assertEqual(
            [],
            missing_imports,
            f"single_train.py imports missing local modules: {missing_imports}",
        )

    def test_configured_dataset_paths_exist_in_repo(self) -> None:
        config_text = (REPO_ROOT / "configs" / "config.yaml").read_text(encoding="utf-8")
        dataset_paths = dict(
            re.findall(
                r"^\s{2}([A-Za-z0-9_]+):\s*$[\r\n]+^\s{4}path:\s+(.+?)\s*$",
                config_text,
                re.MULTILINE,
            )
        )

        missing_paths = []
        for dataset_name in ("Steam", "Beauty", "ASO", "ATG", "ML1M"):
            raw_path = dataset_paths[dataset_name]
            relative_path = raw_path.strip().strip('"').strip("'")
            candidate = (REPO_ROOT / relative_path).resolve()
            if not candidate.exists():
                missing_paths.append(f"{dataset_name}:{relative_path}")

        self.assertEqual(
            [],
            missing_paths,
            f"config.yaml points to missing dataset paths: {missing_paths}",
        )

    def test_config_does_not_require_submitit_launcher(self) -> None:
        config_text = (REPO_ROOT / "configs" / "config.yaml").read_text(encoding="utf-8")
        self.assertNotIn(
            "override hydra/launcher: submitit_slurm",
            config_text,
            "config.yaml should not require the submitit Slurm launcher for local reproduction",
        )

    def test_transformer_exposes_extended_text_side_knobs(self) -> None:
        source = (REPO_ROOT / "model" / "transformer.py").read_text(encoding="utf-8")
        for knob in (
            "agreement_weight",
            "completeness_weight",
            "history_reliability_weight",
            "ess_weight",
            "recency_weight",
            "stability_weight",
            "max_temperature_scale",
            "popularity_mix_scale",
            "popularity_mix_power",
            "center_embeddings",
            "pseudo_mass_scale",
            "pseudo_mass_power",
            "ablation_mode",
            "injection_mode",
            "encoder_context_scale",
            "loss_weight_scale",
            "gate_dataset_scale_override",
            "require_gate_source",
        ):
            self.assertIn(
                f'text_side_cfg.get("{knob}"',
                source,
                f"transformer.py should pass text_side.{knob} through to the text-side builder",
            )

    def test_beauty_corrupted_batch_supports_three_way_injection_experiments(self) -> None:
        source = (REPO_ROOT / "scripts" / "run_beauty_corrupted_ranking_batch.sh").read_text(encoding="utf-8")
        for experiment_name in ("kernel_u", "encoder_u", "loss_u"):
            self.assertIn(
                f"{experiment_name})",
                source,
                f"run_beauty_corrupted_ranking_batch.sh should support the {experiment_name} experiment",
            )
        for knob in ("text_side.injection_mode", "text_side.loss_weight_scale"):
            self.assertIn(
                knob,
                source,
                f"run_beauty_corrupted_ranking_batch.sh should wire {knob} into single_train.py",
            )

    def test_beauty_corrupted_batch_wires_checkpoint_retention_knobs(self) -> None:
        source = (REPO_ROOT / "scripts" / "run_beauty_corrupted_ranking_batch.sh").read_text(encoding="utf-8")
        for expected_literal in (
            'WRITE_SNAPSHOT_CHECKPOINT="${WRITE_SNAPSHOT_CHECKPOINT:-True}"',
            'WRITE_BEST_CHECKPOINT="${WRITE_BEST_CHECKPOINT:-True}"',
            'export WRITE_SNAPSHOT_CHECKPOINT="$WRITE_SNAPSHOT_CHECKPOINT"',
            'export WRITE_BEST_CHECKPOINT="$WRITE_BEST_CHECKPOINT"',
            '+training.write_snapshot_checkpoint="$WRITE_SNAPSHOT_CHECKPOINT"',
            '+training.write_best_checkpoint="$WRITE_BEST_CHECKPOINT"',
        ):
            self.assertIn(
                expected_literal,
                source,
                f"run_beauty_corrupted_ranking_batch.sh should preserve checkpoint retention knob {expected_literal}",
            )

    def test_beauty_power20_three_way_batch_exists_for_corruption_mainpath(self) -> None:
        launcher_path = REPO_ROOT / "scripts" / "run_beauty_power20_3way_batch.sh"
        self.assertTrue(
            launcher_path.exists(),
            "main-path corruption-side 3-way should have a dedicated power20 launcher script",
        )

        source = launcher_path.read_text(encoding="utf-8")
        for experiment_name in ("kernel_u", "encoder_u", "loss_u"):
            self.assertIn(
                f"{experiment_name})",
                source,
                f"run_beauty_power20_3way_batch.sh should support the {experiment_name} experiment",
            )
        for knob in ("text_side.injection_mode", "text_side.loss_weight_scale"):
            self.assertIn(
                knob,
                source,
                f"run_beauty_power20_3way_batch.sh should wire {knob} into single_train.py",
            )
        for expected_literal in (
            'AGREEMENT_WEIGHT="0.35"',
            'COMPLETENESS_WEIGHT="0.05"',
            'HISTORY_RELIABILITY_WEIGHT="0.60"',
            'MAX_TEMPERATURE_SCALE="${MAX_TEMPERATURE_SCALE:-1.4}"',
            'MIN_PSEUDO_MASS="${MIN_PSEUDO_MASS:-0.03}"',
            'PSEUDO_MASS_POWER="${PSEUDO_MASS_POWER:-2.0}"',
        ):
            self.assertIn(
                expected_literal,
                source,
                f"run_beauty_power20_3way_batch.sh should preserve the power20 main-path setting {expected_literal}",
            )


if __name__ == "__main__":
    unittest.main()
