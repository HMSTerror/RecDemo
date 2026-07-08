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
    "build_close02_ml1m_noise_floor_report",
    REPO_ROOT / "scripts" / "build_close02_ml1m_noise_floor_report.py",
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
                    "write_snapshot_checkpoint": False,
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
        json.dumps({"datasets": [{"dataset": "ML1M", "delta_test_p2_ndcg10": delta, "dataset_verdict": "miss"}]}),
        encoding="utf-8",
    )


class BuildClose02Ml1mNoiseFloorReportTests(unittest.TestCase):
    def test_default_official_repo_root_uses_closeout_clean_root(self) -> None:
        self.assertEqual(
            "/data/Zijian/goal/RecDemo_clean_closeout_chain",
            str(report.DEFAULT_OFFICIAL_REPO_ROOT).replace("\\", "/"),
        )

    def test_build_rows_and_decision_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_root = root / "runs"
            official_root = root / "clean"
            gate1_report = root / "gate1.json"
            official_root.mkdir()
            write_gate1_report(gate1_report, delta=-0.015133045070724)

            for seed, test_p2 in ((100, 0.0800), (101, 0.0910), (102, 0.0845)):
                write_summary(
                    run_root / f"ml1m_core_seed{seed}" / "checkpoints-meta" / "ML1M" / "best_summary_hybrid.json",
                    best_step=1000 + seed,
                    best_metric=0.09,
                    val_p5=0.08,
                    test_p2=test_p2,
                    test_p5=test_p2 + 0.01,
                    test_p10=test_p2 + 0.02,
                )
                write_manifest(
                    run_root / f"ml1m_core_seed{seed}" / "checkpoints-meta" / "ML1M" / "frozen_run_manifest.json",
                    official_root,
                    seed,
                )
                write_log(
                    run_root / f"ml1m_core_seed{seed}" / "logs" / f"ml1m_core_seed{seed}.log",
                    f"EARLY_STOP_TRIGGERED step={1000 + seed}\nFINISH seed={seed}\n",
                )

            rows = report.build_rows(run_root=run_root, official_repo_root=official_root)
            pairwise = report.build_pairwise_deltas(rows)
            noise_floor_summary = report.build_noise_floor_summary(rows, pairwise)
            gate1_context = report.read_gate1_ml1m_delta(gate1_report)
            decision_line = report.build_decision_line(noise_floor_summary, gate1_context)

            self.assertEqual(3, len(rows))
            self.assertTrue(all(row["status"] == "completed" for row in rows))
            self.assertEqual("0.011", pairwise[0]["abs_delta_test_p2_ndcg10"])
            self.assertAlmostEqual(0.011, noise_floor_summary["max_pairwise_abs_delta_test_p2_ndcg10"])
            self.assertEqual("outside_noise_red_flag", decision_line["decision_line"])

    def test_running_and_invalid_stale_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_root = root / "runs"
            official_root = root / "clean"
            other_root = root / "other"
            official_root.mkdir()
            other_root.mkdir()

            write_summary(
                run_root / "ml1m_core_seed100" / "checkpoints-meta" / "ML1M" / "best_summary_hybrid.json",
                best_step=1100,
                best_metric=0.09,
                val_p5=0.08,
                test_p2=0.081,
                test_p5=0.091,
                test_p10=0.101,
            )
            write_manifest(
                run_root / "ml1m_core_seed100" / "checkpoints-meta" / "ML1M" / "frozen_run_manifest.json",
                official_root,
                100,
            )
            write_log(
                run_root / "ml1m_core_seed100" / "logs" / "ml1m_core_seed100.log",
                "step: 1100, evaluation_loss: 1.0\n",
            )

            write_summary(
                run_root / "ml1m_core_seed101" / "checkpoints-meta" / "ML1M" / "best_summary_hybrid.json",
                best_step=1200,
                best_metric=0.09,
                val_p5=0.08,
                test_p2=0.082,
                test_p5=0.092,
                test_p10=0.102,
            )
            write_manifest(
                run_root / "ml1m_core_seed101" / "checkpoints-meta" / "ML1M" / "frozen_run_manifest.json",
                other_root,
                101,
            )
            write_log(
                run_root / "ml1m_core_seed101" / "logs" / "ml1m_core_seed101.log",
                "EARLY_STOP_TRIGGERED step=1200\nFINISH seed=101\n",
            )

            rows = report.build_rows(
                run_root=run_root,
                official_repo_root=official_root,
                seeds=(100, 101),
            )
            by_seed = {row["seed"]: row for row in rows}

            self.assertEqual("running", by_seed["100"]["status"])
            self.assertEqual("1100", by_seed["100"]["last_logged_step"])
            self.assertEqual("", by_seed["100"]["best_step"])
            self.assertEqual("", by_seed["100"]["test_p2_ndcg10"])
            self.assertEqual("invalid_stale", by_seed["101"]["status"])
            self.assertEqual(str(other_root.resolve()), by_seed["101"]["repo_root"])
            self.assertEqual("", by_seed["101"]["test_p2_ndcg10"])


if __name__ == "__main__":
    unittest.main()
