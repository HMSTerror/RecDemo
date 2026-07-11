import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scripts.run_sasrec import EVALUATOR_VERSION, SELECTOR_VERSION, canonical_hash, parse_args, train_one


def make_dataset(root: Path, name: str = "Beauty") -> Path:
    dataset = root / name
    dataset.mkdir(parents=True)
    protocol = {
        "dataset": name,
        "protocol_version": "paper_raw_v1",
        "parameters": {"target_sequence_length": 4},
        "counts": {
            "item_num": 8,
            "train_row_count": 8,
            "val_row_count": 4,
            "test_row_count": 4,
        },
    }
    (dataset / "protocol.json").write_text(json.dumps(protocol), encoding="utf-8")
    (dataset / "item_mapping.csv").write_text("row,item\n" + "\n".join(f"{i},i{i}" for i in range(8)) + "\n", encoding="utf-8")
    rows = []
    for i in range(8):
        rows.append({"seq": [8, i % 8, (i + 1) % 8, (i + 2) % 8], "len_seq": 3, "next": (i + 3) % 8})
    pd.DataFrame(rows).to_pickle(dataset / "train_data.df")
    pd.DataFrame(rows[:4]).to_pickle(dataset / "val_data.df")
    pd.DataFrame(rows[4:]).to_pickle(dataset / "test_data.df")
    return dataset


class SasrecAdapterTest(unittest.TestCase):
    def test_startup_probe_does_not_write_training_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = make_dataset(root)
            run_dir = root / "probe"
            args = parse_args([
                "--dataset", "Beauty", "--dataset-dir", str(dataset), "--run-dir", str(run_dir),
                "--seed", "100", "--device", "cpu", "--startup-probe-only",
            ])
            payload = train_one(args)
            self.assertEqual(payload["status"], "STARTUP_PROBE_PASS")
            self.assertTrue((run_dir / "startup_probe.json").exists())
            self.assertFalse((run_dir / "sasrec_best.pt").exists())
            self.assertFalse((run_dir / "best_summary_sasrec.json").exists())

    def test_full_run_selects_from_validation_and_writes_self_hashed_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = make_dataset(root)
            run_dir = root / "run"
            args = parse_args([
                "--dataset", "Beauty", "--dataset-dir", str(dataset), "--run-dir", str(run_dir),
                "--seed", "100", "--device", "cpu", "--epochs", "2", "--batch-size", "4",
                "--eval-batch-size", "4", "--hidden-size", "8", "--num-heads", "2", "--num-layers", "1",
                "--dropout", "0.0", "--early-stop-patience", "2",
            ])
            payload = train_one(args)
            self.assertEqual(payload["method"], "SASRec")
            self.assertEqual(payload["dataset"], "Beauty")
            self.assertEqual(payload["seed"], 100)
            self.assertEqual(payload["evaluator_version"], EVALUATOR_VERSION)
            self.assertEqual(payload["selector_version"], SELECTOR_VERSION)
            self.assertEqual(payload["row_counts"], {"train": 8, "val": 4, "test": 4})
            self.assertTrue((run_dir / "sasrec_best.pt").exists())
            self.assertTrue((run_dir / "best_summary_sasrec.json").exists())
            self.assertTrue((run_dir / "metrics_sasrec.json").exists())
            manifest = json.loads((run_dir / "artifact_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["artifact_sha256"], canonical_hash(manifest))
            summary = json.loads((run_dir / "best_summary_sasrec.json").read_text(encoding="utf-8"))
            self.assertIn("validation", summary)
            self.assertIn("test", summary)
            self.assertIn("validation only", summary["test_disclosure"])


if __name__ == "__main__":
    unittest.main()
