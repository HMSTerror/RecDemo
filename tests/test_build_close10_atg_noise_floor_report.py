import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


report = load_module(
    "build_close10_atg_noise_floor_report",
    REPO_ROOT / "scripts" / "build_close10_atg_noise_floor_report.py",
)


def write_summary(
    path: Path,
    *,
    best_step: int,
    best_metric: float,
    val_p5: float,
    test_p2: float,
    test_p5: float,
    test_p10: float,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "best_step": best_step,
                "best_metric": best_metric,
                "validation": {"p5": {"ndcg": [0.0, 0.0, val_p5]}},
                "test": {
                    "p2": {"ndcg": [0.0, 0.0, test_p2]},
                    "p5": {"ndcg": [0.0, 0.0, test_p5]},
                    "p10": {"ndcg": [0.0, 0.0, test_p10]},
                },
            }
        ),
        encoding="utf-8",
    )


def write_manifest(path: Path, repo_root: Path, seed: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "provenance": {"repo_root": str(repo_root.resolve())},
                "random_seed": seed,
                "frozen_config": {
                    "graph_type": "hybrid",
                    "text_side_enabled": False,
                    "early_stop_metric": "ndcg10",
                    "early_stop_strength": "p5",
                    "write_snapshot_checkpoint": True,
                    "write_best_checkpoint": True,
                },
            }
        ),
        encoding="utf-8",
    )


def write_log(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_gate1_report(path: Path, delta: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "datasets": [
                    {"dataset": "ML1M", "delta_test_p2_ndcg10": -0.015133045070724, "dataset_verdict": "miss"},
                    {"dataset": "ATG", "delta_test_p2_ndcg10": delta, "dataset_verdict": "miss"},
                ]
            }
        ),
        encoding="utf-8",
    )


class BuildClose10AtgNoiseFloorReportTests(unittest.TestCase):
    def test_default_run_root_and_output_dir_target_close10_atg(self) -> None:
        self.assertEqual(
            "/data/Zijian/goal/RecDemoRuns/close10_atg_noise_floor",
            str(report.DEFAULT_RUN_ROOT).replace("\\", "/"),
        )
        self.assertIn("close10-atg-noise-floor", str(report.DEFAULT_OUTPUT_DIR).replace("\\", "/"))
        self.assertEqual((100, 101), report.DEFAULT_SEEDS)

    def test_path_helpers_use_atg_dimension(self) -> None:
        run_root = Path("/tmp/close10")
        self.assertTrue(str(report.run_dir_for(run_root, 100)).endswith("atg_core_seed100"))
        self.assertIn("checkpoints-meta/ATG", str(report.summary_path_for(run_root, 100)).replace("\\", "/"))
        self.assertTrue(str(report.log_path_for(run_root, 100)).replace("\\", "/").endswith("logs/atg_core_seed100.log"))

    def test_read_gate1_picks_atg_row_not_ml1m(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            gate1_report = Path(tmpdir) / "gate1.json"
            write_gate1_report(gate1_report, delta=-0.011410105406507)
            context = report.read_gate1_atg_delta(gate1_report)
            self.assertEqual("ATG", context["dataset"] if "dataset" in context else "ATG")
            self.assertAlmostEqual(-0.011410105406507, context["delta_test_p2_ndcg10"])
            self.assertAlmostEqual(0.011410105406507, context["abs_delta_test_p2_ndcg10"])

    def test_within_noise_candidate_when_floor_covers_atg_delta(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_root = root / "runs"
            official_root = root / "clean"
            gate1_report = root / "gate1.json"
            official_root.mkdir()
            # ATG gate1 delta = -0.01141; make the two-seed floor larger than that.
            write_gate1_report(gate1_report, delta=-0.011410105406507)

            for seed, test_p2 in ((100, 0.0419), (101, 0.0250)):
                write_summary(
                    run_root / f"atg_core_seed{seed}" / "checkpoints-meta" / "ATG" / "best_summary_hybrid.json",
                    best_step=30000 + seed,
                    best_metric=0.031,
                    val_p5=0.03,
                    test_p2=test_p2,
                    test_p5=test_p2 + 0.001,
                    test_p10=test_p2 + 0.002,
                )
                write_manifest(
                    run_root / f"atg_core_seed{seed}" / "checkpoints-meta" / "ATG" / "frozen_run_manifest.json",
                    official_root,
                    seed,
                )
                write_log(
                    run_root / f"atg_core_seed{seed}" / "logs" / f"atg_core_seed{seed}.log",
                    f"EARLY_STOP_TRIGGERED step={30000 + seed}\nFINISH seed={seed}\n",
                )

            rows = report.build_rows(run_root=run_root, official_repo_root=official_root)
            pairwise = report.build_pairwise_deltas(rows)
            noise_floor_summary = report.build_noise_floor_summary(rows, pairwise)
            gate1_context = report.read_gate1_atg_delta(gate1_report)
            decision_line = report.build_decision_line(noise_floor_summary, gate1_context)

            self.assertEqual(2, len(rows))
            self.assertTrue(all(row["status"] == "completed" for row in rows))
            self.assertAlmostEqual(0.0169, noise_floor_summary["max_pairwise_abs_delta_test_p2_ndcg10"], places=4)
            self.assertEqual("within_noise_candidate", decision_line["decision_line"])
            self.assertIn("atg", decision_line["reason"])

    def test_outside_noise_red_flag_when_floor_below_atg_delta(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_root = root / "runs"
            official_root = root / "clean"
            gate1_report = root / "gate1.json"
            official_root.mkdir()
            write_gate1_report(gate1_report, delta=-0.011410105406507)

            for seed, test_p2 in ((100, 0.0419), (101, 0.0410)):
                write_summary(
                    run_root / f"atg_core_seed{seed}" / "checkpoints-meta" / "ATG" / "best_summary_hybrid.json",
                    best_step=30000 + seed,
                    best_metric=0.031,
                    val_p5=0.03,
                    test_p2=test_p2,
                    test_p5=test_p2 + 0.001,
                    test_p10=test_p2 + 0.002,
                )
                write_manifest(
                    run_root / f"atg_core_seed{seed}" / "checkpoints-meta" / "ATG" / "frozen_run_manifest.json",
                    official_root,
                    seed,
                )
                write_log(
                    run_root / f"atg_core_seed{seed}" / "logs" / f"atg_core_seed{seed}.log",
                    f"EARLY_STOP_TRIGGERED step={30000 + seed}\nFINISH seed={seed}\n",
                )

            rows = report.build_rows(run_root=run_root, official_repo_root=official_root)
            pairwise = report.build_pairwise_deltas(rows)
            noise_floor_summary = report.build_noise_floor_summary(rows, pairwise)
            gate1_context = report.read_gate1_atg_delta(gate1_report)
            decision_line = report.build_decision_line(noise_floor_summary, gate1_context)

            self.assertAlmostEqual(0.0009, noise_floor_summary["max_pairwise_abs_delta_test_p2_ndcg10"], places=4)
            self.assertEqual("outside_noise_red_flag", decision_line["decision_line"])

    def test_running_status_when_no_completion_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_root = root / "runs"
            official_root = root / "clean"
            official_root.mkdir()

            write_summary(
                run_root / "atg_core_seed100" / "checkpoints-meta" / "ATG" / "best_summary_hybrid.json",
                best_step=20000,
                best_metric=0.031,
                val_p5=0.03,
                test_p2=0.041,
                test_p5=0.042,
                test_p10=0.043,
            )
            write_manifest(
                run_root / "atg_core_seed100" / "checkpoints-meta" / "ATG" / "frozen_run_manifest.json",
                official_root,
                100,
            )
            write_log(
                run_root / "atg_core_seed100" / "logs" / "atg_core_seed100.log",
                "step: 20000, evaluation_loss: 1.0\n",
            )

            rows = report.build_rows(run_root=run_root, official_repo_root=official_root, seeds=(100,))
            self.assertEqual("running", rows[0]["status"])
            self.assertEqual("", rows[0]["test_p2_ndcg10"])
            self.assertEqual("20000", rows[0]["last_logged_step"])

    def test_markdown_titles_are_atg(self) -> None:
        markdown = report.build_markdown(
            rows=[],
            pairwise=[],
            noise_floor_summary={
                "completed_seed_count": 0,
                "expected_seed_count": 2,
                "max_pairwise_abs_delta_test_p2_ndcg10": None,
                "max_pairwise_abs_delta_test_p5_ndcg10": None,
                "max_pairwise_abs_delta_test_p10_ndcg10": None,
            },
            gate1_context={},
            decision_line={"decision_line": "", "reason": "insufficient_data"},
            official_repo_root=Path("/tmp/clean"),
        )
        self.assertIn("CLOSE-10 ATG", markdown)


if __name__ == "__main__":
    unittest.main()
