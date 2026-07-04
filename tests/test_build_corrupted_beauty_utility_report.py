import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd
import torch


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script_module():
    script_path = REPO_ROOT / "scripts" / "build_corrupted_beauty_utility_report.py"
    spec = importlib.util.spec_from_file_location("build_corrupted_beauty_utility_report", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_text_bank(path: Path) -> None:
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
    ).to_csv(path, index=False)


def write_embedding_payload(path: Path, rows: list[list[float]]) -> None:
    torch.save(
        {
            "item_ids": [0, 1, 2],
            "embeddings": torch.tensor(rows, dtype=torch.float32),
        },
        path,
    )


def write_toy_beauty_dataset(dataset_dir: Path) -> None:
    write_text_bank(dataset_dir / "text_bank.csv")
    write_embedding_payload(
        dataset_dir / "sentence_t5_xl_item_emb.pt",
        [
            [1.0, 0.0],
            [1.0, 0.0],
            [-1.0, 0.0],
        ],
    )
    train_rows = ([{"seq": [0, 0], "len_seq": 2, "next": 1}] * 6) + ([{"seq": [2, 2], "len_seq": 2, "next": 0}] * 6)
    pd.DataFrame(train_rows).to_pickle(dataset_dir / "train_data.df")


def write_corrupted_variant(corruption_dir: Path, variant_tag: str) -> None:
    write_text_bank(corruption_dir / f"{variant_tag}_text_bank.csv")
    write_embedding_payload(
        corruption_dir / f"{variant_tag}_sentence_t5_xl_item_emb.pt",
        [
            [1.0, 0.0],
            [-1.0, 0.0],
            [-1.0, 0.0],
        ],
    )


class BuildCorruptedBeautyUtilityReportTests(unittest.TestCase):
    def test_select_variants_prefers_existing_canonical_ladder(self) -> None:
        module = load_script_module()
        root = Path(tempfile.gettempdir())
        discovered = {
            "token_dropout50": module.VariantPaths(
                variant_tag="token_dropout50",
                text_bank_path=root / "token_dropout50_text_bank.csv",
                embeddings_path=root / "token_dropout50_sentence_t5_xl_item_emb.pt",
            ),
            "token_dropout41246337890625": module.VariantPaths(
                variant_tag="token_dropout41246337890625",
                text_bank_path=root / "token_dropout41246337890625_text_bank.csv",
                embeddings_path=root / "token_dropout41246337890625_sentence_t5_xl_item_emb.pt",
            ),
            "token_dropout": module.VariantPaths(
                variant_tag="token_dropout",
                text_bank_path=root / "token_dropout_text_bank.csv",
                embeddings_path=root / "token_dropout_sentence_t5_xl_item_emb.pt",
            ),
        }

        selected, mode = module._select_variants(discovered, explicit_variants=[], include_all_discovered=False)

        self.assertEqual("canonical_existing", mode)
        self.assertEqual(["token_dropout", "token_dropout50"], [variant.variant_tag for variant in selected])

    def test_build_report_writes_artifacts_and_marks_result_observational(self) -> None:
        module = load_script_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            beauty_dataset_dir = root / "Beauty"
            corruption_dir = root / "beauty_corruptions"
            output_dir = root / "report"
            beauty_dataset_dir.mkdir()
            corruption_dir.mkdir()

            write_toy_beauty_dataset(beauty_dataset_dir)
            write_corrupted_variant(corruption_dir, "token_dropout")
            write_corrupted_variant(corruption_dir, "token_dropout50")
            write_corrupted_variant(corruption_dir, "token_dropout41246337890625")

            clean_summary_csv = root / "gate0_text_utility_summary.csv"
            pd.DataFrame(
                [
                    {
                        "dataset": "Beauty",
                        "dataset_dir": str(beauty_dataset_dir),
                        "train_row_count": 12,
                        "sampled_row_count": 12,
                        "usable_row_count": 12,
                        "skipped_row_count": 0,
                        "negative_count": 100,
                        "history_length_mean": 2.0,
                        "history_length_median": 2.0,
                        "coherence_mean": 0.9,
                        "coherence_median": 0.9,
                        "u_ds_popularity": 0.7124275,
                        "u_ds_uniform": 0.71720375,
                        "phi_u_ds": 0.0,
                        "bank_hash": "clean-bank-hash",
                        "split_hash": "clean-split-hash",
                    }
                ]
            ).to_csv(clean_summary_csv, index=False)

            report = module.build_corrupted_beauty_utility_report(
                beauty_dataset_dir=beauty_dataset_dir,
                corruption_dir=corruption_dir,
                clean_summary_csv=clean_summary_csv,
                output_dir=output_dir,
                sample_size=12,
                negative_count=4,
                seed=7,
            )

            self.assertEqual("canonical_existing", report["protocol"]["variant_selection_mode"])
            self.assertTrue((output_dir / "beauty_corrupted_u_ds_phi_summary.csv").exists())
            self.assertTrue((output_dir / "beauty_corrupted_u_ds_phi_report.json").exists())
            self.assertTrue((output_dir / "beauty_corrupted_u_ds_phi_report.md").exists())

            summary_df = pd.read_csv(output_dir / "beauty_corrupted_u_ds_phi_summary.csv")
            self.assertEqual(["clean", "token_dropout", "token_dropout50"], summary_df["variant_tag"].tolist())
            self.assertEqual([0.0, 0.3, 0.5], summary_df["dropout_rate"].tolist())
            self.assertTrue((summary_df.loc[summary_df["level_kind"] == "corrupted", "u_ds_popularity"] <= 0.7124275).all())
            self.assertTrue((summary_df.loc[summary_df["level_kind"] == "corrupted", "phi_u_ds"] > 0.0).all())

            self.assertEqual(2, report["observation"]["phi_nonzero_variant_count"])
            self.assertTrue(report["observation"]["all_corrupted_u_ds_le_clean"])
            self.assertTrue(report["observation"]["all_corrupted_phi_ge_clean"])
            self.assertIsNone(report["observation"]["spearman_dropout_rate_vs_phi"])

            markdown_text = (output_dir / "beauty_corrupted_u_ds_phi_report.md").read_text(encoding="utf-8")
            self.assertIn("observational evidence only", markdown_text)
            self.assertIn(str(clean_summary_csv.resolve()), markdown_text)

            json_text = (output_dir / "beauty_corrupted_u_ds_phi_report.json").read_text(encoding="utf-8")
            self.assertNotIn("NaN", json_text)

    def test_observation_summary_reports_zero_phi_response_honestly(self) -> None:
        module = load_script_module()

        observation = module._observation_summary(
            {"u_ds_popularity": 0.7124275, "phi_u_ds": 0.0},
            [
                {"variant_tag": "token_dropout", "dropout_rate": 0.3, "u_ds_popularity": 0.7132, "phi_u_ds": 0.0},
                {"variant_tag": "token_dropout50", "dropout_rate": 0.5, "u_ds_popularity": 0.704, "phi_u_ds": 0.0},
            ],
        )

        self.assertEqual(0, observation["phi_nonzero_variant_count"])
        self.assertIn("stays at 0", observation["direction_note"])
        self.assertIn("never opens", observation["direction_note"])


if __name__ == "__main__":
    unittest.main()
