import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module():
    script_path = REPO_ROOT / "scripts" / "build_aso_validation_report.py"
    spec = importlib.util.spec_from_file_location("build_aso_validation_report", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def write_summary(path: Path, *, best_metric: float, val_p2: float, test_p2: float, test_p5: float, test_p10: float) -> None:
    payload = {
        "best_step": 3000,
        "best_metric": best_metric,
        "validation": {
            "p2": {"ndcg": [0.0, 0.0, val_p2]},
            "p5": {"ndcg": [0.0, 0.0, best_metric]},
            "p10": {"ndcg": [0.0, 0.0, best_metric]},
        },
        "test": {
            "p2": {"ndcg": [0.0, 0.0, test_p2]},
            "p5": {"ndcg": [0.0, 0.0, test_p5]},
            "p10": {"ndcg": [0.0, 0.0, test_p10]},
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_step0_report(path: Path, *, phi_u_ds: float, prediction_tier: str, prediction: str) -> None:
    payload = {
        "dataset": "ASO",
        "utility_report_path": "/remote/aso_step0_utility.json",
        "u_ds_popularity": 0.5379225,
        "phi_u_ds": phi_u_ds,
        "bank_hash": "bank",
        "split_hash": "split",
        "prediction_tier": prediction_tier,
        "pre_registered_prediction": prediction,
        "run_decision": "launch_validation_run",
        "scientific_role": "pure_out_of_sample_prediction_point",
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_manifest(path: Path, *, phi_u_ds: float, u_ds_popularity: float) -> None:
    payload = {
        "dataset": "ASO",
        "dataset_dir": "/remote/dataset/ASO",
        "run_dir": "/remote/run/ASO",
        "random_seed": 100,
        "bank_hash": "bank",
        "split_hash": "split",
        "null_curve_hash": "null",
        "u_ds_artifact_path": "/remote/aso_step0_utility.json",
        "u_ds_artifact_hash": "utility",
        "u_ds_popularity": u_ds_popularity,
        "phi_u_ds": phi_u_ds,
        "frozen_config": {
            "write_snapshot_checkpoint": False,
            "write_best_checkpoint": True,
            "early_stop_metric": "ndcg10",
            "early_stop_strength": "p5",
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


class BuildASOValidationReportTests(unittest.TestCase):
    def test_positive_tier_negative_delta_is_recorded_as_miss(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            step0 = root / "aso_step0_report.json"
            core = root / "core.json"
            run = root / "run.json"
            manifest = root / "manifest.json"

            write_step0_report(
                step0,
                phi_u_ds=1.0,
                prediction_tier="phi_ge_0p5_positive",
                prediction="delta_test_p2_ndcg10 > 0",
            )
            write_summary(
                core,
                best_metric=0.0477,
                val_p2=0.0477,
                test_p2=0.0373,
                test_p5=0.0352,
                test_p10=0.0331,
            )
            write_summary(
                run,
                best_metric=0.0355,
                val_p2=0.0352,
                test_p2=0.0265,
                test_p5=0.0267,
                test_p10=0.0258,
            )
            write_manifest(manifest, phi_u_ds=1.0, u_ds_popularity=0.5379225)

            report = module.build_report(
                step0_report_path=step0,
                core_summary_path=core,
                run_summary_path=run,
                run_manifest_path=manifest,
                core_summary_source="/remote/core.json",
                run_summary_source="/remote/run.json",
                run_manifest_source="/remote/manifest.json",
            )

        self.assertTrue(report["launch_checks_pass"])
        self.assertEqual("miss", report["prediction_outcome"])
        self.assertFalse(report["prediction_hit"])
        self.assertLess(report["actual_outcome"]["delta_test_p2_ndcg10"], 0.0)

    def test_positive_tier_positive_delta_is_recorded_as_hit(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            step0 = root / "aso_step0_report.json"
            core = root / "core.json"
            run = root / "run.json"
            manifest = root / "manifest.json"

            write_step0_report(
                step0,
                phi_u_ds=0.9,
                prediction_tier="phi_ge_0p5_positive",
                prediction="delta_test_p2_ndcg10 > 0",
            )
            write_summary(
                core,
                best_metric=0.0300,
                val_p2=0.0300,
                test_p2=0.0200,
                test_p5=0.0190,
                test_p10=0.0180,
            )
            write_summary(
                run,
                best_metric=0.0330,
                val_p2=0.0330,
                test_p2=0.0240,
                test_p5=0.0210,
                test_p10=0.0200,
            )
            write_manifest(manifest, phi_u_ds=0.9, u_ds_popularity=0.5379225)

            report = module.build_report(
                step0_report_path=step0,
                core_summary_path=core,
                run_summary_path=run,
                run_manifest_path=manifest,
                core_summary_source="/remote/core.json",
                run_summary_source="/remote/run.json",
                run_manifest_source="/remote/manifest.json",
            )

        self.assertTrue(report["launch_checks_pass"])
        self.assertEqual("hit", report["prediction_outcome"])
        self.assertTrue(report["prediction_hit"])
        self.assertGreater(report["actual_outcome"]["delta_test_p2_ndcg10"], 0.0)


if __name__ == "__main__":
    unittest.main()
