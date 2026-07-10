from __future__ import annotations

import base64
import copy
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_e10_selector_strength_report.py"


def load_module():
    if not SCRIPT_PATH.exists():
        raise AssertionError(f"missing E10 builder: {SCRIPT_PATH}")
    spec = importlib.util.spec_from_file_location("build_e10_selector_strength_report", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


DATASETS = ("Steam", "ML1M", "Beauty", "ATG")
CORE_TYPES = {
    "Steam": "adaptive",
    "ML1M": "hybrid",
    "Beauty": "adaptive",
    "ATG": "hybrid",
}
CONTROL_VARIANTS = {
    "u_shuffle": "ablation_u_shuffle",
    "text_anchor_only": "ablation_text_anchor_only",
    "global_p": "ablation_global_p",
}


def e0_artifact_id(dataset: str, arm: str) -> str:
    dataset_token = dataset.lower()
    if arm == "host":
        return f"host_{dataset_token}"
    if arm == "full":
        return f"ours_full_{dataset_token}"
    return f"{arm}_{dataset_token}"


def make_e0_amendment(snapshot: dict) -> dict:
    rows = []
    for entry in snapshot["entries"]:
        summary = embedded_json(entry["summary"])
        rows.append(
            {
                "artifact_id": e0_artifact_id(entry["dataset"], entry["arm"]),
                "dataset": entry["dataset"],
                "checkpoint_path": entry["checkpoint"]["path"],
                "checkpoint_sha256": entry["checkpoint"]["sha256"],
                "summary_path": entry["summary"]["path"],
                "summary_sha256": entry["summary"]["sha256"],
                "old_hr10": summary["test"]["p2"]["hr"][2],
                "old_ndcg10": summary["test"]["p2"]["ndcg"][2],
                "corrected_hr10": summary["test"]["p2"]["hr"][2] + 0.0001,
                "corrected_ndcg10": summary["test"]["p2"]["ndcg"][2] + 0.0001,
            }
        )
    return {
        "report_name": "E0 full-tail common-evaluator dated amendment",
        "matrix_validation": {"all_contract_checks_pass": True, "artifact_count": 18},
        "rows": rows,
    }


def build_payload(module, snapshot: dict, e0_amendment: dict | None = None) -> dict:
    return module.build_report_payload(snapshot, e0_amendment or make_e0_amendment(snapshot))


def metric_block(p2: float, p5: float, p10: float) -> dict[str, dict[str, list[float]]]:
    result: dict[str, dict[str, list[float]]] = {}
    for strength, ndcg10 in (("p2", p2), ("p5", p5), ("p10", p10)):
        hr10 = ndcg10 + 0.05
        result[strength] = {
            "hr": [0.0, 0.0, hr10, hr10, hr10],
            "ndcg": [0.0, 0.0, ndcg10, ndcg10, ndcg10],
        }
    return result


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_summary(
    path: Path,
    *,
    best_step: int,
    selector_strength: str,
    test_values: tuple[float, float, float],
    omit_test_strength: str | None = None,
) -> None:
    validation = metric_block(0.11, 0.12, 0.13)
    best_metric = validation[selector_strength]["ndcg"][2]
    test = metric_block(*test_values)
    if omit_test_strength is not None:
        del test[omit_test_strength]
    write_json(
        path,
        {
            "metric_name": "ndcg10",
            "best_step": best_step,
            "best_metric": best_metric,
            "validation": validation,
            "test": test,
        },
    )


def write_checkpoint(path: Path, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((label + "\n").encode("utf-8"))


def write_manifest(path: Path, *, dataset: str, arm: str, run_dir: Path) -> None:
    write_json(
        path,
        {
            "dataset": dataset,
            "random_seed": 100,
            "run_dir": str(run_dir),
            "bank_hash": hashlib.sha256(f"bank:{dataset}".encode()).hexdigest(),
            "split_hash": hashlib.sha256(f"split:{dataset}".encode()).hexdigest(),
            "frozen_config": {
                "ablation_mode": "none" if arm == "full" else arm,
                "early_stop_metric": "ndcg10",
                "early_stop_strength": "p5",
            },
            "provenance": {
                "git_head": "a" * 40,
                "repo_root": "/frozen/repo",
            },
        },
    )


def replace_embedded_json(record: dict, payload: dict) -> None:
    raw = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
    record["content_b64"] = base64.b64encode(raw).decode("ascii")
    record["sha256"] = hashlib.sha256(raw).hexdigest()
    record["size_bytes"] = len(raw)


def embedded_json(record: dict) -> dict:
    return json.loads(base64.b64decode(record["content_b64"]))


def replace_embedded_text(record: dict, text: str) -> None:
    raw = text.encode("utf-8")
    record["content_b64"] = base64.b64encode(raw).decode("ascii")
    record["sha256"] = hashlib.sha256(raw).hexdigest()
    record["size_bytes"] = len(raw)


def create_fixture(root: Path, *, omit_steam_full_p10: bool = False) -> tuple[Path, Path, Path]:
    core_root = root / "core" / "checkpoints-meta"
    run_root = root / "runs" / "main_table_text_side"
    host_log_root = root / "core" / "logs"

    for index, dataset in enumerate(DATASETS, start=1):
        graph_type = CORE_TYPES[dataset]
        host_summary = core_root / dataset / f"best_summary_{graph_type}.json"
        host_checkpoint = core_root / dataset / f"checkpoint_{graph_type}_best.pth"
        # Steam host/full intentionally reverse order between p2 and p5/p10.
        host_test = (0.20, 0.10, 0.20) if dataset == "Steam" else (0.20, 0.21, 0.22)
        write_summary(
            host_summary,
            best_step=index * 1000,
            selector_strength="p2",
            test_values=host_test,
        )
        write_checkpoint(host_checkpoint, f"{dataset}:host")
        log_path = host_log_root / f"{dataset.lower()}_{graph_type}_earlystop.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            "EARLY_STOP_MONITOR step=1000 metric=ndcg10 strength=p2 value=0.110000\n"
            f"BEST_RESULT step={index * 1000} metric=ndcg10 value=0.110000 "
            f"summary=./checkpoints-meta/{dataset}/best_summary_{graph_type}.json\n",
            encoding="utf-8",
        )

        full_dir = run_root / f"{dataset.lower()}_proposal_adaptive_mainpath"
        full_meta = full_dir / "checkpoints-meta" / dataset
        write_summary(
            full_meta / "best_summary_proposal_adaptive.json",
            best_step=index * 1000 + 500,
            selector_strength="p5",
            test_values=(0.10, 0.20, 0.10) if dataset == "Steam" else (0.19, 0.22, 0.21),
            omit_test_strength="p10" if dataset == "Steam" and omit_steam_full_p10 else None,
        )
        write_checkpoint(full_meta / "checkpoint_proposal_adaptive_best.pth", f"{dataset}:full")
        write_manifest(full_meta / "frozen_run_manifest.json", dataset=dataset, arm="full", run_dir=full_dir)

    for dataset in ("Beauty", "Steam"):
        for arm_index, (arm, variant) in enumerate(CONTROL_VARIANTS.items(), start=1):
            run_dir = run_root / f"{dataset.lower()}_proposal_adaptive_{variant}"
            meta_dir = run_dir / "checkpoints-meta" / dataset
            write_summary(
                meta_dir / "best_summary_proposal_adaptive.json",
                best_step=10_000 + arm_index,
                selector_strength="p5",
                test_values=(0.15 + arm_index / 100, 0.16 + arm_index / 100, 0.17 + arm_index / 100),
            )
            write_checkpoint(meta_dir / "checkpoint_proposal_adaptive_best.pth", f"{dataset}:{arm}")
            write_manifest(meta_dir / "frozen_run_manifest.json", dataset=dataset, arm=arm, run_dir=run_dir)

    return core_root, run_root, host_log_root


class E10SelectorStrengthReportTests(unittest.TestCase):
    def test_snapshot_embeds_hash_bound_raw_summary_manifest_and_host_log_bytes(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            core_root, run_root, host_log_root = create_fixture(Path(tmp))
            snapshot = module.collect_snapshot(
                core_root=core_root,
                run_root=run_root,
                host_log_root=host_log_root,
                source_host="fixture-l20",
                collected_at="2026-07-10T17:00:00+08:00",
            )

        for entry in snapshot["entries"]:
            self.assertIn("content_b64", entry["summary"])
            if entry["manifest"] is not None:
                self.assertIn("content_b64", entry["manifest"])
            if entry["arm"] == "host":
                evidence = entry["selection_evidence"]
                self.assertIn("content_b64", evidence)
                raw = base64.b64decode(evidence["content_b64"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), evidence["sha256"])

    def test_rejects_self_attested_compact_payload_after_metric_tampering(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            core_root, run_root, host_log_root = create_fixture(Path(tmp))
            snapshot = module.collect_snapshot(
                core_root=core_root,
                run_root=run_root,
                host_log_root=host_log_root,
                source_host="fixture-l20",
                collected_at="2026-07-10T17:00:00+08:00",
            )

        steam_full = next(
            entry for entry in snapshot["entries"] if entry["dataset"] == "Steam" and entry["arm"] == "full"
        )
        e0_amendment = make_e0_amendment(snapshot)
        summary = steam_full["summary"]
        raw_payload = json.loads(base64.b64decode(summary.pop("content_b64")))
        raw_payload["test"]["p2"]["ndcg"][2] = 0.000001
        summary["payload"] = raw_payload
        summary["collector_sha256_verified"] = True
        with self.assertRaisesRegex(ValueError, "hash-bound raw content required"):
            build_payload(module, snapshot, e0_amendment)

    def test_collects_exact_selected_artifact_matrix_with_hashes(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            core_root, run_root, host_log_root = create_fixture(Path(tmp))
            snapshot = module.collect_snapshot(
                core_root=core_root,
                run_root=run_root,
                host_log_root=host_log_root,
                source_host="fixture-l20",
                collected_at="2026-07-10T17:00:00+08:00",
            )

        self.assertEqual("aaai-e10-existing-artifacts-v1", snapshot["schema_version"])
        self.assertEqual(14, len(snapshot["entries"]))
        self.assertEqual(0, snapshot["policy"]["training_runs_launched"])
        self.assertEqual(0, snapshot["policy"]["evaluation_runs_launched"])
        self.assertFalse(snapshot["policy"]["checkpoint_reselection"])
        by_key = {(entry["dataset"], entry["arm"]): entry for entry in snapshot["entries"]}
        self.assertEqual(set(DATASETS), {dataset for dataset, arm in by_key if arm == "host"})
        self.assertIsNone(by_key[("Steam", "host")]["manifest"])
        self.assertEqual("log", by_key[("Steam", "host")]["selection_evidence"]["source"])
        self.assertEqual("manifest", by_key[("Steam", "full")]["selection_evidence"]["source"])
        for entry in snapshot["entries"]:
            for artifact_name in ("summary", "checkpoint"):
                self.assertRegex(entry[artifact_name]["sha256"], r"^[0-9a-f]{64}$")
            raw = base64.b64decode(entry["summary"]["content_b64"])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), entry["summary"]["sha256"])

    def test_builds_same_checkpoint_strength_readouts_and_reports_reversals(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            core_root, run_root, host_log_root = create_fixture(root)
            snapshot = module.collect_snapshot(
                core_root=core_root,
                run_root=run_root,
                host_log_root=host_log_root,
                source_host="fixture-l20",
                collected_at="2026-07-10T17:00:00+08:00",
            )
            snapshot_path = root / "snapshot.json"
            write_json(snapshot_path, snapshot)
            e0_path = root / "e0_evaluator_amendment.json"
            write_json(e0_path, make_e0_amendment(snapshot))
            output_dir = root / "output"
            module.write_report(snapshot_path=snapshot_path, e0_amendment_path=e0_path, output_dir=output_dir)

            payload = json.loads((output_dir / "e10_selector_strength_report.json").read_text(encoding="utf-8"))
            with (output_dir / "e10_selector_strength_table.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            report_zh = (output_dir / "e10_selector_strength_report_zh.md").read_text(encoding="utf-8")
            provenance = json.loads((output_dir / "provenance_manifest.json").read_text(encoding="utf-8"))
            sums = (output_dir / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
            verified_sums = []
            for line in sums:
                digest, relative_path = line.split("  ", 1)
                verified_sums.append(
                    hashlib.sha256((output_dir / relative_path).read_bytes()).hexdigest() == digest
                )

        self.assertEqual(14, len(rows))
        by_key = {(row["dataset"], row["arm"]): row for row in rows}
        self.assertEqual("validation_p2_ndcg10", by_key[("Steam", "host")]["selector_metric"])
        self.assertEqual("validation_p5_ndcg10", by_key[("Steam", "full")]["selector_metric"])
        self.assertEqual("NA", by_key[("Steam", "host")]["manifest_path"])
        self.assertEqual("0.25", by_key[("Steam", "host")]["test_p2_hr10"])
        self.assertEqual("0.2", by_key[("Steam", "host")]["test_p2_ndcg10"])
        self.assertIn("Steam/host:manifest/path", payload["missing_fields"])
        self.assertNotIn("Steam/full:manifest/path", payload["missing_fields"])
        self.assertFalse(any(":test/" in field for field in payload["missing_fields"]))
        self.assertTrue(payload["strength_sensitivity"]["strict_pairwise_reversals"])
        self.assertFalse(payload["scope"]["alternative_selector_sweep_used"])
        reversal = next(
            item
            for item in payload["strength_sensitivity"]["strict_pairwise_reversals"]
            if item["dataset"] == "Steam"
            and item["metric"] == "NDCG@10"
            and {item["arm_a"], item["arm_b"]} == {"host", "full"}
        )
        self.assertEqual(["p2", "p5", "p10"], reversal["strengths"])
        self.assertIn("仅作 strength sensitivity", report_zh)
        self.assertIn("未启动训练", report_zh)
        self.assertIn("旧 evaluator", report_zh)
        self.assertIn("`analyze_selector_sweep.py` 未执行", report_zh)

        self.assertEqual(42, provenance["source_artifact_count"])
        self.assertEqual(42, len(provenance["source_artifacts"]))
        self.assertRegex(provenance["collector"]["script_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(provenance["source_snapshot"]["sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(provenance["e0_amendment"]["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(5, len(sums))
        self.assertTrue(all(verified_sums))

    def test_missing_strength_readout_is_na_and_never_requests_a_rerun(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            core_root, run_root, host_log_root = create_fixture(Path(tmp), omit_steam_full_p10=True)
            snapshot = module.collect_snapshot(
                core_root=core_root,
                run_root=run_root,
                host_log_root=host_log_root,
                source_host="fixture-l20",
                collected_at="2026-07-10T17:00:00+08:00",
            )
            payload = build_payload(module, snapshot)

        row = next(row for row in payload["rows"] if row["dataset"] == "Steam" and row["arm"] == "full")
        self.assertEqual("NA", row["test_p10_hr10"])
        self.assertEqual("NA", row["test_p10_ndcg10"])
        self.assertIn("Steam/full:test/p10/hr10", payload["missing_fields"])
        self.assertIn("Steam/full:test/p10/ndcg10", payload["missing_fields"])
        self.assertEqual(0, payload["policy"]["evaluation_runs_launched"])

    def test_each_missing_metric_cell_is_na_and_recorded_without_hiding_its_pair(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            core_root, run_root, host_log_root = create_fixture(Path(tmp))
            summary_path = (
                run_root
                / "steam_proposal_adaptive_mainpath"
                / "checkpoints-meta"
                / "Steam"
                / "best_summary_proposal_adaptive.json"
            )
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            del summary["test"]["p10"]["hr"]
            write_json(summary_path, summary)
            snapshot = module.collect_snapshot(
                core_root=core_root,
                run_root=run_root,
                host_log_root=host_log_root,
                source_host="fixture-l20",
                collected_at="2026-07-10T17:00:00+08:00",
            )
            payload = build_payload(module, snapshot)

        row = next(row for row in payload["rows"] if row["dataset"] == "Steam" and row["arm"] == "full")
        self.assertEqual("NA", row["test_p10_hr10"])
        self.assertNotEqual("NA", row["test_p10_ndcg10"])
        self.assertIn("Steam/full:test/p10/hr10", payload["missing_fields"])
        self.assertNotIn("Steam/full:test/p10/ndcg10", payload["missing_fields"])

    def test_none_and_empty_provenance_become_na_and_are_listed_as_missing(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            core_root, run_root, host_log_root = create_fixture(Path(tmp))
            manifest_path = (
                run_root
                / "steam_proposal_adaptive_mainpath"
                / "checkpoints-meta"
                / "Steam"
                / "frozen_run_manifest.json"
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["bank_hash"] = None
            manifest["provenance"]["git_head"] = ""
            write_json(manifest_path, manifest)
            snapshot = module.collect_snapshot(
                core_root=core_root,
                run_root=run_root,
                host_log_root=host_log_root,
                source_host="fixture-l20",
                collected_at="2026-07-10T17:00:00+08:00",
            )
            payload = build_payload(module, snapshot)

        row = next(row for row in payload["rows"] if row["dataset"] == "Steam" and row["arm"] == "full")
        self.assertEqual("NA", row["bank_hash"])
        self.assertEqual("NA", row["provenance_git_head"])
        self.assertNotIn("None", row.values())
        self.assertIn("Steam/full:manifest/bank_hash", payload["missing_fields"])
        self.assertIn("Steam/full:manifest/provenance/git_head", payload["missing_fields"])

    def test_rejects_nonfinite_or_negative_selection_metadata(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            core_root, run_root, host_log_root = create_fixture(Path(tmp))
            snapshot = module.collect_snapshot(
                core_root=core_root,
                run_root=run_root,
                host_log_root=host_log_root,
                source_host="fixture-l20",
                collected_at="2026-07-10T17:00:00+08:00",
            )

        base_entry = next(
            entry for entry in snapshot["entries"] if entry["dataset"] == "Steam" and entry["arm"] == "full"
        )
        cases = (
            ("nonfinite best_metric", lambda summary: summary.__setitem__("best_metric", float("nan"))),
            ("nonnegative best_step", lambda summary: summary.__setitem__("best_step", -1)),
            (
                "nonfinite selected validation",
                lambda summary: summary["validation"]["p5"]["ndcg"].__setitem__(2, float("inf")),
            ),
        )
        for message, mutate in cases:
            with self.subTest(message=message):
                candidate = copy.deepcopy(snapshot)
                entry = next(
                    item for item in candidate["entries"] if item["dataset"] == "Steam" and item["arm"] == "full"
                )
                summary = embedded_json(entry["summary"])
                mutate(summary)
                replace_embedded_json(entry["summary"], summary)
                with self.assertRaisesRegex(ValueError, message):
                    build_payload(module, candidate, make_e0_amendment(snapshot))

        host_candidate = copy.deepcopy(snapshot)
        host = next(
            item for item in host_candidate["entries"] if item["dataset"] == "Steam" and item["arm"] == "host"
        )
        log_text = base64.b64decode(host["selection_evidence"]["content_b64"]).decode("utf-8")
        log_text = log_text.replace("value=0.110000 summary=", "value=NaN summary=")
        replace_embedded_text(host["selection_evidence"], log_text)
        host["selection_evidence"]["last_best_result_line"] = host["selection_evidence"][
            "last_best_result_line"
        ].replace("value=0.110000", "value=NaN")
        with self.assertRaisesRegex(ValueError, "nonfinite host BEST_RESULT"):
            build_payload(module, host_candidate, make_e0_amendment(snapshot))

    def test_rejects_non_validation_or_mismatched_checkpoint_selection(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            core_root, run_root, host_log_root = create_fixture(Path(tmp))
            snapshot = module.collect_snapshot(
                core_root=core_root,
                run_root=run_root,
                host_log_root=host_log_root,
                source_host="fixture-l20",
                collected_at="2026-07-10T17:00:00+08:00",
            )

        steam_full = next(
            entry for entry in snapshot["entries"] if entry["dataset"] == "Steam" and entry["arm"] == "full"
        )
        manifest_raw = base64.b64decode(steam_full["manifest"]["content_b64"])
        manifest = json.loads(manifest_raw)
        manifest["frozen_config"]["early_stop_strength"] = "test_p5"
        replacement = (json.dumps(manifest, indent=2) + "\n").encode()
        steam_full["manifest"]["content_b64"] = base64.b64encode(replacement).decode("ascii")
        steam_full["manifest"]["sha256"] = hashlib.sha256(replacement).hexdigest()
        steam_full["manifest"]["size_bytes"] = len(replacement)
        steam_full["selection_evidence"]["sha256"] = steam_full["manifest"]["sha256"]
        with self.assertRaisesRegex(ValueError, "validation-only selector"):
            build_payload(module, snapshot)

        manifest["frozen_config"]["early_stop_strength"] = "p10"
        replacement = (json.dumps(manifest, indent=2) + "\n").encode()
        steam_full["manifest"]["content_b64"] = base64.b64encode(replacement).decode("ascii")
        steam_full["manifest"]["sha256"] = hashlib.sha256(replacement).hexdigest()
        steam_full["manifest"]["size_bytes"] = len(replacement)
        steam_full["selection_evidence"]["sha256"] = steam_full["manifest"]["sha256"]
        with self.assertRaisesRegex(ValueError, "best_metric does not bind"):
            build_payload(module, snapshot)

    def test_rejects_cross_arm_manifest_or_unbound_selector_evidence(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            core_root, run_root, host_log_root = create_fixture(Path(tmp))
            snapshot = module.collect_snapshot(
                core_root=core_root,
                run_root=run_root,
                host_log_root=host_log_root,
                source_host="fixture-l20",
                collected_at="2026-07-10T17:00:00+08:00",
            )

        steam_full = next(
            entry for entry in snapshot["entries"] if entry["dataset"] == "Steam" and entry["arm"] == "full"
        )
        beauty_full = next(
            entry for entry in snapshot["entries"] if entry["dataset"] == "Beauty" and entry["arm"] == "full"
        )
        original_manifest = steam_full["manifest"]
        steam_full["manifest"] = beauty_full["manifest"]
        steam_full["selection_evidence"] = beauty_full["selection_evidence"]
        with self.assertRaisesRegex(ValueError, "manifest dataset mismatch"):
            build_payload(module, snapshot)

        steam_full["manifest"] = original_manifest
        steam_full["selection_evidence"]["sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "selector evidence does not bind manifest"):
            build_payload(module, snapshot)

    def test_e0_amendment_cross_binds_checkpoint_summary_and_old_p2_metrics(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            core_root, run_root, host_log_root = create_fixture(Path(tmp))
            snapshot = module.collect_snapshot(
                core_root=core_root,
                run_root=run_root,
                host_log_root=host_log_root,
                source_host="fixture-l20",
                collected_at="2026-07-10T17:00:00+08:00",
            )
        e0_amendment = make_e0_amendment(snapshot)
        payload = build_payload(module, snapshot, e0_amendment)
        self.assertTrue(all(row["e0_binding"] == "bound" for row in payload["rows"]))
        self.assertEqual(
            {e0_artifact_id(row["dataset"], row["arm"]) for row in payload["rows"]},
            {row["e0_artifact_id"] for row in payload["rows"]},
        )

        checkpoint_drift = copy.deepcopy(e0_amendment)
        checkpoint_drift["rows"][0]["checkpoint_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "E0 checkpoint binding mismatch"):
            build_payload(module, snapshot, checkpoint_drift)

        metric_drift = copy.deepcopy(e0_amendment)
        metric_drift["rows"][0]["old_ndcg10"] += 0.01
        with self.assertRaisesRegex(ValueError, "E0 old p2 metric mismatch"):
            build_payload(module, snapshot, metric_drift)

    def test_refuses_to_overwrite_a_dated_report(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            core_root, run_root, host_log_root = create_fixture(root)
            snapshot = module.collect_snapshot(
                core_root=core_root,
                run_root=run_root,
                host_log_root=host_log_root,
                source_host="fixture-l20",
                collected_at="2026-07-10T17:00:00+08:00",
            )
            snapshot_path = root / "snapshot.json"
            write_json(snapshot_path, snapshot)
            e0_path = root / "e0_evaluator_amendment.json"
            write_json(e0_path, make_e0_amendment(snapshot))
            output_dir = root / "output"
            module.write_report(snapshot_path=snapshot_path, e0_amendment_path=e0_path, output_dir=output_dir)
            with self.assertRaisesRegex(FileExistsError, "refusing to overwrite"):
                module.write_report(snapshot_path=snapshot_path, e0_amendment_path=e0_path, output_dir=output_dir)

            bad_e0 = make_e0_amendment(snapshot)
            bad_e0["rows"][0]["checkpoint_sha256"] = "0" * 64
            bad_e0_path = root / "bad_e0.json"
            write_json(bad_e0_path, bad_e0)
            failed_output = root / "failed-output"
            with self.assertRaisesRegex(ValueError, "E0 checkpoint binding mismatch"):
                module.write_report(
                    snapshot_path=snapshot_path,
                    e0_amendment_path=bad_e0_path,
                    output_dir=failed_output,
                )
            self.assertFalse(failed_output.exists())


if __name__ == "__main__":
    unittest.main()
