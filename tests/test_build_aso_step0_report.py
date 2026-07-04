import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module():
    script_path = REPO_ROOT / "scripts" / "build_aso_step0_report.py"
    spec = importlib.util.spec_from_file_location("build_aso_step0_report", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class BuildASOStep0ReportTests(unittest.TestCase):
    def test_phi_zero_records_no_run(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp_dir:
            utility_report = Path(tmp_dir) / "gate0_text_utility_report.json"
            utility_report.write_text(
                json.dumps(
                    {
                        "protocol": {"sample_size": 4000, "negative_count": 100, "seed": 7},
                        "datasets": [
                            {
                                "dataset": "ASO",
                                "u_ds_popularity": 0.75,
                                "phi_u_ds": 0.0,
                                "bank_hash": "bank",
                                "split_hash": "split",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            report = module.build_report(utility_report, "ASO")

        self.assertEqual("phi_eq_0_parity", report["prediction_tier"])
        self.assertEqual("|delta_test_p2_ndcg10| < 0.01", report["pre_registered_prediction"])
        self.assertEqual("no_run_record_only", report["run_decision"])

    def test_phi_positive_opens_validation_run(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp_dir:
            utility_report = Path(tmp_dir) / "gate0_text_utility_report.json"
            utility_report.write_text(
                json.dumps(
                    {
                        "protocol": {"sample_size": 4000, "negative_count": 100, "seed": 7},
                        "datasets": [
                            {
                                "dataset": "ASO",
                                "u_ds_popularity": 0.62,
                                "phi_u_ds": 0.8,
                                "bank_hash": "bank",
                                "split_hash": "split",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            report = module.build_report(utility_report, "ASO")

        self.assertEqual("phi_ge_0p5_positive", report["prediction_tier"])
        self.assertEqual("delta_test_p2_ndcg10 > 0", report["pre_registered_prediction"])
        self.assertEqual("launch_validation_run", report["run_decision"])


if __name__ == "__main__":
    unittest.main()
