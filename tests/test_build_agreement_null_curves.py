import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd
import torch


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script_module():
    script_path = REPO_ROOT / "scripts" / "build_agreement_null_curves.py"
    spec = importlib.util.spec_from_file_location("build_agreement_null_curves", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class BuildAgreementNullCurvesTests(unittest.TestCase):
    def test_script_builds_byte_stable_length_keyed_artifact_with_bank_hash(self) -> None:
        module = load_script_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_dir = Path(tmpdir)
            pd.DataFrame(
                [
                    {"item_id": 0, "source_id": "a0", "title": "Alpha", "brand": "", "categories": "", "description": "", "text": "Alpha"},
                    {"item_id": 1, "source_id": "a1", "title": "Beta", "brand": "", "categories": "", "description": "", "text": "Beta"},
                    {"item_id": 2, "source_id": "a2", "title": "Gamma", "brand": "", "categories": "", "description": "", "text": "Gamma"},
                ]
            ).to_csv(dataset_dir / "item_metadata.csv", index=False)
            text_bank_path = module.ensure_text_bank(dataset_dir)
            torch.save(
                {
                    "item_ids": [0, 1, 2],
                    "embeddings": torch.tensor(
                        [
                            [1.0, 0.0],
                            [0.9, 0.1],
                            [0.0, 1.0],
                        ],
                        dtype=torch.float32,
                    ),
                    "field_coverage": torch.tensor([1.0, 1.0, 1.0], dtype=torch.float32),
                    "text_bank_path": str(text_bank_path),
                },
                dataset_dir / "sentence_t5_xl_item_emb.pt",
            )
            split_df = pd.DataFrame(
                [
                    {"seq": [0, 3, 3], "len_seq": 1, "next": 1},
                    {"seq": [0, 1, 3], "len_seq": 2, "next": 2},
                ]
            )
            for split_name in ("train_data.df", "val_data.df", "test_data.df"):
                split_df.to_pickle(dataset_dir / split_name)

            output_path = dataset_dir / "agreement_null_curves.json"
            artifact = module.build_null_curve_artifact(
                dataset_dir=dataset_dir,
                embeddings_path=dataset_dir / "sentence_t5_xl_item_emb.pt",
                text_bank_path=text_bank_path,
                output_path=output_path,
                samples_per_length=8,
                seed=7,
            )
            first_bytes = output_path.read_bytes()
            second = module.build_null_curve_artifact(
                dataset_dir=dataset_dir,
                embeddings_path=dataset_dir / "sentence_t5_xl_item_emb.pt",
                text_bank_path=text_bank_path,
                output_path=output_path,
                samples_per_length=8,
                seed=7,
            )
            second_bytes = output_path.read_bytes()

            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(artifact, second)
            self.assertIn("protocol", artifact)
            self.assertIn("bank_hash", artifact["protocol"])
            self.assertEqual(["1", "2"], sorted(artifact["length_bins"].keys()))
            self.assertGreater(artifact["length_bins"]["1"]["sigma"], 0.0)
            self.assertGreater(artifact["length_bins"]["2"]["sigma"], 0.0)


if __name__ == "__main__":
    unittest.main()
