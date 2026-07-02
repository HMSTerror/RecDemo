import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd
import torch


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script_module():
    script_path = REPO_ROOT / "scripts" / "build_gate0_calibration_repair_audit.py"
    spec = importlib.util.spec_from_file_location("build_gate0_calibration_repair_audit", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def synthetic_component(
    *,
    dataset: str,
    residual: float,
    sigma: float,
    baseline_u_tilde: float,
    user_count: int = 3,
) -> dict[str, object]:
    residual_tensor = torch.full((user_count,), residual, dtype=torch.float32)
    sigma_tensor = torch.full((user_count,), sigma, dtype=torch.float32)
    return {
        "dataset": dataset,
        "dataset_dir": f"/tmp/{dataset}",
        "user_count": user_count,
        "item_count": 2,
        "split_counts": {"train": 1, "val": 1, "test": 1},
        "bank_hash": f"{dataset}-hash",
        "baseline_median_residual": residual,
        "baseline_median_sigma_null": sigma,
        "baseline_median_u_tilde": baseline_u_tilde,
        "baseline_median_g": min(max(baseline_u_tilde, 0.0), 1.0) * 0.5,
        "residual": residual_tensor,
        "sigma": sigma_tensor,
    }


class BuildGate0CalibrationRepairAuditTests(unittest.TestCase):
    def test_evaluate_candidate_row_can_reduce_ml1m_without_flipping_order(self) -> None:
        module = load_script_module()
        components = {
            "ML1M": synthetic_component(dataset="ML1M", residual=0.011, sigma=0.0040, baseline_u_tilde=1.375),
            "Steam": synthetic_component(dataset="Steam", residual=0.002, sigma=0.0075, baseline_u_tilde=0.133333),
            "Beauty": synthetic_component(dataset="Beauty", residual=0.007, sigma=0.0050, baseline_u_tilde=0.700000),
        }

        row = module._evaluate_candidate_row(
            dataset_components=components,
            agreement_k=2.0,
            sigma_scale=1.0,
            sigma_floor=0.0050,
            g_max=0.5,
            baseline_k=2.0,
        )

        self.assertEqual("sigma_floor", row["family"])
        self.assertLess(float(row["ml1m_median_u_tilde"]), 1.375)
        self.assertFalse(row["gate0_pass"])
        self.assertLess(float(row["steam_order_margin"]), 0.0)

    def test_build_decision_can_detect_passing_candidate(self) -> None:
        module = load_script_module()
        components = {
            "ML1M": synthetic_component(dataset="ML1M", residual=0.11, sigma=0.10, baseline_u_tilde=0.55),
            "Steam": synthetic_component(dataset="Steam", residual=0.16, sigma=0.10, baseline_u_tilde=0.80),
            "Beauty": synthetic_component(dataset="Beauty", residual=0.14, sigma=0.10, baseline_u_tilde=0.70),
            "ATG": synthetic_component(dataset="ATG", residual=0.15, sigma=0.10, baseline_u_tilde=0.75),
        }
        candidate_rows = [
            module._evaluate_candidate_row(
                dataset_components=components,
                agreement_k=2.0,
                sigma_scale=1.0,
                sigma_floor=0.0,
                g_max=0.5,
                baseline_k=2.0,
            ),
            module._evaluate_candidate_row(
                dataset_components=components,
                agreement_k=2.5,
                sigma_scale=1.0,
                sigma_floor=0.0,
                g_max=0.5,
                baseline_k=2.0,
            ),
        ]

        decision = module._build_decision(
            gate0_report={"gate0_verdict": "fail", "gate0_reasons": ["baseline failed"]},
            dataset_components=components,
            candidate_rows=candidate_rows,
        )

        self.assertEqual("implement_best_repair_and_rerun_gate0", decision["recommended_next_path"])
        self.assertEqual(1, decision["passing_candidate_count"])
        self.assertEqual("k2.5_scale1_floor0", decision["best_passing_candidate"]["candidate_id"])

    def test_build_audit_writes_artifacts_and_reports_no_global_pass(self) -> None:
        module = load_script_module()
        synthetic_components = {
            "ML1M": synthetic_component(dataset="ML1M", residual=0.011, sigma=0.0040, baseline_u_tilde=1.375),
            "Steam": synthetic_component(dataset="Steam", residual=0.002, sigma=0.0075, baseline_u_tilde=0.133333),
            "Beauty": synthetic_component(dataset="Beauty", residual=0.007, sigma=0.0050, baseline_u_tilde=0.700000),
            "ATG": synthetic_component(dataset="ATG", residual=0.006, sigma=0.0045, baseline_u_tilde=0.666667),
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            output_dir = root / "report"
            output_dir.mkdir()
            gate0_report = {
                "gate0_verdict": "fail",
                "gate0_reasons": [
                    "|median_u_tilde(ML1M)|=1.375000 exceeds 0.50",
                    "median_u_tilde(Steam)=0.133333 is not greater than ML1M=1.375000",
                ],
            }
            gate0_report_json = output_dir / "gate0_u_tilde_report.json"
            gate0_report_json.write_text(json.dumps(gate0_report, indent=2, sort_keys=True), encoding="utf-8")

            dataset_dirs = {name: root / name for name in synthetic_components}
            for path in dataset_dirs.values():
                path.mkdir()

            def fake_collect(**kwargs):
                return synthetic_components[kwargs["dataset_name"]]

            with mock.patch.object(module, "_collect_dataset_components", side_effect=fake_collect):
                report = module.build_gate0_calibration_repair_audit(
                    dataset_dirs=dataset_dirs,
                    output_dir=output_dir,
                    gate0_report_json=gate0_report_json,
                    k_values=(2.0, 2.5, 3.0),
                    sigma_scales=(1.0, 1.5),
                    sigma_floors=(0.0, 0.0050),
                )

            self.assertEqual("blocked", report["sprint05_status"])
            self.assertEqual("downgrade_claim_or_design_deeper_repair", report["recommended_next_path"])
            self.assertEqual(0, report["passing_candidate_count"])

            candidates_df = pd.read_csv(output_dir / "gate0_calibration_repair_candidates.csv")
            self.assertGreaterEqual(len(candidates_df), 1)
            self.assertTrue((output_dir / "gate0_calibration_repair_audit.json").exists())
            self.assertTrue((output_dir / "gate0_calibration_repair_audit.md").exists())

            markdown_text = (output_dir / "gate0_calibration_repair_audit.md").read_text(encoding="utf-8")
            self.assertIn("Gate0 Calibration Repair Audit", markdown_text)
            self.assertIn("Passing candidate count: `0`", markdown_text)


if __name__ == "__main__":
    unittest.main()
