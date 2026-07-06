import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module():
    script_path = REPO_ROOT / "scripts" / "build_sprint05_gate1_report.py"
    spec = importlib.util.spec_from_file_location("build_sprint05_gate1_report", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def write_csv_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_manifest(path: Path, *, dataset: str, repo_root: str = "/data/Zijian/goal/RecDemo_clean_main") -> None:
    payload = {
        "bank_hash": f"bank-{dataset.lower()}",
        "dataset": dataset,
        "dataset_dir": f"/data/datasets/{dataset}",
        "frozen_config": {
            "ablation_mode": "none",
            "agreement_k": 2.0,
            "agreement_weight": 0.45,
            "center_embeddings": False,
            "completeness_weight": 0.15,
            "early_stop_metric": "ndcg10",
            "early_stop_strength": "p5",
            "ess_weight": 0.2,
            "g_max": 0.5,
            "history_reliability_weight": 0.4,
            "injection_mode": "kernel",
            "kernel_version": "v2",
            "max_temperature_scale": 2.0,
            "min_pseudo_mass": 0.05,
            "popularity_mix_power": 1.0,
            "popularity_mix_scale": 1.0,
            "pseudo_mass_power": 1.0,
            "pseudo_mass_scale": 1.0,
            "recency_weight": 0.3,
            "stability_weight": 0.5,
            "temperature": 0.2,
            "write_best_checkpoint": True,
            "write_snapshot_checkpoint": False,
        },
        "null_curve_hash": f"null-{dataset.lower()}",
        "phi_u_ds": 0.0 if dataset in {"ML1M", "Beauty"} else 1.0,
        "provenance": {"repo_root": repo_root},
        "random_seed": 100,
        "run_dir": f"/data/runs/{dataset}",
        "split_hash": f"split-{dataset.lower()}",
        "u_ds_artifact_hash": f"uds-{dataset.lower()}",
        "u_ds_artifact_path": "/data/Zijian/goal/RecDemo/docs/reports/data/2026-07-02-gate0/gate0_text_utility_report.json",
        "u_ds_popularity": 0.75 if dataset == "ML1M" else 0.5,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


class BuildSprint05Gate1ReportTests(unittest.TestCase):
    def test_build_report_marks_gate1_fail_without_diagnostic_and_weak_only(self) -> None:
        module = load_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            status_csv = root / "status.csv"
            compare_csv = root / "compare.csv"
            manifest_paths = {
                "Beauty": root / "beauty_manifest.json",
                "ML1M": root / "ml1m_manifest.json",
                "Steam": root / "steam_manifest.json",
                "ATG": root / "atg_manifest.json",
            }

            for dataset, path in manifest_paths.items():
                write_manifest(path, dataset=dataset)

            write_csv_rows(
                status_csv,
                [
                    {
                        "dataset": "Steam",
                        "status": "completed",
                        "official_status": "completed",
                        "run_dir": "/data/runs/Steam",
                        "summary_path": "/data/runs/Steam/best_summary.json",
                        "summary_exists": "yes",
                        "summary_source": "run_dir",
                        "manifest_path": "/remote/Steam/frozen_run_manifest.json",
                        "manifest_exists": "yes",
                        "best_step": "66000",
                        "best_metric": "0.01663",
                        "log_path": "/data/runs/Steam/run.log",
                        "log_exists": "yes",
                        "last_logged_step": "71000",
                        "early_stop_wait_counter": "5",
                        "early_stop_wait_patience": "5",
                        "queue_launcher": "sprint05_official_steam_gpu0",
                    },
                    {
                        "dataset": "ML1M",
                        "status": "completed",
                        "official_status": "completed",
                        "run_dir": "/data/runs/ML1M",
                        "summary_path": "/data/runs/ML1M/best_summary.json",
                        "summary_exists": "yes",
                        "summary_source": "run_dir",
                        "manifest_path": "/remote/ML1M/frozen_run_manifest.json",
                        "manifest_exists": "yes",
                        "best_step": "405000",
                        "best_metric": "0.09517",
                        "log_path": "/data/runs/ML1M/run.log",
                        "log_exists": "yes",
                        "last_logged_step": "410000",
                        "early_stop_wait_counter": "5",
                        "early_stop_wait_patience": "5",
                        "queue_launcher": "sprint05_official_ml1m_gpu1",
                    },
                    {
                        "dataset": "Beauty",
                        "status": "completed",
                        "official_status": "completed",
                        "run_dir": "/data/runs/Beauty",
                        "summary_path": "/data/runs/Beauty/best_summary.json",
                        "summary_exists": "yes",
                        "summary_source": "run_dir",
                        "manifest_path": "/remote/Beauty/frozen_run_manifest.json",
                        "manifest_exists": "yes",
                        "best_step": "18000",
                        "best_metric": "0.02453",
                        "log_path": "/data/runs/Beauty/run.log",
                        "log_exists": "yes",
                        "last_logged_step": "23000",
                        "early_stop_wait_counter": "5",
                        "early_stop_wait_patience": "5",
                        "queue_launcher": "sprint05_official_beauty_gpu0",
                    },
                    {
                        "dataset": "ATG",
                        "status": "completed",
                        "official_status": "completed",
                        "run_dir": "/data/runs/ATG",
                        "summary_path": "/data/runs/ATG/best_summary.json",
                        "summary_exists": "yes",
                        "summary_source": "run_dir",
                        "manifest_path": "/remote/ATG/frozen_run_manifest.json",
                        "manifest_exists": "yes",
                        "best_step": "30000",
                        "best_metric": "0.02949",
                        "log_path": "/data/runs/ATG/run.log",
                        "log_exists": "yes",
                        "last_logged_step": "35000",
                        "early_stop_wait_counter": "5",
                        "early_stop_wait_patience": "5",
                        "queue_launcher": "sprint05_official_atg_gpu1",
                    },
                ],
            )
            write_csv_rows(
                compare_csv,
                [
                    {
                        "dataset": "Steam",
                        "status": "completed",
                        "official_status": "completed",
                        "manifest_path": "/remote/Steam/frozen_run_manifest.json",
                        "manifest_exists": "yes",
                        "last_logged_step": "71000",
                        "early_stop_wait_counter": "5",
                        "early_stop_wait_patience": "5",
                        "current_summary_path": "/remote/Steam/best_summary.json",
                        "current_best_step": "66000",
                        "current_best_metric": "0.016632993411694566",
                        "current_val_p2_ndcg10": "0.016358867878776",
                        "current_test_p2_ndcg10": "0.014911009456831",
                        "current_test_p5_ndcg10": "0.015140031944749",
                        "current_test_p10_ndcg10": "0.016165704843637",
                        "live_eval_step": "71000",
                        "live_val_p2_ndcg10": "0.016405",
                        "live_test_p2_ndcg10": "0.015172",
                        "live_test_p5_ndcg10": "0.015693",
                        "live_test_p10_ndcg10": "0.01651",
                        "live_delta_val_p2_ndcg10": "0.001764129900751",
                        "live_delta_test_p2_ndcg10": "0.002276192844287",
                        "live_delta_test_p5_ndcg10": "0.002196023355036",
                        "live_delta_test_p10_ndcg10": "0.002133405835026",
                        "core_summary_path": "/remote/core/Steam.json",
                        "core_best_step": "27000",
                        "core_best_metric": "0.01464087009924878",
                        "core_val_p2_ndcg10": "0.014640870099249",
                        "core_test_p2_ndcg10": "0.012895807155713",
                        "core_test_p5_ndcg10": "0.013496976644964",
                        "core_test_p10_ndcg10": "0.014376594164974",
                        "delta_val_p2_ndcg10": "0.001717997779528",
                        "delta_test_p2_ndcg10": "0.001717997779528",
                        "delta_test_p5_ndcg10": "0.001643055299786",
                        "delta_test_p10_ndcg10": "0.001789110678662",
                        "expected_outcome": "delta_test_p2_ndcg10 > 0",
                        "prediction_outcome": "hit",
                        "reference_magnitude_outcome": "miss",
                    },
                    {
                        "dataset": "ML1M",
                        "status": "completed",
                        "official_status": "completed",
                        "manifest_path": "/remote/ML1M/frozen_run_manifest.json",
                        "manifest_exists": "yes",
                        "last_logged_step": "410000",
                        "early_stop_wait_counter": "5",
                        "early_stop_wait_patience": "5",
                        "current_summary_path": "/remote/ML1M/best_summary.json",
                        "current_best_step": "405000",
                        "current_best_metric": "0.09517516100200263",
                        "current_val_p2_ndcg10": "0.080038175971273",
                        "current_test_p2_ndcg10": "0.07588870818712",
                        "current_test_p5_ndcg10": "0.088931624328109",
                        "current_test_p10_ndcg10": "0.095596713146165",
                        "live_eval_step": "410000",
                        "live_val_p2_ndcg10": "0.079879",
                        "live_test_p2_ndcg10": "0.076103",
                        "live_test_p5_ndcg10": "0.089098",
                        "live_test_p10_ndcg10": "0.095672",
                        "live_delta_val_p2_ndcg10": "-0.015962765896199",
                        "live_delta_test_p2_ndcg10": "-0.014918753257844",
                        "live_delta_test_p5_ndcg10": "-0.010825875016794",
                        "live_delta_test_p10_ndcg10": "-0.006498742343752",
                        "core_summary_path": "/remote/core/ML1M.json",
                        "core_best_step": "302000",
                        "core_best_metric": "0.09584176589619875",
                        "core_val_p2_ndcg10": "0.095841765896199",
                        "core_test_p2_ndcg10": "0.091021753257844",
                        "core_test_p5_ndcg10": "0.099923875016794",
                        "core_test_p10_ndcg10": "0.102170742343752",
                        "delta_val_p2_ndcg10": "-0.015803589924925",
                        "delta_test_p2_ndcg10": "-0.015133045070724",
                        "delta_test_p5_ndcg10": "-0.010992250688685",
                        "delta_test_p10_ndcg10": "-0.006574029197588",
                        "expected_outcome": "abs(delta_test_p2_ndcg10) < 0.01",
                        "prediction_outcome": "miss",
                        "reference_magnitude_outcome": "",
                    },
                    {
                        "dataset": "Beauty",
                        "status": "completed",
                        "official_status": "completed",
                        "manifest_path": "/remote/Beauty/frozen_run_manifest.json",
                        "manifest_exists": "yes",
                        "last_logged_step": "23000",
                        "early_stop_wait_counter": "5",
                        "early_stop_wait_patience": "5",
                        "current_summary_path": "/remote/Beauty/best_summary.json",
                        "current_best_step": "18000",
                        "current_best_metric": "0.024532750777767648",
                        "current_val_p2_ndcg10": "0.018545317259075",
                        "current_test_p2_ndcg10": "0.029435971334722",
                        "current_test_p5_ndcg10": "0.042029809097732",
                        "current_test_p10_ndcg10": "0.040298677463239",
                        "live_eval_step": "23000",
                        "live_val_p2_ndcg10": "0.018438",
                        "live_test_p2_ndcg10": "0.029387",
                        "live_test_p5_ndcg10": "0.040189",
                        "live_test_p10_ndcg10": "0.038732",
                        "live_delta_val_p2_ndcg10": "0.000072186351698",
                        "live_delta_test_p2_ndcg10": "-0.003907857803678",
                        "live_delta_test_p5_ndcg10": "-0.001410098719008",
                        "live_delta_test_p10_ndcg10": "-0.001807326822485",
                        "core_summary_path": "/remote/core/Beauty.json",
                        "core_best_step": "20000",
                        "core_best_metric": "0.018365813648302143",
                        "core_val_p2_ndcg10": "0.018365813648302",
                        "core_test_p2_ndcg10": "0.033294857803678",
                        "core_test_p5_ndcg10": "0.041599098719008",
                        "core_test_p10_ndcg10": "0.040539326822485",
                        "delta_val_p2_ndcg10": "0.000179503610773",
                        "delta_test_p2_ndcg10": "-0.003858886468956",
                        "delta_test_p5_ndcg10": "0.000430710378725",
                        "delta_test_p10_ndcg10": "-0.000240649359246",
                        "expected_outcome": "abs(delta_test_p2_ndcg10) < 0.01",
                        "prediction_outcome": "hit",
                        "reference_magnitude_outcome": "",
                    },
                    {
                        "dataset": "ATG",
                        "status": "completed",
                        "official_status": "completed",
                        "manifest_path": "/remote/ATG/frozen_run_manifest.json",
                        "manifest_exists": "yes",
                        "last_logged_step": "35000",
                        "early_stop_wait_counter": "5",
                        "early_stop_wait_patience": "5",
                        "current_summary_path": "/remote/ATG/best_summary.json",
                        "current_best_step": "30000",
                        "current_best_metric": "0.029494931106811513",
                        "current_val_p2_ndcg10": "0.021359428174654",
                        "current_test_p2_ndcg10": "0.03046740161338",
                        "current_test_p5_ndcg10": "0.040614593945725",
                        "current_test_p10_ndcg10": "0.041204882061368",
                        "live_eval_step": "35000",
                        "live_val_p2_ndcg10": "0.021576",
                        "live_test_p2_ndcg10": "0.030931",
                        "live_test_p5_ndcg10": "0.041655",
                        "live_test_p10_ndcg10": "0.041181",
                        "live_delta_val_p2_ndcg10": "-0.009427162221414",
                        "live_delta_test_p2_ndcg10": "-0.010946507019888",
                        "live_delta_test_p5_ndcg10": "-0.001337388063084",
                        "live_delta_test_p10_ndcg10": "-0.002467658540524",
                        "core_summary_path": "/remote/core/ATG.json",
                        "core_best_step": "39000",
                        "core_best_metric": "0.031003162221413583",
                        "core_val_p2_ndcg10": "0.031003162221414",
                        "core_test_p2_ndcg10": "0.041877507019888",
                        "core_test_p5_ndcg10": "0.042992388063084",
                        "core_test_p10_ndcg10": "0.043648658540524",
                        "delta_val_p2_ndcg10": "-0.00964373404676",
                        "delta_test_p2_ndcg10": "-0.011410105406507",
                        "delta_test_p5_ndcg10": "-0.002377794117359",
                        "delta_test_p10_ndcg10": "-0.002443776479156",
                        "expected_outcome": "abs(delta_test_p2_ndcg10) < 0.01",
                        "prediction_outcome": "miss",
                        "reference_magnitude_outcome": "",
                    },
                ],
            )

            report = module.build_report(
                output_dir=root,
                status_csv=status_csv,
                compare_csv=compare_csv,
                status_csv_source="/remote/status.csv",
                compare_csv_source="/remote/compare.csv",
                manifest_paths=manifest_paths,
            )

            self.assertTrue(report["sprint05"]["official_complete"])
            self.assertEqual("fail_no_diagnostic", report["gate1"]["verdict"])
            self.assertFalse(report["gate1"]["diagnostic_allowed"])
            self.assertTrue(report["gate1"]["implementation_red_flag"])
            self.assertFalse(report["gate2_exits"]["strong"]["reachable"])
            self.assertFalse(report["gate2_exits"]["medium"]["reachable"])
            self.assertTrue(report["gate2_exits"]["weak"]["reachable"])
            self.assertEqual("directional_hit_reference_miss", report["datasets"][0]["dataset_verdict"])

            json_path, md_path = module.write_report(report, root)
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            markdown = md_path.read_text(encoding="utf-8")
            self.assertIn("Gate 1 verdict: `fail_no_diagnostic`", markdown)
            self.assertIn("弱出口", markdown)

    def test_manifest_checks_fail_when_clean_root_or_frozen_flags_break(self) -> None:
        module = load_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "bad_manifest.json"
            write_manifest(
                manifest_path,
                dataset="ML1M",
                repo_root="/data/Zijian/goal/RecDemo",
            )
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload["frozen_config"]["write_snapshot_checkpoint"] = True
            manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

            checks = module._manifest_check_rows(module._load_json(manifest_path))
            by_id = {check["id"]: check for check in checks}
            self.assertFalse(by_id["repo_root_clean_main"]["passed"])
            self.assertFalse(by_id["write_snapshot_checkpoint"]["passed"])


if __name__ == "__main__":
    unittest.main()
