import base64
import csv
import hashlib
import importlib.util
import json
import math
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_close10_atg_provenance_limited_report.py"
RUN_ROOT = "/data/Zijian/goal/RecDemoRuns/close10_atg_noise_floor"
SEED_VALUES = {
    100: 0.0397181623215186,
    101: 0.04129374588439805,
    102: 0.0423501067251558,
}
ORIGINAL_GATE1_GAP = 0.011410105406507
E0_CORRECTED_GAP = 0.011505201353104493
EXPECTED_SPREAD = 0.002631944403637204


def load_module():
    if not SCRIPT_PATH.is_file():
        return None
    spec = importlib.util.spec_from_file_location(
        "build_close10_atg_provenance_limited_report",
        SCRIPT_PATH,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def artifact_record(path: str, raw: bytes) -> dict:
    return {
        "path": path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "content_b64": base64.b64encode(raw).decode("ascii"),
    }


def summary_bytes(seed: int, value: float) -> bytes:
    payload = {
        "metric_name": "ndcg10",
        "best_step": {100: 29000, 101: 32000, 102: 42000}[seed],
        "best_metric": {100: 0.028213199503339222, 101: 0.029021099610334278, 102: 0.029207551260010158}[seed],
        "validation": {
            "p5": {
                "ndcg": [
                    0.0,
                    0.0,
                    {100: 0.028213199503339222, 101: 0.029021099610334278, 102: 0.029207551260010158}[seed],
                ]
            }
        },
        "test": {
            "p2": {"ndcg": [0.0, 0.0, value]},
            "p5": {"ndcg": [0.0, 0.0, value + 0.001]},
            "p10": {"ndcg": [0.0, 0.0, value + 0.002]},
        },
    }
    return (json.dumps(payload, indent=2) + "\n").encode("utf-8")


def make_snapshot() -> dict:
    entries = []
    terminal_steps = {100: 34000, 101: 37000, 102: 47000}
    best_steps = {100: 29000, 101: 32000, 102: 42000}
    best_metrics = {100: 0.028213, 101: 0.029021, 102: 0.029208}
    for seed, value in SEED_VALUES.items():
        summary_path = (
            f"{RUN_ROOT}/atg_core_seed{seed}/checkpoints-meta/ATG/"
            "best_summary_hybrid.json"
        )
        log_path = f"{RUN_ROOT}/atg_core_seed{seed}/logs/atg_core_seed{seed}.log"
        log = (
            "EARLY_STOP_TRIGGERED "
            f"step={terminal_steps[seed]} best_step={best_steps[seed]} "
            f"best_metric={best_metrics[seed]:.6f}\n"
            f"BEST_RESULT step={best_steps[seed]} metric=ndcg10 "
            f"value={best_metrics[seed]:.6f} summary={summary_path}\n"
        ).encode("utf-8")
        entries.append(
            {
                "seed": seed,
                "summary": artifact_record(summary_path, summary_bytes(seed, value)),
                "log": artifact_record(log_path, log),
                "manifest_path": (
                    f"{RUN_ROOT}/atg_core_seed{seed}/checkpoints-meta/ATG/"
                    "frozen_run_manifest.json"
                ),
                "manifest_exists": False,
            }
        )

    session_path = "/data/Zijian/goal/RecDemo_clean_closeout_chain/logs/close10_session.log"
    session_raw = b"2026-07-10 13:51:04 close10 ALL_SEEDS_DONE\n"
    return {
        "schema_version": "close10-atg-remote-snapshot-v1",
        "collected_at": "2026-07-10T18:00:00+08:00",
        "source_host": "l20",
        "run_root": RUN_ROOT,
        "policy": {
            "remote_read_only": True,
            "manifest_reconstructed": False,
        },
        "entries": entries,
        "session_log": artifact_record(session_path, session_raw),
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_inputs(root: Path, snapshot: dict | None = None) -> tuple[Path, Path, Path]:
    snapshot_path = root / "snapshot.json"
    gate1_path = root / "gate1.json"
    e0_path = root / "e0.json"
    write_json(snapshot_path, snapshot or make_snapshot())
    write_json(
        gate1_path,
        {
            "datasets": [
                {
                    "dataset": "ATG",
                    "delta_test_p2_ndcg10": -ORIGINAL_GATE1_GAP,
                    "dataset_verdict": "miss",
                }
            ]
        },
    )
    write_json(
        e0_path,
        {
            "gate_reread": {
                "sprint05_preregistered_prediction_reread": {
                    "ATG": {
                        "corrected_delta_test_p2_ndcg10": -E0_CORRECTED_GAP,
                        "corrected_outcome": "miss",
                        "gate_state": "barely_open_phi_0.117375",
                    }
                }
            }
        },
    )
    return snapshot_path, gate1_path, e0_path


class Close10AtgProvenanceLimitedReportTests(unittest.TestCase):
    def require_module(self):
        module = load_module()
        self.assertIsNotNone(
            module,
            "provenance-limited CLOSE-10 report builder has not been implemented",
        )
        return module

    def test_contract_requires_exactly_three_frozen_seeds(self) -> None:
        module = self.require_module()
        self.assertEqual((100, 101, 102), module.REQUIRED_SEEDS)
        self.assertEqual(
            "close10-atg-provenance-limited-v1",
            module.REPORT_SCHEMA_VERSION,
        )

    def test_collect_local_snapshot_hashes_raw_copies_and_reports_remote_paths(self) -> None:
        module = self.require_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local_run_root = root / "mirror"
            expected = make_snapshot()
            for entry in expected["entries"]:
                seed = entry["seed"]
                local_summary = (
                    local_run_root
                    / f"atg_core_seed{seed}"
                    / "checkpoints-meta"
                    / "ATG"
                    / "best_summary_hybrid.json"
                )
                local_log = (
                    local_run_root
                    / f"atg_core_seed{seed}"
                    / "logs"
                    / f"atg_core_seed{seed}.log"
                )
                local_summary.parent.mkdir(parents=True, exist_ok=True)
                local_log.parent.mkdir(parents=True, exist_ok=True)
                local_summary.write_bytes(base64.b64decode(entry["summary"]["content_b64"]))
                local_log.write_bytes(base64.b64decode(entry["log"]["content_b64"]))
            local_session = root / "close10_session.log"
            local_session.write_bytes(
                base64.b64decode(expected["session_log"]["content_b64"])
            )

            collected = module.collect_local_snapshot(
                local_run_root=local_run_root,
                reported_run_root=RUN_ROOT,
                local_session_log=local_session,
                reported_session_log=expected["session_log"]["path"],
                source_host="l20",
                collected_at="2026-07-10T18:00:00+08:00",
            )

        self.assertEqual("close10-atg-remote-snapshot-v1", collected["schema_version"])
        self.assertEqual([100, 101, 102], [entry["seed"] for entry in collected["entries"]])
        self.assertEqual(
            expected["entries"][0]["summary"]["sha256"],
            collected["entries"][0]["summary"]["sha256"],
        )
        self.assertEqual(
            expected["entries"][0]["summary"]["path"],
            collected["entries"][0]["summary"]["path"],
        )
        self.assertFalse(collected["entries"][0]["manifest_exists"])
        self.assertFalse(collected["policy"]["manifest_reconstructed"])

    def test_end_to_end_report_recomputes_observed_spread_and_two_gap_reads(self) -> None:
        module = self.require_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot_path, gate1_path, e0_path = write_inputs(root)
            output_dir = root / "report"
            module.write_report(
                snapshot_path=snapshot_path,
                gate1_report_path=gate1_path,
                e0_report_path=e0_path,
                output_dir=output_dir,
            )
            report = json.loads(
                (output_dir / "close10_atg_provenance_limited_report.json").read_text(
                    encoding="utf-8"
                )
            )
            with (
                output_dir / "close10_atg_provenance_limited_observations.csv"
            ).open(encoding="utf-8", newline="") as handle:
                csv_rows = list(csv.DictReader(handle))
            chinese = (
                output_dir / "close10_atg_provenance_limited_report_zh.md"
            ).read_text(encoding="utf-8")
            english = (
                output_dir / "close10_atg_provenance_limited_report.md"
            ).read_text(encoding="utf-8")

        self.assertEqual(3, len(report["observations"]))
        self.assertEqual([100, 101, 102], [row["seed"] for row in report["observations"]])
        self.assertTrue(
            math.isclose(
                EXPECTED_SPREAD,
                report["observed_spread"]["max_pairwise_test_p2_ndcg10"],
                rel_tol=0.0,
                abs_tol=1e-15,
            )
        )
        original = report["gap_comparisons"]["original_gate1"]
        corrected = report["gap_comparisons"]["e0_corrected"]
        self.assertTrue(math.isclose(ORIGINAL_GATE1_GAP, original["abs_gap"], abs_tol=1e-15))
        self.assertTrue(math.isclose(E0_CORRECTED_GAP, corrected["abs_gap"], abs_tol=1e-15))
        self.assertTrue(
            math.isclose(
                ORIGINAL_GATE1_GAP / EXPECTED_SPREAD,
                original["gap_to_observed_spread_ratio"],
                rel_tol=0.0,
                abs_tol=1e-12,
            )
        )
        self.assertTrue(
            math.isclose(
                E0_CORRECTED_GAP / EXPECTED_SPREAD,
                corrected["gap_to_observed_spread_ratio"],
                rel_tol=0.0,
                abs_tol=1e-12,
            )
        )
        self.assertEqual("outside_observed_spread", original["decision"])
        self.assertEqual("outside_observed_spread", corrected["decision"])
        self.assertEqual(3, len(csv_rows))
        self.assertEqual(str(SEED_VALUES[102]), csv_rows[2]["test_p2_ndcg10"])
        self.assertIn("0.002631944403637204", chinese)
        self.assertIn("provenance-limited observed spread", english)

    def test_report_discloses_missing_manifests_without_reconstruction_or_parity_claim(self) -> None:
        module = self.require_module()
        report = module.build_report_payload(
            make_snapshot(),
            {"datasets": [{"dataset": "ATG", "delta_test_p2_ndcg10": -ORIGINAL_GATE1_GAP}]},
            {
                "gate_reread": {
                    "sprint05_preregistered_prediction_reread": {
                        "ATG": {"corrected_delta_test_p2_ndcg10": -E0_CORRECTED_GAP}
                    }
                }
            },
        )
        self.assertFalse(report["scope"]["complete_configuration_parity_claimed"])
        self.assertFalse(report["scope"]["population_variance_estimate"])
        self.assertFalse(report["scope"]["training_seed_variance_estimate"])
        self.assertFalse(report["scope"]["manifest_reconstructed"])
        for observation in report["observations"]:
            self.assertFalse(observation["manifest_exists"])
            self.assertFalse(observation["manifest_reconstructed"])

    def test_fails_closed_for_incomplete_or_wrong_seed_set(self) -> None:
        module = self.require_module()
        snapshot = make_snapshot()
        snapshot["entries"].pop()
        with self.assertRaisesRegex(ValueError, "seed set mismatch"):
            module.build_report_payload(
                snapshot,
                {"datasets": [{"dataset": "ATG", "delta_test_p2_ndcg10": -ORIGINAL_GATE1_GAP}]},
                {
                    "gate_reread": {
                        "sprint05_preregistered_prediction_reread": {
                            "ATG": {"corrected_delta_test_p2_ndcg10": -E0_CORRECTED_GAP}
                        }
                    }
                },
            )

    def test_fails_closed_for_tampered_summary_or_nonfinite_metric(self) -> None:
        module = self.require_module()
        snapshot = make_snapshot()
        snapshot["entries"][0]["summary"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            module.normalize_snapshot(snapshot)

        snapshot = make_snapshot()
        raw = summary_bytes(100, float("nan"))
        snapshot["entries"][0]["summary"] = artifact_record(
            snapshot["entries"][0]["summary"]["path"], raw
        )
        with self.assertRaisesRegex(ValueError, "finite"):
            module.normalize_snapshot(snapshot)

    def test_fails_closed_without_terminal_and_bound_best_result_evidence(self) -> None:
        module = self.require_module()
        snapshot = make_snapshot()
        entry = snapshot["entries"][1]
        entry["log"] = artifact_record(entry["log"]["path"], b"step: 32000, loss: 1.0\n")
        with self.assertRaisesRegex(ValueError, "completion evidence"):
            module.normalize_snapshot(snapshot)

        snapshot = make_snapshot()
        entry = snapshot["entries"][1]
        raw = base64.b64decode(entry["log"]["content_b64"])
        raw = raw.replace(b"best_summary_hybrid.json", b"wrong_summary.json")
        entry["log"] = artifact_record(entry["log"]["path"], raw)
        with self.assertRaisesRegex(ValueError, "does not bind summary"):
            module.normalize_snapshot(snapshot)

    def test_provenance_limited_builder_rejects_present_or_reconstructed_manifest(self) -> None:
        module = self.require_module()
        snapshot = make_snapshot()
        snapshot["entries"][0]["manifest_exists"] = True
        with self.assertRaisesRegex(ValueError, "manifest absence required"):
            module.normalize_snapshot(snapshot)

        snapshot = make_snapshot()
        snapshot["policy"]["manifest_reconstructed"] = True
        with self.assertRaisesRegex(ValueError, "retrospective manifest reconstruction"):
            module.normalize_snapshot(snapshot)

    def test_report_has_no_prohibited_single_run_claim_language(self) -> None:
        module = self.require_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot_path, gate1_path, e0_path = write_inputs(root)
            output_dir = root / "report"
            module.write_report(
                snapshot_path=snapshot_path,
                gate1_report_path=gate1_path,
                e0_report_path=e0_path,
                output_dir=output_dir,
            )
            text = "\n".join(
                path.read_text(encoding="utf-8")
                for path in output_dir.iterdir()
                if path.suffix in {".md", ".json", ".csv"}
            ).lower()

        for prohibited in (
            "significant",
            "stable",
            "statistically equivalent",
            "within noise",
        ):
            self.assertNotIn(prohibited, text)

    def test_report_archives_raw_source_evidence_bytes(self) -> None:
        module = self.require_module()
        snapshot = make_snapshot()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot_path, gate1_path, e0_path = write_inputs(root)
            output_dir = root / "report"
            module.write_report(
                snapshot_path=snapshot_path,
                gate1_report_path=gate1_path,
                e0_report_path=e0_path,
                output_dir=output_dir,
            )

            for entry in snapshot["entries"]:
                seed = entry["seed"]
                expected_summary = base64.b64decode(entry["summary"]["content_b64"])
                expected_log = base64.b64decode(entry["log"]["content_b64"])
                self.assertEqual(
                    expected_summary,
                    (output_dir / f"provenance/seed{seed}/best_summary_hybrid.json").read_bytes(),
                )
                self.assertEqual(
                    expected_log,
                    (output_dir / f"provenance/seed{seed}/atg_core_seed{seed}.log").read_bytes(),
                )
            self.assertEqual(
                base64.b64decode(snapshot["session_log"]["content_b64"]),
                (output_dir / "provenance/session/close10_session.log").read_bytes(),
            )

    def test_report_disables_text_normalization_for_raw_provenance(self) -> None:
        module = self.require_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot_path, gate1_path, e0_path = write_inputs(root)
            output_dir = root / "report"
            module.write_report(
                snapshot_path=snapshot_path,
                gate1_report_path=gate1_path,
                e0_report_path=e0_path,
                output_dir=output_dir,
            )
            self.assertEqual(
                "provenance/** -text -diff\n",
                (output_dir / ".gitattributes").read_text(encoding="utf-8"),
            )

    def test_sha256sums_covers_every_other_output_and_verifies(self) -> None:
        module = self.require_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot_path, gate1_path, e0_path = write_inputs(root)
            output_dir = root / "report"
            module.write_report(
                snapshot_path=snapshot_path,
                gate1_report_path=gate1_path,
                e0_report_path=e0_path,
                output_dir=output_dir,
            )
            entries = {}
            for line in (output_dir / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
                digest, relative_path = line.split("  ", 1)
                entries[relative_path] = digest
            actual_files = {
                path.relative_to(output_dir).as_posix()
                for path in output_dir.rglob("*")
                if path.is_file() and path.name != "SHA256SUMS"
            }
            self.assertEqual(actual_files, set(entries))
            for relative_path, expected_digest in entries.items():
                actual_digest = hashlib.sha256((output_dir / relative_path).read_bytes()).hexdigest()
                self.assertEqual(expected_digest, actual_digest)

    def test_output_directory_is_no_clobber(self) -> None:
        module = self.require_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot_path, gate1_path, e0_path = write_inputs(root)
            output_dir = root / "report"
            module.write_report(
                snapshot_path=snapshot_path,
                gate1_report_path=gate1_path,
                e0_report_path=e0_path,
                output_dir=output_dir,
            )
            with self.assertRaisesRegex(FileExistsError, "refusing to overwrite"):
                module.write_report(
                    snapshot_path=snapshot_path,
                    gate1_report_path=gate1_path,
                    e0_report_path=e0_path,
                    output_dir=output_dir,
                )


if __name__ == "__main__":
    unittest.main()
