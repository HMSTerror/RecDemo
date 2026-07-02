import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd
import torch


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script_module():
    script_path = REPO_ROOT / "scripts" / "build_gate0_failure_diagnostic.py"
    spec = importlib.util.spec_from_file_location("build_gate0_failure_diagnostic", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def write_toy_dataset(dataset_dir: Path, *, mu_null: float) -> None:
    pd.DataFrame(
        [
            {
                "item_id": 0,
                "source_id": "a0",
                "title": "Alpha",
                "brand": "BrandA",
                "categories": "CatA",
                "description": "Alpha desc",
                "text": "Alpha",
            },
            {
                "item_id": 1,
                "source_id": "a1",
                "title": "Beta",
                "brand": "BrandB",
                "categories": "CatB",
                "description": "Beta desc",
                "text": "Beta",
            },
        ]
    ).to_csv(dataset_dir / "item_metadata.csv", index=False)
    torch.save(
        {
            "item_ids": [0, 1],
            "embeddings": torch.tensor([[1.0, 0.0], [1.0, 0.0]], dtype=torch.float32),
            "field_coverage": torch.tensor([1.0, 1.0], dtype=torch.float32),
        },
        dataset_dir / "sentence_t5_xl_item_emb.pt",
    )
    (dataset_dir / "agreement_null_curves.json").write_text(
        json.dumps(
            {
                "protocol": {
                    "agreement_k": 2.0,
                },
                "length_bins": {
                    "2": {
                        "mu": mu_null,
                        "sigma": 0.25,
                        "samples": 16,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    split_df = pd.DataFrame(
        [
            {"seq": [0, 0], "len_seq": 2, "next": 1},
            {"seq": [1, 1], "len_seq": 2, "next": 0},
        ]
    )
    split_df.to_pickle(dataset_dir / "train_data.df")
    split_df.to_pickle(dataset_dir / "val_data.df")
    split_df.to_pickle(dataset_dir / "test_data.df")


class BuildGate0FailureDiagnosticTests(unittest.TestCase):
    def test_classify_primary_driver_prefers_agreement_residual_signal(self) -> None:
        module = load_script_module()

        driver, evidence = module._classify_primary_driver(
            [
                {"dataset": "ML1M", "median_agreement_residual": 0.70, "median_sigma_null": 0.25, "median_residual_to_sigma": 2.80},
                {"dataset": "Steam", "median_agreement_residual": 0.05, "median_sigma_null": 0.25, "median_residual_to_sigma": 0.20},
                {"dataset": "Beauty", "median_agreement_residual": 0.08, "median_sigma_null": 0.25, "median_residual_to_sigma": 0.32},
            ]
        )

        self.assertEqual("agreement_residual_above_mu_null", driver)
        self.assertIn("ML1M median(agreement-mu_null)=0.700000", evidence)

    def test_classify_primary_driver_can_flag_null_curve_spread_or_scaling(self) -> None:
        module = load_script_module()

        driver, evidence = module._classify_primary_driver(
            [
                {"dataset": "ML1M", "median_agreement_residual": 0.011, "median_sigma_null": 0.0040, "median_residual_to_sigma": 2.75},
                {"dataset": "Steam", "median_agreement_residual": 0.002, "median_sigma_null": 0.0075, "median_residual_to_sigma": 0.27},
                {"dataset": "Beauty", "median_agreement_residual": 0.007, "median_sigma_null": 0.0051, "median_residual_to_sigma": 1.37},
            ]
        )

        self.assertEqual("null_curve_spread_or_scaling_mismatch", driver)
        self.assertIn("residual/sigma=2.750000", evidence)

    def test_build_failure_diagnostic_writes_artifacts_and_blocks_sprint05(self) -> None:
        module = load_script_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            datasets = {
                "ML1M": root / "ML1M",
                "Steam": root / "Steam",
                "Beauty": root / "Beauty",
                "ATG": root / "ATG",
            }
            for path in datasets.values():
                path.mkdir()

            write_toy_dataset(datasets["ML1M"], mu_null=0.25)
            write_toy_dataset(datasets["Steam"], mu_null=0.95)
            write_toy_dataset(datasets["Beauty"], mu_null=0.95)
            write_toy_dataset(datasets["ATG"], mu_null=0.95)

            output_dir = root / "report"
            output_dir.mkdir()
            gate0_report = {
                "gate0_verdict": "fail",
                "gate0_reasons": [
                    "|median_u_tilde(ML1M)|=1.500000 exceeds 0.50",
                    "median_u_tilde(Steam)=0.100000 is not greater than ML1M=1.500000",
                ],
            }
            (output_dir / "gate0_u_tilde_report.json").write_text(
                json.dumps(gate0_report, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            report = module.build_gate0_failure_diagnostic(
                dataset_dirs=datasets,
                output_dir=output_dir,
            )

            self.assertEqual("fail", report["gate0_verdict"])
            self.assertEqual("blocked", report["sprint05_status"])
            self.assertEqual("calibration_repair_first", report["recommended_next_path"])
            self.assertEqual("agreement_residual_above_mu_null", report["primary_driver"])

            summary_df = pd.read_csv(output_dir / "gate0_failure_component_summary.csv")
            self.assertCountEqual(summary_df["dataset"].tolist(), ["ML1M", "Steam", "Beauty", "ATG"])
            self.assertTrue((output_dir / "gate0_failure_diagnostic.md").exists())
            self.assertTrue((output_dir / "gate0_failure_diagnostic.json").exists())

            markdown_text = (output_dir / "gate0_failure_diagnostic.md").read_text(encoding="utf-8")
            self.assertIn("`SPRINT-05` status: `blocked`", markdown_text)
            self.assertIn("calibration_repair_first", markdown_text)
            self.assertIn("Gate0 report JSON", markdown_text)


if __name__ == "__main__":
    unittest.main()
