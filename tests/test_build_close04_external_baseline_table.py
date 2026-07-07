import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "build_close04_external_baseline_table.py"


def load_module():
    spec = importlib.util.spec_from_file_location("build_close04_external_baseline_table", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class BuildClose04ExternalBaselineTableTests(unittest.TestCase):
    def test_script_module_exists(self) -> None:
        self.assertTrue(MODULE_PATH.exists(), f"missing script: {MODULE_PATH}")

    def test_build_rows_reads_diffurec_and_host_summaries(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            core_root = root / "core"
            ours_run_root = root / "ours"
            baseline_root = root / "baseline"

            write_json(
                core_root / "ML1M" / "best_summary_hybrid.json",
                {
                    "test": {
                        "p2": {
                            "hr": [0.0, 0.0, 0.15, 0.22],
                            "ndcg": [0.0, 0.0, 0.08, 0.11],
                        }
                    }
                },
            )
            write_json(
                ours_run_root
                / "ml1m_proposal_adaptive_mainpath"
                / "checkpoints-meta"
                / "ML1M"
                / "best_summary_proposal_adaptive.json",
                {
                    "test": {
                        "p2": {
                            "hr": [0.0, 0.0, 0.18, 0.25],
                            "ndcg": [0.0, 0.0, 0.095, 0.12],
                        }
                    }
                },
            )
            write_json(
                baseline_root
                / "ml1m_diffurec_seed100"
                / "checkpoints-meta"
                / "ML1M"
                / "best_summary_diffurec.json",
                {
                    "method": "DiffuRec",
                    "dataset": "ML1M",
                    "selector": {"metric": "NDCG@10", "best_epoch": 40, "best_metric_value": 0.09},
                    "validation": {"HR@10": 0.17, "NDCG@10": 0.09},
                    "test": {"HR@10": 0.19, "NDCG@10": 0.1},
                },
            )

            rows = module.build_rows(
                core_root=core_root,
                ours_run_root=ours_run_root,
                baseline_run_root=baseline_root,
                datasets=("ML1M",),
                baseline_method="DiffuRec",
                baseline_seed=100,
            )

            self.assertEqual(1, len(rows))
            row = rows[0]
            self.assertEqual("ML1M", row["dataset"])
            self.assertEqual("DiffuRec", row["baseline_method"])
            self.assertEqual("NDCG@10", row["baseline_selector_metric"])
            self.assertEqual("40", row["baseline_best_epoch"])
            self.assertEqual("0.19", row["baseline_test_hr10"])
            self.assertEqual("0.1", row["baseline_test_ndcg10"])
            self.assertEqual("0.15", row["host_test_hr10"])
            self.assertEqual("0.08", row["host_test_ndcg10"])
            self.assertEqual("0.18", row["ours_test_hr10"])
            self.assertEqual("0.095", row["ours_test_ndcg10"])
            self.assertEqual("0.02", row["delta_baseline_vs_host_ndcg10"])
            self.assertEqual("0.005", row["delta_baseline_vs_ours_ndcg10"])


if __name__ == "__main__":
    unittest.main()
