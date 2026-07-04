import csv
import json
import tempfile
import unittest
from pathlib import Path
import importlib.util


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


compare = load_module(
    "compare_text_side_main_table_to_core",
    REPO_ROOT / "scripts" / "compare_text_side_main_table_to_core.py",
)


def make_summary(best_step: int, best_metric: float, val_p2: float, test_p2: float, test_p5: float, test_p10: float) -> dict:
    def block(value: float) -> dict[str, list[float]]:
        return {"ndcg": [0.0, 0.0, value, value]}

    return {
        "best_step": best_step,
        "best_metric": best_metric,
        "validation": {"p2": block(val_p2)},
        "test": {"p2": block(test_p2), "p5": block(test_p5), "p10": block(test_p10)},
    }


class CompareTextSideMainTableToCoreTests(unittest.TestCase):
    def test_build_rows_computes_deltas(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            status_csv = root / "status.csv"
            current_summary = root / "steam_text.json"
            current_log = root / "steam_text.log"
            core_root = root / "core"
            (core_root / "Steam").mkdir(parents=True)
            core_summary = core_root / "Steam" / "best_summary_adaptive.json"

            current_summary.write_text(
                json.dumps(make_summary(3000, 0.02, 0.02, 0.03, 0.04, 0.05)),
                encoding="utf-8",
            )
            current_log.write_text(
                "\n".join(
                    [
                        "step: 4000, evaluation_loss: 1.0",
                        "Generating items at step: 4000",
                        "without personalzation strength",
                        "NDCG@5     NDCG@10    NDCG@20    NDCG@50",
                        "0.001000   0.002000   0.003000   0.004000",
                        "with personalzation strength 2",
                        "NDCG@5     NDCG@10    NDCG@20    NDCG@50",
                        "0.011000   0.022000   0.033000   0.044000",
                        "with personalzation strength 5",
                        "NDCG@5     NDCG@10    NDCG@20    NDCG@50",
                        "0.015000   0.025000   0.035000   0.045000",
                        "with personalzation strength 10",
                        "NDCG@5     NDCG@10    NDCG@20    NDCG@50",
                        "0.016000   0.026000   0.036000   0.046000",
                        "test phase:",
                        "without personalzation strength",
                        "NDCG@5     NDCG@10    NDCG@20    NDCG@50",
                        "0.005000   0.006000   0.007000   0.008000",
                        "with personalzation strength 2",
                        "NDCG@5     NDCG@10    NDCG@20    NDCG@50",
                        "0.020000   0.030000   0.040000   0.050000",
                        "with personalzation strength 5",
                        "NDCG@5     NDCG@10    NDCG@20    NDCG@50",
                        "0.021000   0.031000   0.041000   0.051000",
                        "with personalzation strength 10",
                        "NDCG@5     NDCG@10    NDCG@20    NDCG@50",
                        "0.022000   0.032000   0.042000   0.052000",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            core_summary.write_text(
                json.dumps(make_summary(27000, 0.01, 0.015, 0.02, 0.03, 0.04)),
                encoding="utf-8",
            )

            with status_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["dataset", "status", "summary_path", "log_path", "last_logged_step", "early_stop_wait_counter", "early_stop_wait_patience"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "dataset": "Steam",
                        "status": "running",
                        "summary_path": str(current_summary),
                        "log_path": str(current_log),
                        "last_logged_step": "4000",
                        "early_stop_wait_counter": "2",
                        "early_stop_wait_patience": "5",
                    }
                )

            status_rows = compare.read_status_rows(status_csv)
            rows = compare.build_rows(status_rows, core_root)
            row = rows[0]
            self.assertEqual("Steam", row["dataset"])
            self.assertEqual("0.005", row["delta_val_p2_ndcg10"])
            self.assertEqual("0.01", row["delta_test_p2_ndcg10"])
            self.assertEqual("0.01", row["delta_test_p5_ndcg10"])
            self.assertEqual("4000", row["live_eval_step"])
            self.assertEqual("0.022", row["live_val_p2_ndcg10"])
            self.assertEqual("0.03", row["live_test_p2_ndcg10"])
            self.assertEqual("0.01", row["live_delta_test_p2_ndcg10"])
            self.assertEqual("2", row["early_stop_wait_counter"])
            self.assertEqual("5", row["early_stop_wait_patience"])

    def test_build_rows_adds_manifest_and_spec_prediction_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            core_root = root / "core"
            status_rows = []

            cases = [
                ("Beauty", "best_summary_adaptive.json", 0.025, 0.02, "abs(delta_test_p2_ndcg10) < 0.01", "hit", ""),
                ("ML1M", "best_summary_hybrid.json", 0.011, 0.02, "abs(delta_test_p2_ndcg10) < 0.01", "hit", ""),
                ("ATG", "best_summary_hybrid.json", 0.021, 0.02, "abs(delta_test_p2_ndcg10) < 0.01", "hit", ""),
                ("Steam", "best_summary_adaptive.json", 0.025, 0.02, "delta_test_p2_ndcg10 > 0", "hit", "hit"),
            ]

            for dataset, core_name, current_test_p2, core_test_p2, expected_outcome, prediction_outcome, reference_outcome in cases:
                current_summary = root / f"{dataset.lower()}_current.json"
                current_summary.write_text(
                    json.dumps(make_summary(3000, 0.02, 0.02, current_test_p2, 0.04, 0.05)),
                    encoding="utf-8",
                )
                dataset_core_dir = core_root / dataset
                dataset_core_dir.mkdir(parents=True, exist_ok=True)
                (dataset_core_dir / core_name).write_text(
                    json.dumps(make_summary(27000, 0.01, 0.015, core_test_p2, 0.03, 0.04)),
                    encoding="utf-8",
                )
                manifest_path = root / f"{dataset.lower()}_manifest.json"
                manifest_path.write_text("{}", encoding="utf-8")
                status_rows.append(
                    {
                        "dataset": dataset,
                        "status": "completed",
                        "official_status": "completed",
                        "manifest_path": str(manifest_path),
                        "manifest_exists": "yes",
                        "summary_path": str(current_summary),
                        "log_path": "",
                        "last_logged_step": "",
                        "early_stop_wait_counter": "",
                        "early_stop_wait_patience": "",
                    }
                )

            rows = compare.build_rows(status_rows, core_root)
            by_name = {row["dataset"]: row for row in rows}

            self.assertEqual("completed", by_name["Beauty"]["official_status"])
            self.assertEqual("yes", by_name["Beauty"]["manifest_exists"])
            self.assertEqual("abs(delta_test_p2_ndcg10) < 0.01", by_name["Beauty"]["expected_outcome"])
            self.assertEqual("hit", by_name["Beauty"]["prediction_outcome"])
            self.assertEqual("", by_name["Beauty"]["reference_magnitude_outcome"])

            self.assertEqual("abs(delta_test_p2_ndcg10) < 0.01", by_name["ML1M"]["expected_outcome"])
            self.assertEqual("hit", by_name["ML1M"]["prediction_outcome"])

            self.assertEqual("abs(delta_test_p2_ndcg10) < 0.01", by_name["ATG"]["expected_outcome"])
            self.assertEqual("hit", by_name["ATG"]["prediction_outcome"])

            self.assertEqual("delta_test_p2_ndcg10 > 0", by_name["Steam"]["expected_outcome"])
            self.assertEqual("hit", by_name["Steam"]["prediction_outcome"])
            self.assertEqual("hit", by_name["Steam"]["reference_magnitude_outcome"])

    def test_parse_latest_live_eval_reads_latest_complete_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "ml1m.log"
            log_path.write_text(
                "\n".join(
                    [
                        "step: 1000, evaluation_loss: 1.0",
                        "Generating items at step: 1000",
                        "with personalzation strength 2",
                        "NDCG@5     NDCG@10    NDCG@20    NDCG@50",
                        "0.010000   0.020000   0.030000   0.040000",
                        "test phase:",
                        "with personalzation strength 2",
                        "NDCG@5     NDCG@10    NDCG@20    NDCG@50",
                        "0.011000   0.021000   0.031000   0.041000",
                        "step: 2000, evaluation_loss: 1.0",
                        "Generating items at step: 2000",
                        "with personalzation strength 2",
                        "NDCG@5     NDCG@10    NDCG@20    NDCG@50",
                        "0.012000   0.022000   0.032000   0.042000",
                        "test phase:",
                        "with personalzation strength 2",
                        "NDCG@5     NDCG@10    NDCG@20    NDCG@50",
                        "0.013000   0.023000   0.033000   0.043000",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            parsed = compare.parse_latest_live_eval(log_path)
            self.assertIsNotNone(parsed)
            assert parsed is not None
            self.assertEqual(2000, parsed["step"])
            self.assertEqual(0.022, parsed["validation"]["p2"]["ndcg10"])
            self.assertEqual(0.023, parsed["test"]["p2"]["ndcg10"])

    def test_write_outputs_preserve_headers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "compare.csv"
            md_path = Path(tmpdir) / "compare.md"
            rows = [
                {
                    "dataset": "Steam",
                    "status": "running",
                    "official_status": "running",
                    "manifest_exists": "yes",
                    "current_best_step": "3000",
                    "current_val_p2_ndcg10": "0.02",
                    "core_val_p2_ndcg10": "0.01",
                    "delta_val_p2_ndcg10": "0.01",
                    "current_test_p2_ndcg10": "0.03",
                    "core_test_p2_ndcg10": "0.02",
                    "delta_test_p2_ndcg10": "0.01",
                    "expected_outcome": "delta_test_p2_ndcg10 > 0",
                    "prediction_outcome": "hit",
                    "reference_magnitude_outcome": "hit",
                }
            ]
            compare.write_csv(csv_path, rows)
            compare.write_markdown(md_path, rows)
            parsed = list(csv.DictReader(csv_path.read_text(encoding="utf-8").splitlines()))
            self.assertEqual(["Steam"], [row["dataset"] for row in parsed])
            self.assertIn("Text-side vs core main-table comparison", md_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
