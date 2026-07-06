import csv
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
    "build_sprint07_control_report",
    REPO_ROOT / "scripts" / "build_sprint07_control_report.py",
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


def write_manifest(path: Path, repo_root: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "provenance": {"repo_root": str(repo_root.resolve())},
                "phi_u_ds": 0.0,
                "frozen_config": {"ablation_mode": path.parent.parent.name.lower()},
            }
        ),
        encoding="utf-8",
    )


def write_log(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class BuildSprint07ControlReportTests(unittest.TestCase):
    def test_build_rows_compute_status_and_verdicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_root = root / "runs"
            core_root = root / "core"
            official_root = root / "clean"
            official_root.mkdir()

            write_summary(
                core_root / "Beauty" / "best_summary_adaptive.json",
                best_step=100,
                best_metric=0.1,
                val_p5=0.10,
                test_p2=0.20,
                test_p5=0.30,
                test_p10=0.40,
            )
            write_summary(
                run_root / "beauty_proposal_adaptive_mainpath" / "checkpoints-meta" / "Beauty" / "best_summary_proposal_adaptive.json",
                best_step=110,
                best_metric=0.11,
                val_p5=0.15,
                test_p2=0.26,
                test_p5=0.35,
                test_p10=0.45,
            )
            write_manifest(
                run_root / "beauty_proposal_adaptive_mainpath" / "checkpoints-meta" / "Beauty" / "frozen_run_manifest.json",
                official_root,
            )
            write_log(
                run_root / "beauty_proposal_adaptive_mainpath" / "logs" / "beauty_proposal_adaptive_mainpath.log",
                "EARLY_STOP_TRIGGERED step=110 best_step=110 best_metric=0.11\nBEST_RESULT step=110 metric=ndcg10 value=0.11 summary=/tmp/full.json\n",
            )

            write_summary(
                run_root / "beauty_proposal_adaptive_ablation_u_shuffle" / "checkpoints-meta" / "Beauty" / "best_summary_proposal_adaptive.json",
                best_step=120,
                best_metric=0.09,
                val_p5=0.14,
                test_p2=0.21,
                test_p5=0.31,
                test_p10=0.41,
            )
            write_manifest(
                run_root / "beauty_proposal_adaptive_ablation_u_shuffle" / "checkpoints-meta" / "Beauty" / "frozen_run_manifest.json",
                official_root,
            )
            write_log(
                run_root / "beauty_proposal_adaptive_ablation_u_shuffle" / "logs" / "beauty_proposal_adaptive_ablation_u_shuffle.log",
                "EARLY_STOP_TRIGGERED step=120 best_step=120 best_metric=0.09\nBEST_RESULT step=120 metric=ndcg10 value=0.09 summary=/tmp/u.json\n",
            )

            write_summary(
                run_root / "beauty_proposal_adaptive_ablation_text_anchor_only" / "checkpoints-meta" / "Beauty" / "best_summary_proposal_adaptive.json",
                best_step=130,
                best_metric=0.08,
                val_p5=0.13,
                test_p2=0.23,
                test_p5=0.32,
                test_p10=0.42,
            )
            write_manifest(
                run_root / "beauty_proposal_adaptive_ablation_text_anchor_only" / "checkpoints-meta" / "Beauty" / "frozen_run_manifest.json",
                official_root,
            )
            write_log(
                run_root / "beauty_proposal_adaptive_ablation_text_anchor_only" / "logs" / "beauty_proposal_adaptive_ablation_text_anchor_only.log",
                "step: 130, evaluation_loss: 1.0\n",
            )

            write_summary(
                run_root / "beauty_proposal_adaptive_ablation_global_p" / "checkpoints-meta" / "Beauty" / "best_summary_proposal_adaptive.json",
                best_step=140,
                best_metric=0.07,
                val_p5=0.12,
                test_p2=0.205,
                test_p5=0.305,
                test_p10=0.405,
            )
            write_manifest(
                run_root / "beauty_proposal_adaptive_ablation_global_p" / "checkpoints-meta" / "Beauty" / "frozen_run_manifest.json",
                official_root,
            )
            write_log(
                run_root / "beauty_proposal_adaptive_ablation_global_p" / "logs" / "beauty_proposal_adaptive_ablation_global_p.log",
                "EARLY_STOP_TRIGGERED step=140 best_step=140 best_metric=0.07\nBEST_RESULT step=140 metric=ndcg10 value=0.07 summary=/tmp/g.json\n",
            )

            write_summary(
                core_root / "Steam" / "best_summary_adaptive.json",
                best_step=100,
                best_metric=0.1,
                val_p5=0.05,
                test_p2=0.06,
                test_p5=0.07,
                test_p10=0.08,
            )
            for variant, step in (
                ("mainpath", 200),
                ("ablation_u_shuffle", 210),
                ("ablation_text_anchor_only", 220),
                ("ablation_global_p", 230),
            ):
                write_summary(
                    run_root / f"steam_proposal_adaptive_{variant}" / "checkpoints-meta" / "Steam" / "best_summary_proposal_adaptive.json",
                    best_step=step,
                    best_metric=0.1,
                    val_p5=0.09,
                    test_p2=0.10,
                    test_p5=0.11,
                    test_p10=0.12,
                )
                write_manifest(
                    run_root / f"steam_proposal_adaptive_{variant}" / "checkpoints-meta" / "Steam" / "frozen_run_manifest.json",
                    official_root,
                )
                write_log(
                    run_root / f"steam_proposal_adaptive_{variant}" / "logs" / f"steam_proposal_adaptive_{variant}.log",
                    f"EARLY_STOP_TRIGGERED step={step} best_step={step} best_metric=0.1\nBEST_RESULT step={step} metric=ndcg10 value=0.1 summary=/tmp/{variant}.json\n",
                )

            rows = report.build_rows(run_root=run_root, core_root=core_root, official_repo_root=official_root)
            by_key = {(row["dataset"], row["arm"]): row for row in rows}

            self.assertEqual("completed", by_key[("Beauty", "full")]["status"])
            self.assertEqual("degrades", by_key[("Beauty", "u_shuffle")]["u_shuffle_verdict_vs_full"])
            self.assertEqual("-0.05", by_key[("Beauty", "u_shuffle")]["delta_test_p2_vs_full"])
            self.assertEqual("running", by_key[("Beauty", "text_anchor_only")]["status"])
            self.assertEqual("130", by_key[("Beauty", "text_anchor_only")]["last_logged_step"])
            self.assertEqual("", by_key[("Beauty", "text_anchor_only")]["best_step"])
            self.assertEqual("", by_key[("Beauty", "text_anchor_only")]["test_p2_ndcg10"])
            self.assertEqual("", by_key[("Beauty", "text_anchor_only")]["delta_test_p2_vs_full"])
            self.assertEqual("close", by_key[("Beauty", "global_p")]["global_p_core_equivalence"])
            self.assertEqual("0.005", by_key[("Beauty", "global_p")]["delta_test_p2_vs_core"])
            self.assertEqual("0", by_key[("Beauty", "global_p")]["phi_u_ds"])

    def test_invalid_stale_when_manifest_missing_or_wrong_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_root = root / "runs"
            core_root = root / "core"
            official_root = root / "clean"
            other_root = root / "other"
            official_root.mkdir()
            other_root.mkdir()

            write_summary(
                core_root / "Beauty" / "best_summary_adaptive.json",
                best_step=100,
                best_metric=0.1,
                val_p5=0.10,
                test_p2=0.20,
                test_p5=0.30,
                test_p10=0.40,
            )
            write_summary(
                run_root / "beauty_proposal_adaptive_mainpath" / "checkpoints-meta" / "Beauty" / "best_summary_proposal_adaptive.json",
                best_step=110,
                best_metric=0.11,
                val_p5=0.15,
                test_p2=0.26,
                test_p5=0.35,
                test_p10=0.45,
            )
            write_manifest(
                run_root / "beauty_proposal_adaptive_mainpath" / "checkpoints-meta" / "Beauty" / "frozen_run_manifest.json",
                other_root,
            )
            write_log(
                run_root / "beauty_proposal_adaptive_mainpath" / "logs" / "beauty_proposal_adaptive_mainpath.log",
                "EARLY_STOP_TRIGGERED step=110 best_step=110 best_metric=0.11\nBEST_RESULT step=110 metric=ndcg10 value=0.11 summary=/tmp/full.json\n",
            )

            write_summary(
                run_root / "beauty_proposal_adaptive_ablation_u_shuffle" / "checkpoints-meta" / "Beauty" / "best_summary_proposal_adaptive.json",
                best_step=120,
                best_metric=0.09,
                val_p5=0.14,
                test_p2=0.21,
                test_p5=0.31,
                test_p10=0.41,
            )

            rows = report.build_rows(
                run_root=run_root,
                core_root=core_root,
                official_repo_root=official_root,
                datasets=("Beauty",),
            )
            by_arm = {row["arm"]: row for row in rows}
            self.assertEqual("invalid_stale", by_arm["full"]["status"])
            self.assertEqual("", by_arm["full"]["test_p2_ndcg10"])
            self.assertEqual("invalid_stale", by_arm["u_shuffle"]["status"])
            self.assertEqual("", by_arm["u_shuffle"]["test_p2_ndcg10"])
            self.assertEqual("missing_summary", by_arm["text_anchor_only"]["status"])

    def test_write_outputs_include_chinese_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "table.csv"
            md_path = Path(tmpdir) / "report.md"
            rows = [
                {
                    "dataset": "Beauty",
                    "arm": "full",
                    "variant": "mainpath",
                    "run_dir": "/tmp/run",
                    "summary_path": "/tmp/summary.json",
                    "manifest_path": "/tmp/manifest.json",
                    "log_path": "/tmp/full.log",
                    "status": "completed",
                    "manifest_exists": "yes",
                    "manifest_ablation_mode": "none",
                    "phi_u_ds": "0",
                    "log_exists": "yes",
                    "last_logged_step": "100",
                    "best_step": "100",
                    "best_metric": "0.1",
                    "val_p5_ndcg10": "0.12",
                    "test_p2_ndcg10": "0.22",
                    "test_p5_ndcg10": "0.33",
                    "test_p10_ndcg10": "0.44",
                    "delta_test_p2_vs_full": "0",
                    "delta_test_p5_vs_full": "0",
                    "delta_test_p10_vs_full": "0",
                    "delta_test_p2_vs_core": "0.01",
                    "delta_test_p5_vs_core": "0.02",
                    "delta_test_p10_vs_core": "0.03",
                    "u_shuffle_verdict_vs_full": "",
                    "global_p_core_equivalence": "",
                },
                {
                    "dataset": "Beauty",
                    "arm": "u_shuffle",
                    "variant": "ablation_u_shuffle",
                    "run_dir": "/tmp/run2",
                    "summary_path": "/tmp/summary2.json",
                    "manifest_path": "/tmp/manifest2.json",
                    "log_path": "/tmp/u.log",
                    "status": "completed",
                    "manifest_exists": "yes",
                    "manifest_ablation_mode": "u_shuffle",
                    "phi_u_ds": "0",
                    "log_exists": "yes",
                    "last_logged_step": "101",
                    "best_step": "101",
                    "best_metric": "0.09",
                    "val_p5_ndcg10": "0.11",
                    "test_p2_ndcg10": "0.20",
                    "test_p5_ndcg10": "0.30",
                    "test_p10_ndcg10": "0.40",
                    "delta_test_p2_vs_full": "-0.02",
                    "delta_test_p5_vs_full": "-0.03",
                    "delta_test_p10_vs_full": "-0.04",
                    "delta_test_p2_vs_core": "-0.01",
                    "delta_test_p5_vs_core": "0",
                    "delta_test_p10_vs_core": "0.01",
                    "u_shuffle_verdict_vs_full": "degrades",
                    "global_p_core_equivalence": "",
                },
                {
                    "dataset": "Steam",
                    "arm": "full",
                    "variant": "mainpath",
                    "run_dir": "/tmp/run3",
                    "summary_path": "/tmp/summary3.json",
                    "manifest_path": "/tmp/manifest3.json",
                    "log_path": "/tmp/full2.log",
                    "status": "completed",
                    "manifest_exists": "yes",
                    "manifest_ablation_mode": "none",
                    "phi_u_ds": "0",
                    "log_exists": "yes",
                    "last_logged_step": "200",
                    "best_step": "200",
                    "best_metric": "0.08",
                    "val_p5_ndcg10": "0.09",
                    "test_p2_ndcg10": "0.10",
                    "test_p5_ndcg10": "0.11",
                    "test_p10_ndcg10": "0.12",
                    "delta_test_p2_vs_full": "0",
                    "delta_test_p5_vs_full": "0",
                    "delta_test_p10_vs_full": "0",
                    "delta_test_p2_vs_core": "0.02",
                    "delta_test_p5_vs_core": "0.03",
                    "delta_test_p10_vs_core": "0.04",
                    "u_shuffle_verdict_vs_full": "",
                    "global_p_core_equivalence": "",
                },
                {
                    "dataset": "Steam",
                    "arm": "global_p",
                    "variant": "ablation_global_p",
                    "run_dir": "/tmp/run4",
                    "summary_path": "/tmp/summary4.json",
                    "manifest_path": "/tmp/manifest4.json",
                    "log_path": "/tmp/g.log",
                    "status": "completed",
                    "manifest_exists": "yes",
                    "manifest_ablation_mode": "global_p",
                    "phi_u_ds": "0",
                    "log_exists": "yes",
                    "last_logged_step": "201",
                    "best_step": "201",
                    "best_metric": "0.07",
                    "val_p5_ndcg10": "0.08",
                    "test_p2_ndcg10": "0.09",
                    "test_p5_ndcg10": "0.10",
                    "test_p10_ndcg10": "0.11",
                    "delta_test_p2_vs_full": "-0.01",
                    "delta_test_p5_vs_full": "-0.01",
                    "delta_test_p10_vs_full": "-0.01",
                    "delta_test_p2_vs_core": "0.001",
                    "delta_test_p5_vs_core": "0.002",
                    "delta_test_p10_vs_core": "0.003",
                    "u_shuffle_verdict_vs_full": "",
                    "global_p_core_equivalence": "close",
                },
            ]
            report.write_csv(csv_path, rows)
            report.write_markdown(md_path, rows)
            parsed = list(csv.DictReader(csv_path.read_text(encoding="utf-8").splitlines()))
            self.assertEqual(4, len(parsed))
            md_text = md_path.read_text(encoding="utf-8")
            self.assertIn("Chinese Summary", md_text)
            self.assertIn("u_shuffle vs full", md_text)
            self.assertIn("global_p vs core", md_text)
            self.assertIn("phi_u_ds=0", md_text)

    def test_markdown_hides_provisional_metrics_for_non_completed_rows(self) -> None:
        rows = [
            {
                "dataset": "Steam",
                "arm": "full",
                "variant": "mainpath",
                "run_dir": "/tmp/run",
                "summary_path": "/tmp/summary.json",
                "manifest_path": "/tmp/manifest.json",
                "log_path": "/tmp/full.log",
                "status": "completed",
                "manifest_exists": "yes",
                "manifest_ablation_mode": "none",
                "phi_u_ds": "1",
                "log_exists": "yes",
                "last_logged_step": "100",
                "best_step": "100",
                "best_metric": "0.1",
                "val_p5_ndcg10": "0.12",
                "test_p2_ndcg10": "0.22",
                "test_p5_ndcg10": "0.33",
                "test_p10_ndcg10": "0.44",
                "delta_test_p2_vs_full": "0",
                "delta_test_p5_vs_full": "0",
                "delta_test_p10_vs_full": "0",
                "delta_test_p2_vs_core": "0.01",
                "delta_test_p5_vs_core": "0.02",
                "delta_test_p10_vs_core": "0.03",
                "u_shuffle_verdict_vs_full": "",
                "global_p_core_equivalence": "",
            },
            {
                "dataset": "Steam",
                "arm": "text_anchor_only",
                "variant": "ablation_text_anchor_only",
                "run_dir": "/tmp/run2",
                "summary_path": "/tmp/summary2.json",
                "manifest_path": "/tmp/manifest2.json",
                "log_path": "/tmp/t.log",
                "status": "running",
                "manifest_exists": "yes",
                "manifest_ablation_mode": "text_anchor_only",
                "phi_u_ds": "1",
                "log_exists": "yes",
                "last_logged_step": "141000",
                "best_step": "",
                "best_metric": "",
                "val_p5_ndcg10": "",
                "test_p2_ndcg10": "",
                "test_p5_ndcg10": "",
                "test_p10_ndcg10": "",
                "delta_test_p2_vs_full": "",
                "delta_test_p5_vs_full": "",
                "delta_test_p10_vs_full": "",
                "delta_test_p2_vs_core": "",
                "delta_test_p5_vs_core": "",
                "delta_test_p10_vs_core": "",
                "u_shuffle_verdict_vs_full": "",
                "global_p_core_equivalence": "",
            },
        ]
        md_text = report.build_markdown(rows)
        self.assertIn("provisional metrics hidden until completed", md_text)
        self.assertIn("last_logged_step=141000", md_text)


if __name__ == "__main__":
    unittest.main()
