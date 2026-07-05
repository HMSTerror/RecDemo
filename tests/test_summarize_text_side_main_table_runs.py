import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
import importlib.util
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


summary = load_module(
    "summarize_text_side_main_table_runs",
    REPO_ROOT / "scripts" / "summarize_text_side_main_table_runs.py",
)


class SummarizeTextSideMainTableRunsTests(unittest.TestCase):
    def test_build_rows_distinguishes_completed_running_and_queued(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_root = Path(tmpdir)

            beauty_summary = run_root / "beauty_existing.json"
            beauty_summary.write_text(json.dumps({"best_step": 8000, "best_metric": 0.02}), encoding="utf-8")

            ml1m_log = run_root / "ml1m_proposal_adaptive_mainpath" / "logs" / "ml1m_proposal_adaptive_mainpath.log"
            ml1m_log.parent.mkdir(parents=True)
            ml1m_log.write_text("step: 1000, evaluation_loss: 1.0\n", encoding="utf-8")

            steam_summary = (
                run_root
                / "steam_proposal_adaptive_mainpath"
                / "checkpoints-meta"
                / "Steam"
                / "best_summary_proposal_adaptive.json"
            )
            steam_summary.parent.mkdir(parents=True)
            steam_summary.write_text(json.dumps({"best_step": 12000, "best_metric": 0.03}), encoding="utf-8")

            launcher = run_root / "textside_main_table_gpu0" / "run_batch.sh"
            launcher.parent.mkdir(parents=True)
            launcher.write_text('export DATASETS_CSV="ATG,Steam"\n', encoding="utf-8")

            rows = summary.build_rows(
                run_root=run_root,
                datasets=["Steam", "ML1M", "Beauty", "ATG"],
                beauty_summary_override=beauty_summary,
            )
            by_name = {row["dataset"]: row for row in rows}

            self.assertEqual("completed", by_name["Steam"]["status"])
            self.assertEqual("12000", by_name["Steam"]["best_step"])

            self.assertEqual("running", by_name["ML1M"]["status"])
            self.assertEqual("1000", by_name["ML1M"]["last_logged_step"])
            self.assertEqual("", by_name["ML1M"]["early_stop_wait_counter"])

            self.assertEqual("completed", by_name["Beauty"]["status"])
            self.assertEqual("8000", by_name["Beauty"]["best_step"])

            self.assertEqual("queued", by_name["ATG"]["status"])
            self.assertEqual("textside_main_table_gpu0", by_name["ATG"]["queue_launcher"])

    def test_summary_with_unfinished_log_counts_as_running(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_root = Path(tmpdir)
            summary_path = (
                run_root
                / "Steam_proposal_adaptive_mainpath".lower()
                / "checkpoints-meta"
                / "Steam"
                / "best_summary_proposal_adaptive.json"
            )
            summary_path.parent.mkdir(parents=True)
            summary_path.write_text(json.dumps({"best_step": 1000, "best_metric": 0.01}), encoding="utf-8")

            log_path = run_root / "steam_proposal_adaptive_mainpath" / "logs" / "steam_proposal_adaptive_mainpath.log"
            log_path.parent.mkdir(parents=True)
            log_path.write_text("step: 1000, evaluation_loss: 1.0\n", encoding="utf-8")

            rows = summary.build_rows(run_root=run_root, datasets=["Steam"], beauty_summary_override=None)
            self.assertEqual("running", rows[0]["status"])

    def test_summary_with_early_stop_log_counts_as_completed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_root = Path(tmpdir)
            summary_path = (
                run_root
                / "steam_proposal_adaptive_mainpath"
                / "checkpoints-meta"
                / "Steam"
                / "best_summary_proposal_adaptive.json"
            )
            summary_path.parent.mkdir(parents=True)
            summary_path.write_text(json.dumps({"best_step": 3000, "best_metric": 0.02}), encoding="utf-8")

            log_path = run_root / "steam_proposal_adaptive_mainpath" / "logs" / "steam_proposal_adaptive_mainpath.log"
            log_path.parent.mkdir(parents=True)
            log_path.write_text(
                "\n".join(
                    [
                        "step: 8000, evaluation_loss: 1.0",
                        "EARLY_STOP_TRIGGERED step=8000 best_step=3000 best_metric=0.02",
                        "BEST_RESULT step=3000 metric=ndcg10 value=0.02 summary=/tmp/best_summary.json",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            rows = summary.build_rows(run_root=run_root, datasets=["Steam"], beauty_summary_override=None)
            self.assertEqual("completed", rows[0]["status"])

    def test_summary_parses_latest_early_stop_wait_counter(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_root = Path(tmpdir)
            log_path = run_root / "ml1m_proposal_adaptive_mainpath" / "logs" / "ml1m_proposal_adaptive_mainpath.log"
            log_path.parent.mkdir(parents=True)
            log_path.write_text(
                "\n".join(
                    [
                        "EARLY_STOP_WAIT counter=1/5 best_step=48000 best_value=0.024219",
                        "EARLY_STOP_WAIT counter=2/5 best_step=48000 best_value=0.024219",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            rows = summary.build_rows(run_root=run_root, datasets=["ML1M"], beauty_summary_override=None)
            self.assertEqual("2", rows[0]["early_stop_wait_counter"])
            self.assertEqual("5", rows[0]["early_stop_wait_patience"])

    def test_official_mode_marks_summary_without_manifest_as_invalid_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_root = Path(tmpdir)
            summary_path = (
                run_root
                / "steam_proposal_adaptive_mainpath"
                / "checkpoints-meta"
                / "Steam"
                / "best_summary_proposal_adaptive.json"
            )
            summary_path.parent.mkdir(parents=True)
            summary_path.write_text(json.dumps({"best_step": 12000, "best_metric": 0.03}), encoding="utf-8")

            rows = summary.build_rows(
                run_root=run_root,
                datasets=["Steam"],
                beauty_summary_override=None,
                official_mode=True,
            )

            self.assertEqual("invalid_stale", rows[0]["status"])
            self.assertEqual("invalid_stale", rows[0]["official_status"])
            self.assertEqual("no", rows[0]["manifest_exists"])

    def test_official_mode_marks_mismatched_manifest_provenance_as_invalid_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_root = Path(tmpdir)
            summary_path = (
                run_root
                / "steam_proposal_adaptive_mainpath"
                / "checkpoints-meta"
                / "Steam"
                / "best_summary_proposal_adaptive.json"
            )
            summary_path.parent.mkdir(parents=True)
            summary_path.write_text(json.dumps({"best_step": 12000, "best_metric": 0.03}), encoding="utf-8")

            manifest_path = (
                run_root
                / "steam_proposal_adaptive_mainpath"
                / "checkpoints-meta"
                / "Steam"
                / "frozen_run_manifest.json"
            )
            manifest_path.write_text(
                json.dumps({"provenance": {"repo_root": "/tmp/dirty-root"}}),
                encoding="utf-8",
            )

            rows = summary.build_rows(
                run_root=run_root,
                datasets=["Steam"],
                beauty_summary_override=None,
                official_mode=True,
                official_repo_root=Path("/tmp/clean-root"),
            )

            self.assertEqual("invalid_stale", rows[0]["status"])
            self.assertEqual("invalid_stale", rows[0]["official_status"])
            self.assertEqual("yes", rows[0]["manifest_exists"])

    def test_official_mode_accepts_matching_manifest_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_root = Path(tmpdir)
            clean_root = Path(tmpdir) / "clean_root"
            clean_root.mkdir()

            summary_path = (
                run_root
                / "steam_proposal_adaptive_mainpath"
                / "checkpoints-meta"
                / "Steam"
                / "best_summary_proposal_adaptive.json"
            )
            summary_path.parent.mkdir(parents=True)
            summary_path.write_text(json.dumps({"best_step": 12000, "best_metric": 0.03}), encoding="utf-8")

            manifest_path = (
                run_root
                / "steam_proposal_adaptive_mainpath"
                / "checkpoints-meta"
                / "Steam"
                / "frozen_run_manifest.json"
            )
            manifest_path.write_text(
                json.dumps({"provenance": {"repo_root": str(clean_root.resolve())}}),
                encoding="utf-8",
            )

            rows = summary.build_rows(
                run_root=run_root,
                datasets=["Steam"],
                beauty_summary_override=None,
                official_mode=True,
                official_repo_root=clean_root,
            )

            self.assertEqual("completed", rows[0]["status"])
            self.assertEqual("completed", rows[0]["official_status"])

    def test_parse_args_does_not_enable_beauty_override_by_default(self) -> None:
        with mock.patch.object(sys, "argv", ["summarize_text_side_main_table_runs.py"]):
            args = summary.parse_args()

        self.assertIsNone(args.beauty_summary_override)

    def test_write_outputs_preserve_headers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "status.csv"
            md_path = Path(tmpdir) / "status.md"
            rows = [
                {
                    "dataset": "Steam",
                    "status": "running",
                    "official_status": "running",
                    "manifest_exists": "no",
                    "summary_exists": "no",
                    "best_step": "",
                    "best_metric": "",
                    "last_logged_step": "1000",
                    "queue_launcher": "",
                }
            ]
            summary.write_csv(csv_path, rows)
            summary.write_markdown(md_path, rows)
            parsed = list(csv.DictReader(csv_path.read_text(encoding="utf-8").splitlines()))
            self.assertEqual(["Steam"], [row["dataset"] for row in parsed])
            self.assertIn("Text-side main-table run status", md_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
