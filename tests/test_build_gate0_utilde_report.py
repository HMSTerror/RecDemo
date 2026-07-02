import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd
import torch


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script_module():
    script_path = REPO_ROOT / "scripts" / "build_gate0_utilde_report.py"
    spec = importlib.util.spec_from_file_location("build_gate0_utilde_report", script_path)
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


class BuildGate0UTildeReportTests(unittest.TestCase):
    def test_parse_dataset_args_defaults_to_paper_raw_v1_layout(self) -> None:
        module = load_script_module()
        dataset_dirs = module._parse_dataset_args([])

        self.assertEqual(REPO_ROOT / "dataset" / "paper_raw_v1" / "ML1M", dataset_dirs["ML1M"])
        self.assertEqual(REPO_ROOT / "dataset" / "paper_raw_v1" / "Steam", dataset_dirs["Steam"])
        self.assertEqual(REPO_ROOT / "dataset" / "paper_raw_v1" / "Beauty", dataset_dirs["Beauty"])
        self.assertEqual(REPO_ROOT / "dataset" / "paper_raw_v1" / "ATG", dataset_dirs["ATG"])

    def test_script_writes_gate0_dataset_summary_and_pass_verdict(self) -> None:
        module = load_script_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            datasets = {
                "ML1M": root / "ML1M",
                "Steam": root / "Steam",
                "Beauty": root / "Beauty",
                "ATG": root / "ATG",
            }
            datasets["ML1M"].mkdir()
            datasets["Steam"].mkdir()
            datasets["Beauty"].mkdir()
            datasets["ATG"].mkdir()

            write_toy_dataset(datasets["ML1M"], mu_null=1.0)
            write_toy_dataset(datasets["Steam"], mu_null=0.25)
            write_toy_dataset(datasets["Beauty"], mu_null=0.25)
            write_toy_dataset(datasets["ATG"], mu_null=0.10)

            output_dir = root / "report"
            report = module.build_gate0_report(
                dataset_dirs={name: path for name, path in datasets.items()},
                output_dir=output_dir,
            )

            self.assertEqual("pass", report["gate0_verdict"])
            self.assertEqual("open", report["sprint05_status"])
            self.assertFalse(report["main_table_retrains_blocked"])
            self.assertIn("No hypothesis revision is required", report["revised_hypothesis"])
            self.assertTrue((output_dir / "gate0_u_tilde_summary.csv").exists())
            self.assertTrue((output_dir / "gate0_u_tilde_report.md").exists())
            self.assertTrue((output_dir / "gate0_u_tilde_report.json").exists())

            summary_df = pd.read_csv(output_dir / "gate0_u_tilde_summary.csv")
            self.assertCountEqual(summary_df["dataset"].tolist(), ["ML1M", "Steam", "Beauty", "ATG"])
            self.assertTrue((summary_df["user_count"] == 6).all())

            median_by_dataset = dict(zip(summary_df["dataset"], summary_df["median_u_tilde"]))
            self.assertAlmostEqual(0.0, float(median_by_dataset["ML1M"]), places=6)
            self.assertGreater(float(median_by_dataset["Steam"]), float(median_by_dataset["ML1M"]))
            self.assertGreater(float(median_by_dataset["Beauty"]), float(median_by_dataset["ML1M"]))

            markdown_text = (output_dir / "gate0_u_tilde_report.md").read_text(encoding="utf-8")
            self.assertIn("`SPRINT-05` main-table retrains: `open`", markdown_text)

    def test_script_records_revised_hypothesis_and_keeps_sprint05_blocked_on_fail(self) -> None:
        module = load_script_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            datasets = {
                "ML1M": root / "ML1M",
                "Steam": root / "Steam",
                "Beauty": root / "Beauty",
                "ATG": root / "ATG",
            }
            datasets["ML1M"].mkdir()
            datasets["Steam"].mkdir()
            datasets["Beauty"].mkdir()
            datasets["ATG"].mkdir()

            write_toy_dataset(datasets["ML1M"], mu_null=0.25)
            write_toy_dataset(datasets["Steam"], mu_null=0.95)
            write_toy_dataset(datasets["Beauty"], mu_null=0.95)
            write_toy_dataset(datasets["ATG"], mu_null=0.95)

            output_dir = root / "report"
            report = module.build_gate0_report(
                dataset_dirs={name: path for name, path in datasets.items()},
                output_dir=output_dir,
            )

            self.assertEqual("fail", report["gate0_verdict"])
            self.assertEqual("blocked", report["sprint05_status"])
            self.assertTrue(report["main_table_retrains_blocked"])
            self.assertIn("does not drive ML1M near the null point", report["revised_hypothesis"])

            markdown_text = (output_dir / "gate0_u_tilde_report.md").read_text(encoding="utf-8")
            self.assertIn("`SPRINT-05` main-table retrains: `blocked`", markdown_text)
            self.assertIn("Length-matched null calibration alone does not drive ML1M near the null point", markdown_text)


if __name__ == "__main__":
    unittest.main()
