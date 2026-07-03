import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd
import torch


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script_module():
    script_path = REPO_ROOT / "scripts" / "build_gate0_text_utility_report.py"
    spec = importlib.util.spec_from_file_location("build_gate0_text_utility_report", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def write_toy_dataset(dataset_dir: Path) -> None:
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
            {
                "item_id": 2,
                "source_id": "a2",
                "title": "Gamma",
                "brand": "BrandC",
                "categories": "CatC",
                "description": "Gamma desc",
                "text": "Gamma",
            },
        ]
    ).to_csv(dataset_dir / "item_metadata.csv", index=False)
    torch.save(
        {
            "item_ids": [0, 1, 2],
            "embeddings": torch.tensor(
                [
                    [1.0, 0.0],
                    [1.0, 0.0],
                    [-1.0, 0.0],
                ],
                dtype=torch.float32,
            ),
        },
        dataset_dir / "sentence_t5_xl_item_emb.pt",
    )

    train_rows = (
        [{"seq": [0, 0], "len_seq": 2, "next": 1}] * 8
        + [{"seq": [2, 2], "len_seq": 2, "next": 2}] * 4
    )
    val_rows = [{"seq": [0, 0], "len_seq": 2, "next": 2}] * 8
    test_rows = [{"seq": [2, 2], "len_seq": 2, "next": 1}] * 8
    pd.DataFrame(train_rows).to_pickle(dataset_dir / "train_data.df")
    pd.DataFrame(val_rows).to_pickle(dataset_dir / "val_data.df")
    pd.DataFrame(test_rows).to_pickle(dataset_dir / "test_data.df")


class BuildGate0TextUtilityReportTests(unittest.TestCase):
    def test_build_next_item_distribution_uses_train_next_frequencies(self) -> None:
        module = load_script_module()
        train_df = pd.DataFrame(
            [
                {"next": 1},
                {"next": 1},
                {"next": 2},
            ]
        )

        probs = module.build_next_item_distribution(train_df, item_count=4)

        self.assertEqual(4, len(probs))
        self.assertAlmostEqual(0.0, float(probs[0]), places=6)
        self.assertAlmostEqual(2.0 / 3.0, float(probs[1]), places=6)
        self.assertAlmostEqual(1.0 / 3.0, float(probs[2]), places=6)
        self.assertAlmostEqual(0.0, float(probs[3]), places=6)

    def test_build_text_utility_report_writes_artifacts_and_uses_train_split_only(self) -> None:
        module = load_script_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            datasets = {
                "ML1M": root / "ML1M",
                "Steam": root / "Steam",
                "Beauty": root / "Beauty",
                "ATG": root / "ATG",
            }
            for dataset_dir in datasets.values():
                dataset_dir.mkdir()
                write_toy_dataset(dataset_dir)

            output_dir = root / "report"
            report = module.build_text_utility_report(
                dataset_dirs=datasets,
                output_dir=output_dir,
                sample_size=4000,
                negative_count=8,
                seed=7,
            )

            self.assertEqual(4, len(report["datasets"]))
            self.assertTrue((output_dir / "gate0_text_utility_summary.csv").exists())
            self.assertTrue((output_dir / "gate0_text_utility_coherence_quartiles.csv").exists())
            self.assertTrue((output_dir / "gate0_text_utility_report.json").exists())
            self.assertTrue((output_dir / "gate0_text_utility_report.md").exists())

            summary_df = pd.read_csv(output_dir / "gate0_text_utility_summary.csv")
            self.assertCountEqual(summary_df["dataset"].tolist(), ["ML1M", "Steam", "Beauty", "ATG"])
            self.assertTrue((summary_df["sampled_row_count"] == 12).all())
            self.assertTrue((summary_df["usable_row_count"] == 12).all())
            self.assertTrue((summary_df["u_ds_popularity"] > 0.60).all())

            first_row = report["datasets"][0]
            expected_phi = max(0.0, min(1.0, (0.70 - float(first_row["u_ds_popularity"])) / 0.10))
            self.assertAlmostEqual(expected_phi, float(first_row["phi_u_ds"]), places=6)
            self.assertIn("bank_hash", first_row)
            self.assertIn("split_hash", first_row)

            quartile_df = pd.read_csv(output_dir / "gate0_text_utility_coherence_quartiles.csv")
            self.assertEqual({"Q1", "Q2", "Q3", "Q4"}, set(quartile_df["coherence_bucket"].unique()))

            markdown_text = (output_dir / "gate0_text_utility_report.md").read_text(encoding="utf-8")
            self.assertIn("does **not** make the Gate 0-v2 pass/fail decision", markdown_text)


if __name__ == "__main__":
    unittest.main()
