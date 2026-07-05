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


snapshot = load_module(
    "capture_text_side_main_table_snapshot",
    REPO_ROOT / "scripts" / "capture_text_side_main_table_snapshot.py",
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


class CaptureTextSideMainTableSnapshotTests(unittest.TestCase):
    def test_capture_snapshot_preserves_invalid_stale_status_into_compare(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_root = root / "runs"
            clean_root = root / "clean_root"
            clean_root.mkdir()
            output_dir = root / "snapshot"
            core_root = root / "core"
            (core_root / "ML1M").mkdir(parents=True)

            summary_path = (
                run_root
                / "ml1m_proposal_adaptive_mainpath"
                / "checkpoints-meta"
                / "ML1M"
                / "best_summary_proposal_adaptive.json"
            )
            summary_path.parent.mkdir(parents=True)
            summary_path.write_text(
                json.dumps(make_summary(3000, 0.02, 0.02, 0.03, 0.04, 0.05)),
                encoding="utf-8",
            )

            manifest_path = (
                run_root
                / "ml1m_proposal_adaptive_mainpath"
                / "checkpoints-meta"
                / "ML1M"
                / "frozen_run_manifest.json"
            )
            manifest_path.write_text(
                json.dumps({"provenance": {"repo_root": "/tmp/dirty-root"}}),
                encoding="utf-8",
            )

            log_path = (
                run_root
                / "ml1m_proposal_adaptive_mainpath"
                / "logs"
                / "ml1m_proposal_adaptive_mainpath.log"
            )
            log_path.parent.mkdir(parents=True)
            log_path.write_text(
                "\n".join(
                    [
                        "step: 4000, evaluation_loss: 1.0",
                        "Generating items at step: 4000",
                        "with personalzation strength 2",
                        "NDCG@5     NDCG@10    NDCG@20    NDCG@50",
                        "0.011000   0.022000   0.033000   0.044000",
                        "test phase:",
                        "with personalzation strength 2",
                        "NDCG@5     NDCG@10    NDCG@20    NDCG@50",
                        "0.020000   0.030000   0.040000   0.050000",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            core_summary = core_root / "ML1M" / "best_summary_hybrid.json"
            core_summary.write_text(
                json.dumps(make_summary(27000, 0.01, 0.015, 0.02, 0.03, 0.04)),
                encoding="utf-8",
            )

            status_csv, compare_csv = snapshot.capture_snapshot(
                run_root=run_root,
                output_dir=output_dir,
                datasets=["ML1M"],
                official_mode=True,
                official_repo_root=clean_root,
                beauty_summary_override=None,
                core_root=core_root,
            )

            with status_csv.open("r", encoding="utf-8", newline="") as handle:
                status_rows = list(csv.DictReader(handle))
            self.assertEqual("invalid_stale", status_rows[0]["status"])
            self.assertEqual("invalid_stale", status_rows[0]["official_status"])

            with compare_csv.open("r", encoding="utf-8", newline="") as handle:
                compare_rows = list(csv.DictReader(handle))
            self.assertEqual("invalid_stale", compare_rows[0]["status"])
            self.assertEqual("invalid_stale", compare_rows[0]["official_status"])
            self.assertEqual("0.01", compare_rows[0]["delta_test_p2_ndcg10"])


if __name__ == "__main__":
    unittest.main()
