#!/usr/bin/env python3

from __future__ import annotations

import argparse
import base64
import csv
from datetime import datetime
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import tempfile
from typing import Any


SCHEMA_VERSION = "aaai-e10-existing-artifacts-v1"
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
ARM_ORDER = ("host", "full", "u_shuffle", "text_anchor_only", "global_p")
EXPECTED_ARMS = {
    "Steam": ARM_ORDER,
    "ML1M": ("host", "full"),
    "Beauty": ARM_ORDER,
    "ATG": ("host", "full"),
}
STRENGTHS = ("p2", "p5", "p10")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
MONITOR_RE = re.compile(
    r"EARLY_STOP_MONITOR step=(?P<step>\d+) metric=(?P<metric>[^ ]+) "
    r"strength=(?P<strength>[^ ]+) value=(?P<value>\S+)"
)
BEST_RE = re.compile(
    r"BEST_RESULT step=(?P<step>\d+) metric=(?P<metric>[^ ]+) "
    r"value=(?P<value>\S+)"
)
OUTPUT_FILENAMES = (
    "e10_existing_artifact_snapshot.json",
    "e10_selector_strength_table.csv",
    "e10_selector_strength_report.json",
    "e10_selector_strength_report_zh.md",
    "provenance_manifest.json",
    "SHA256SUMS",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_record(path: Path, *, embed_content: bool) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    record: dict[str, Any] = {
        "path": str(path),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }
    if embed_content:
        record["content_b64"] = base64.b64encode(path.read_bytes()).decode("ascii")
    return record


def host_paths(core_root: Path, host_log_root: Path, dataset: str) -> dict[str, Path]:
    graph_type = CORE_TYPES[dataset]
    meta_dir = core_root / dataset
    return {
        "summary": meta_dir / f"best_summary_{graph_type}.json",
        "checkpoint": meta_dir / f"checkpoint_{graph_type}_best.pth",
        "log": host_log_root / f"{dataset.lower()}_{graph_type}_earlystop.log",
    }


def proposal_paths(run_root: Path, dataset: str, variant: str) -> dict[str, Path]:
    run_dir = run_root / f"{dataset.lower()}_proposal_adaptive_{variant}"
    meta_dir = run_dir / "checkpoints-meta" / dataset
    return {
        "run_dir": run_dir,
        "summary": meta_dir / "best_summary_proposal_adaptive.json",
        "checkpoint": meta_dir / "checkpoint_proposal_adaptive_best.pth",
        "manifest": meta_dir / "frozen_run_manifest.json",
    }


def host_selection_evidence(log_path: Path) -> dict[str, Any]:
    log_path = log_path.resolve()
    if not log_path.is_file():
        raise FileNotFoundError(log_path)
    first_monitor = None
    last_best = None
    for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if first_monitor is None and MONITOR_RE.search(line):
            first_monitor = line.strip()
        if BEST_RE.search(line):
            last_best = line.strip()
    if first_monitor is None or last_best is None:
        raise ValueError(f"host selection evidence missing from {log_path}")
    record = artifact_record(log_path, embed_content=True)
    record.update({
        "source": "log",
        "first_monitor_line": first_monitor,
        "last_best_result_line": last_best,
    })
    return record


def collect_snapshot(
    *,
    core_root: Path,
    run_root: Path,
    host_log_root: Path,
    source_host: str | None = None,
    collected_at: str | None = None,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for dataset in DATASETS:
        paths = host_paths(core_root, host_log_root, dataset)
        entries.append(
            {
                "dataset": dataset,
                "arm": "host",
                "artifact_role": "frozen_host",
                "summary": artifact_record(paths["summary"], embed_content=True),
                "checkpoint": artifact_record(paths["checkpoint"], embed_content=False),
                "manifest": None,
                "selection_evidence": host_selection_evidence(paths["log"]),
            }
        )

        proposal = proposal_paths(run_root, dataset, "mainpath")
        manifest = artifact_record(proposal["manifest"], embed_content=True)
        entries.append(
            {
                "dataset": dataset,
                "arm": "full",
                "artifact_role": "frozen_full",
                "run_dir": str(proposal["run_dir"].resolve()),
                "summary": artifact_record(proposal["summary"], embed_content=True),
                "checkpoint": artifact_record(proposal["checkpoint"], embed_content=False),
                "manifest": manifest,
                "selection_evidence": {
                    "source": "manifest",
                    "path": manifest["path"],
                    "sha256": manifest["sha256"],
                },
            }
        )

    for dataset in ("Beauty", "Steam"):
        for arm, variant in CONTROL_VARIANTS.items():
            proposal = proposal_paths(run_root, dataset, variant)
            manifest = artifact_record(proposal["manifest"], embed_content=True)
            entries.append(
                {
                    "dataset": dataset,
                    "arm": arm,
                    "artifact_role": "frozen_control",
                    "run_dir": str(proposal["run_dir"].resolve()),
                    "summary": artifact_record(proposal["summary"], embed_content=True),
                    "checkpoint": artifact_record(proposal["checkpoint"], embed_content=False),
                    "manifest": manifest,
                    "selection_evidence": {
                        "source": "manifest",
                        "path": manifest["path"],
                        "sha256": manifest["sha256"],
                    },
                }
            )

    return {
        "schema_version": SCHEMA_VERSION,
        "collected_at": collected_at or datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_host": source_host or platform.node(),
        "policy": {
            "existing_artifacts_only": True,
            "training_runs_launched": 0,
            "evaluation_runs_launched": 0,
            "checkpoint_reselection": False,
            "test_value_filtering": False,
        },
        "entries": entries,
    }


def validate_hash(record: dict[str, Any], label: str) -> None:
    if not HASH_RE.fullmatch(str(record.get("sha256", ""))):
        raise ValueError(f"invalid SHA-256 for {label}")
    if int(record.get("size_bytes", -1)) < 0:
        raise ValueError(f"invalid size for {label}")


def decode_raw_artifact(record: dict[str, Any], label: str) -> bytes:
    validate_hash(record, label)
    try:
        raw = base64.b64decode(record["content_b64"], validate=True)
    except (KeyError, ValueError) as exc:
        raise ValueError(f"hash-bound raw content required for {label}") from exc
    if len(raw) != int(record["size_bytes"]):
        raise ValueError(f"embedded content size mismatch for {label}")
    if hashlib.sha256(raw).hexdigest() != record["sha256"]:
        raise ValueError(f"embedded content hash mismatch for {label}")
    return raw


def decode_json_artifact(record: dict[str, Any], label: str) -> dict[str, Any]:
    raw = decode_raw_artifact(record, label)
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required for {label}")
    return payload


def compact_summary_payload(payload: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {
        "metric_name": payload.get("metric_name"),
        "best_step": payload.get("best_step"),
        "best_metric": payload.get("best_metric"),
        "validation": {},
        "test": {},
    }
    validation = payload.get("validation", {})
    if isinstance(validation, dict):
        for strength, block in validation.items():
            try:
                ndcg10 = block["ndcg"][2]
            except (KeyError, IndexError, TypeError):
                continue
            compact["validation"][strength] = {"ndcg": [None, None, ndcg10]}
    test = payload.get("test", {})
    if isinstance(test, dict):
        for strength in STRENGTHS:
            try:
                hr10 = test[strength]["hr"][2]
                ndcg10 = test[strength]["ndcg"][2]
            except (KeyError, IndexError, TypeError):
                continue
            compact["test"][strength] = {
                "hr": [None, None, hr10],
                "ndcg": [None, None, ndcg10],
            }
    return compact


def compact_manifest_payload(payload: dict[str, Any]) -> dict[str, Any]:
    config = payload.get("frozen_config", {})
    provenance = payload.get("provenance", {})
    return {
        "dataset": payload.get("dataset"),
        "random_seed": payload.get("random_seed"),
        "run_dir": payload.get("run_dir"),
        "bank_hash": payload.get("bank_hash"),
        "split_hash": payload.get("split_hash"),
        "frozen_config": {
            "ablation_mode": config.get("ablation_mode") if isinstance(config, dict) else None,
            "early_stop_metric": config.get("early_stop_metric") if isinstance(config, dict) else None,
            "early_stop_strength": config.get("early_stop_strength") if isinstance(config, dict) else None,
            "kernel_version": config.get("kernel_version") if isinstance(config, dict) else None,
        },
        "provenance": {
            "git_head": provenance.get("git_head") if isinstance(provenance, dict) else None,
            "repo_root": provenance.get("repo_root") if isinstance(provenance, dict) else None,
        },
    }


def compact_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Compact JSON whitespace without replacing hash-bound source bytes."""

    compact = json.loads(json.dumps(snapshot))
    for entry in compact.get("entries", []):
        decode_json_artifact(entry["summary"], f"{entry['dataset']}/{entry['arm']}/summary")
        manifest = entry.get("manifest")
        if isinstance(manifest, dict):
            decode_json_artifact(manifest, f"{entry['dataset']}/{entry['arm']}/manifest")
        if entry.get("arm") == "host":
            decode_raw_artifact(
                entry["selection_evidence"],
                f"{entry['dataset']}/host/selection-log",
            )
    compact["snapshot_encoding"] = "hash_bound_raw_artifacts_compact_json"
    return compact


def serialize_snapshot(snapshot: dict[str, Any], *, pretty: bool) -> str:
    if pretty:
        return json.dumps(snapshot, indent=2, ensure_ascii=False)
    return json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))


def validate_policy(snapshot: dict[str, Any]) -> None:
    if snapshot.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported E10 snapshot schema")
    policy = snapshot.get("policy", {})
    expected = {
        "existing_artifacts_only": True,
        "training_runs_launched": 0,
        "evaluation_runs_launched": 0,
        "checkpoint_reselection": False,
        "test_value_filtering": False,
    }
    for key, value in expected.items():
        if policy.get(key) != value:
            raise ValueError(f"E10 policy violation: {key}")


def validate_entry_matrix(entries: list[dict[str, Any]]) -> None:
    actual = [(str(entry.get("dataset")), str(entry.get("arm"))) for entry in entries]
    if len(actual) != len(set(actual)):
        raise ValueError("duplicate dataset/arm entry")
    expected = {
        (dataset, arm)
        for dataset, arms in EXPECTED_ARMS.items()
        for arm in arms
    }
    if set(actual) != expected:
        missing = sorted(expected - set(actual))
        extra = sorted(set(actual) - expected)
        raise ValueError(f"selected artifact matrix mismatch: missing={missing}, extra={extra}")


def selector_from_entry(
    entry: dict[str, Any],
    summary: dict[str, Any],
) -> tuple[str, str, dict[str, Any] | None]:
    dataset = str(entry["dataset"])
    arm = str(entry["arm"])
    evidence = entry.get("selection_evidence", {})
    if arm == "host":
        if entry.get("manifest") is not None:
            raise ValueError(f"unexpected host manifest for {dataset}")
        if evidence.get("source") != "log":
            raise ValueError(f"host validation selector evidence missing for {dataset}")
        log_text = decode_raw_artifact(evidence, f"{dataset}/host/selection-log").decode("utf-8", errors="ignore")
        first_monitor_line = next((line.strip() for line in log_text.splitlines() if MONITOR_RE.search(line)), "")
        best_lines = [line.strip() for line in log_text.splitlines() if BEST_RE.search(line)]
        best_line = best_lines[-1] if best_lines else ""
        monitor = MONITOR_RE.search(first_monitor_line)
        best = BEST_RE.search(best_line)
        if monitor is None or best is None:
            raise ValueError(f"host validation selector evidence missing for {dataset}")
        if evidence.get("first_monitor_line") != first_monitor_line or evidence.get("last_best_result_line") != best_line:
            raise ValueError(f"host selector evidence extraction mismatch for {dataset}")
        if "summary=" not in best_line or Path(best_line.rsplit("summary=", 1)[1]).name != Path(
            str(entry["summary"]["path"])
        ).name:
            raise ValueError(f"host selector evidence does not bind summary for {dataset}")
        if int(best.group("step")) != int(summary.get("best_step", -1)):
            raise ValueError(f"best checkpoint step mismatch for {dataset}/host")
        if best.group("metric") != str(summary.get("metric_name")):
            raise ValueError(f"best checkpoint metric mismatch for {dataset}/host")
        finite_unit_value(monitor.group("value"), f"host EARLY_STOP_MONITOR for {dataset}")
        host_best_value = finite_unit_value(best.group("value"), f"host BEST_RESULT for {dataset}")
        if abs(host_best_value - finite_unit_value(summary.get("best_metric"), f"best_metric for {dataset}/host")) > 5e-7:
            raise ValueError(f"best checkpoint value mismatch for {dataset}/host")
        metric = monitor.group("metric")
        strength = monitor.group("strength")
        return metric, strength, None

    manifest_record = entry.get("manifest")
    if not isinstance(manifest_record, dict):
        raise ValueError(f"manifest required for {dataset}/{arm}")
    manifest = decode_json_artifact(manifest_record, f"{dataset}/{arm}/manifest")
    if evidence.get("source") != "manifest":
        raise ValueError(f"manifest selector evidence required for {dataset}/{arm}")
    if evidence.get("path") != manifest_record.get("path") or evidence.get("sha256") != manifest_record.get("sha256"):
        raise ValueError(f"selector evidence does not bind manifest for {dataset}/{arm}")
    if str(manifest.get("dataset")) != dataset:
        raise ValueError(f"manifest dataset mismatch for {dataset}/{arm}")
    if str(manifest.get("run_dir")) != str(entry.get("run_dir")):
        raise ValueError(f"manifest run_dir mismatch for {dataset}/{arm}")
    config = manifest.get("frozen_config", {})
    if not isinstance(config, dict):
        raise ValueError(f"frozen_config required for {dataset}/{arm}")
    expected_ablation = "none" if arm == "full" else arm
    if str(config.get("ablation_mode")) != expected_ablation:
        raise ValueError(f"manifest ablation mismatch for {dataset}/{arm}")
    metric = str(config.get("early_stop_metric", ""))
    strength = str(config.get("early_stop_strength", ""))
    return metric, strength, manifest


def metric_at_10(summary: dict[str, Any], strength: str, metric: str) -> float | None:
    try:
        value = float(summary["test"][strength][metric][2])
    except (KeyError, IndexError, TypeError, ValueError):
        return None
    return value


def format_number(value: float | None) -> str:
    if value is None:
        return "NA"
    return f"{value:.15g}"


def finite_unit_value(value: object, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"nonfinite {label}") from exc
    if not math.isfinite(number):
        raise ValueError(f"nonfinite {label}")
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{label} out of range")
    return number


def output_or_na(value: object, field_id: str, missing_fields: list[str]) -> str:
    if value is None or (isinstance(value, str) and not value.strip()):
        missing_fields.append(field_id)
        return "NA"
    return str(value)


def validate_metric_pair(hr10: float | None, ndcg10: float | None, label: str) -> None:
    if hr10 is not None:
        finite_unit_value(hr10, f"{label}/hr10")
    if ndcg10 is not None:
        finite_unit_value(ndcg10, f"{label}/ndcg10")
    if hr10 is not None and ndcg10 is not None and ndcg10 > hr10:
        raise ValueError(f"metric range/order violation for {label}")


def build_row(entry: dict[str, Any], missing_fields: list[str]) -> dict[str, Any]:
    dataset = str(entry["dataset"])
    arm = str(entry["arm"])
    summary_record = entry.get("summary")
    checkpoint_record = entry.get("checkpoint")
    if not isinstance(summary_record, dict) or not isinstance(checkpoint_record, dict):
        raise ValueError(f"summary and checkpoint required for {dataset}/{arm}")
    summary = decode_json_artifact(summary_record, f"{dataset}/{arm}/summary")
    validate_hash(checkpoint_record, f"{dataset}/{arm}/checkpoint")
    if Path(str(summary_record.get("path", ""))).parent != Path(str(checkpoint_record.get("path", ""))).parent:
        raise ValueError(f"summary/checkpoint directory mismatch for {dataset}/{arm}")

    expected_checkpoint = (
        f"checkpoint_{CORE_TYPES[dataset]}_best.pth"
        if arm == "host"
        else "checkpoint_proposal_adaptive_best.pth"
    )
    if Path(str(checkpoint_record.get("path", ""))).name != expected_checkpoint:
        raise ValueError(f"selected checkpoint path mismatch for {dataset}/{arm}")

    best_step = summary.get("best_step")
    if isinstance(best_step, bool) or not isinstance(best_step, int) or best_step < 0:
        raise ValueError(f"nonnegative best_step required for {dataset}/{arm}")
    best_metric = finite_unit_value(summary.get("best_metric"), f"best_metric for {dataset}/{arm}")

    selector_metric, selector_strength, manifest = selector_from_entry(entry, summary)
    if selector_metric != "ndcg10" or selector_strength not in ("base", *STRENGTHS):
        raise ValueError(f"validation-only selector required for {dataset}/{arm}")
    try:
        selected_validation_raw = summary["validation"][selector_strength]["ndcg"][2]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"selector readout missing for {dataset}/{arm}") from exc
    selected_validation_value = finite_unit_value(
        selected_validation_raw,
        f"selected validation for {dataset}/{arm}",
    )
    if abs(selected_validation_value - best_metric) > 1e-12:
        raise ValueError(f"best_metric does not bind selected validation readout for {dataset}/{arm}")

    row: dict[str, Any] = {
        "dataset": dataset,
        "arm": arm,
        "artifact_role": str(entry.get("artifact_role", "NA")),
        "selected_checkpoint": str(checkpoint_record["path"]),
        "selector_metric": f"validation_{selector_strength}_{selector_metric}",
        "selector_source": str(entry.get("selection_evidence", {}).get("source", "NA")),
        "best_step": best_step,
        "best_metric": format_number(best_metric),
        "summary_path": str(summary_record["path"]),
        "summary_sha256": str(summary_record["sha256"]),
        "checkpoint_sha256": str(checkpoint_record["sha256"]),
        "manifest_path": "NA",
        "manifest_sha256": "NA",
        "provenance_git_head": "NA",
        "provenance_repo_root": "NA",
        "random_seed": "NA",
        "split_hash": "NA",
        "bank_hash": "NA",
        "selection_evidence_path": str(entry.get("selection_evidence", {}).get("path", "NA")),
        "selection_evidence_sha256": str(entry.get("selection_evidence", {}).get("sha256", "NA")),
        "metric_contract": "archived_best_summary_legacy_tail_skip",
    }
    if manifest is not None:
        manifest_record = entry["manifest"]
        provenance = manifest.get("provenance", {})
        row.update(
            {
                "manifest_path": output_or_na(manifest_record.get("path"), f"{dataset}/{arm}:manifest/path", missing_fields),
                "manifest_sha256": output_or_na(manifest_record.get("sha256"), f"{dataset}/{arm}:manifest/sha256", missing_fields),
                "provenance_git_head": output_or_na(provenance.get("git_head"), f"{dataset}/{arm}:manifest/provenance/git_head", missing_fields),
                "provenance_repo_root": output_or_na(provenance.get("repo_root"), f"{dataset}/{arm}:manifest/provenance/repo_root", missing_fields),
                "random_seed": output_or_na(manifest.get("random_seed"), f"{dataset}/{arm}:manifest/random_seed", missing_fields),
                "split_hash": output_or_na(manifest.get("split_hash"), f"{dataset}/{arm}:manifest/split_hash", missing_fields),
                "bank_hash": output_or_na(manifest.get("bank_hash"), f"{dataset}/{arm}:manifest/bank_hash", missing_fields),
            }
        )
    else:
        missing_fields.extend(
            [
                f"{dataset}/{arm}:manifest/path",
                f"{dataset}/{arm}:manifest/sha256",
                f"{dataset}/{arm}:manifest/provenance/git_head",
                f"{dataset}/{arm}:manifest/provenance/repo_root",
                f"{dataset}/{arm}:manifest/random_seed",
                f"{dataset}/{arm}:manifest/split_hash",
                f"{dataset}/{arm}:manifest/bank_hash",
            ]
        )

    for strength in STRENGTHS:
        hr10 = metric_at_10(summary, strength, "hr")
        ndcg10 = metric_at_10(summary, strength, "ndcg")
        validate_metric_pair(hr10, ndcg10, f"{dataset}/{arm}/test/{strength}")
        row[f"test_{strength}_hr10"] = format_number(hr10)
        row[f"test_{strength}_ndcg10"] = format_number(ndcg10)
        if hr10 is None:
            missing_fields.append(f"{dataset}/{arm}:test/{strength}/hr10")
        if ndcg10 is None:
            missing_fields.append(f"{dataset}/{arm}:test/{strength}/ndcg10")
    return row


def numeric(row: dict[str, Any], field: str) -> float | None:
    value = row.get(field, "NA")
    if value == "NA":
        return None
    return float(value)


def e0_artifact_id(dataset: str, arm: str) -> str:
    token = dataset.lower()
    if arm == "host":
        return f"host_{token}"
    if arm == "full":
        return f"ours_full_{token}"
    return f"{arm}_{token}"


def bind_rows_to_e0(
    rows: list[dict[str, Any]],
    e0_amendment: dict[str, Any],
) -> None:
    matrix = e0_amendment.get("matrix_validation", {})
    if not isinstance(matrix, dict) or matrix.get("all_contract_checks_pass") is not True:
        raise ValueError("complete E0 amendment contract required")
    e0_rows = e0_amendment.get("rows")
    if not isinstance(e0_rows, list):
        raise ValueError("E0 amendment rows required")
    by_id: dict[str, dict[str, Any]] = {}
    for item in e0_rows:
        if not isinstance(item, dict):
            raise ValueError("E0 amendment row must be an object")
        artifact_id = str(item.get("artifact_id", ""))
        if not artifact_id or artifact_id in by_id:
            raise ValueError("unique E0 artifact_id required")
        by_id[artifact_id] = item

    for row in rows:
        artifact_id = e0_artifact_id(str(row["dataset"]), str(row["arm"]))
        e0_row = by_id.get(artifact_id)
        if e0_row is None or str(e0_row.get("dataset")) != str(row["dataset"]):
            raise ValueError(f"E0 artifact binding missing for {artifact_id}")
        checkpoint_matches = (
            str(e0_row.get("checkpoint_path")) == str(row["selected_checkpoint"])
            and str(e0_row.get("checkpoint_sha256")) == str(row["checkpoint_sha256"])
        )
        if not checkpoint_matches:
            raise ValueError(f"E0 checkpoint binding mismatch for {artifact_id}")
        summary_matches = (
            str(e0_row.get("summary_path")) == str(row["summary_path"])
            and str(e0_row.get("summary_sha256")) == str(row["summary_sha256"])
        )
        if not summary_matches:
            raise ValueError(f"E0 summary binding mismatch for {artifact_id}")

        old_hr10 = finite_unit_value(e0_row.get("old_hr10"), f"E0 old_hr10 for {artifact_id}")
        old_ndcg10 = finite_unit_value(e0_row.get("old_ndcg10"), f"E0 old_ndcg10 for {artifact_id}")
        archived_hr10 = numeric(row, "test_p2_hr10")
        archived_ndcg10 = numeric(row, "test_p2_ndcg10")
        if (
            archived_hr10 is None
            or archived_ndcg10 is None
            or abs(archived_hr10 - old_hr10) > 1e-12
            or abs(archived_ndcg10 - old_ndcg10) > 1e-12
        ):
            raise ValueError(f"E0 old p2 metric mismatch for {artifact_id}")

        row.update(
            {
                "e0_artifact_id": artifact_id,
                "e0_binding": "bound",
                "e0_corrected_hr10": format_number(
                    finite_unit_value(e0_row.get("corrected_hr10"), f"E0 corrected_hr10 for {artifact_id}")
                ),
                "e0_corrected_ndcg10": format_number(
                    finite_unit_value(e0_row.get("corrected_ndcg10"), f"E0 corrected_ndcg10 for {artifact_id}")
                ),
            }
        )


def find_strict_reversals(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reversals: list[dict[str, Any]] = []
    for dataset in DATASETS:
        dataset_rows = {row["arm"]: row for row in rows if row["dataset"] == dataset}
        arms = [arm for arm in EXPECTED_ARMS[dataset] if arm in dataset_rows]
        for arm_a, arm_b in itertools.combinations(arms, 2):
            for field_suffix, metric_name in (("hr10", "HR@10"), ("ndcg10", "NDCG@10")):
                deltas: dict[str, float] = {}
                for strength in STRENGTHS:
                    left = numeric(dataset_rows[arm_a], f"test_{strength}_{field_suffix}")
                    right = numeric(dataset_rows[arm_b], f"test_{strength}_{field_suffix}")
                    if left is not None and right is not None:
                        deltas[strength] = left - right
                signs = {1 if value > 0 else -1 for value in deltas.values() if value != 0.0}
                if signs == {-1, 1}:
                    reversals.append(
                        {
                            "dataset": dataset,
                            "metric": metric_name,
                            "arm_a": arm_a,
                            "arm_b": arm_b,
                            "strengths": list(deltas),
                            "deltas_arm_a_minus_arm_b": deltas,
                            "interpretation": "strength_sensitivity_only_primary_selector_unchanged",
                        }
                    )
    return reversals


def build_report_payload(
    snapshot: dict[str, Any],
    e0_amendment: dict[str, Any],
) -> dict[str, Any]:
    validate_policy(snapshot)
    entries = snapshot.get("entries")
    if not isinstance(entries, list):
        raise ValueError("entries must be a list")
    validate_entry_matrix(entries)
    missing_fields: list[str] = []
    rows = [build_row(entry, missing_fields) for entry in entries]
    bind_rows_to_e0(rows, e0_amendment)
    dataset_rank = {name: index for index, name in enumerate(DATASETS)}
    arm_rank = {name: index for index, name in enumerate(ARM_ORDER)}
    rows.sort(key=lambda row: (dataset_rank[row["dataset"]], arm_rank[row["arm"]]))
    reversals = find_strict_reversals(rows)
    return {
        "schema_version": "aaai-e10-selector-strength-report-v1",
        "generated_from_snapshot_schema": snapshot["schema_version"],
        "collected_at": snapshot.get("collected_at", "NA"),
        "source_host": snapshot.get("source_host", "NA"),
        "policy": snapshot["policy"],
        "scope": {
            "datasets": list(DATASETS),
            "row_count": len(rows),
            "checkpoint_selection": "frozen_validation_only",
            "strengths_are_same_checkpoint_test_readouts": True,
            "alternative_selector_sweep_used": False,
            "alternative_selector_sweep_exclusion": (
                "analyze_selector_sweep.py selects separate steps for alternative validation selectors and "
                "also emits best-test checkpoints; both are outside the frozen-checkpoint E10 contract"
            ),
            "evaluator_contract": "archived legacy best-summary readouts; not E0-corrected Table 2 values",
            "e0_binding": "checkpoint, summary, and legacy p2 readout cross-bound to dated E0 amendment",
        },
        "rows": rows,
        "missing_fields": missing_fields,
        "e0_amendment": {
            "report_name": output_or_na(e0_amendment.get("report_name"), "E0:report_name", missing_fields),
            "matrix_contract_pass": True,
        },
        "strength_sensitivity": {
            "primary_selectors_unchanged": True,
            "strict_pairwise_reversals": reversals,
        },
    }


CSV_FIELDS = (
    "dataset",
    "arm",
    "artifact_role",
    "selected_checkpoint",
    "selector_metric",
    "selector_source",
    "best_step",
    "best_metric",
    "test_p2_hr10",
    "test_p2_ndcg10",
    "test_p5_hr10",
    "test_p5_ndcg10",
    "test_p10_hr10",
    "test_p10_ndcg10",
    "summary_path",
    "summary_sha256",
    "checkpoint_sha256",
    "manifest_path",
    "manifest_sha256",
    "provenance_git_head",
    "provenance_repo_root",
    "random_seed",
    "split_hash",
    "bank_hash",
    "selection_evidence_path",
    "selection_evidence_sha256",
    "metric_contract",
    "e0_artifact_id",
    "e0_binding",
    "e0_corrected_hr10",
    "e0_corrected_ndcg10",
)


def markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# AAAI-E10 既有工件 selector-strength 审计",
        "",
        f"_采集时间：`{payload['collected_at']}`；来源主机：`{payload['source_host']}`_",
        "",
        "---",
        "",
        "## 📋 口径与边界",
        "",
        "- 本报告只枚举已经冻结的 host、full 与 SPRINT-07 control best checkpoint、best summary 和 manifest。",
        "- 本次未启动训练，未启动 evaluation-selection run，未重选 checkpoint，也未按 test 数值筛选。",
        "- `analyze_selector_sweep.py` 未执行：该脚本会按替代 validation selector 另选 step，并生成 best-test checkpoint 汇总，不符合 E10 的冻结 checkpoint 边界。",
        "- 每行的 `p2/p5/p10` 都是同一个 validation-selected checkpoint 上记录的 test readout；冻结的 primary selector 不变。",
        "- 数字来自旧 evaluator 生成的 archived best summary，不能当作 E0 修正后的 Table 2 数字。",
        "- 下列顺序翻转仅作 strength sensitivity；它们不授权改变 selector、补跑或追加 seed。",
        "",
        "## 📊 固定 checkpoint 强度读数",
        "",
    ]
    for dataset in DATASETS:
        lines.extend(
            [
                f"### {dataset}",
                "",
                "| Arm | Validation selector | Best step | p2 HR / NDCG | p5 HR / NDCG | p10 HR / NDCG |",
                "| --- | --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in payload["rows"]:
            if row["dataset"] != dataset:
                continue
            lines.append(
                "| {arm} | `{selector_metric}` | {best_step} | {test_p2_hr10} / {test_p2_ndcg10} | "
                "{test_p5_hr10} / {test_p5_ndcg10} | {test_p10_hr10} / {test_p10_ndcg10} |".format(**row)
            )
        lines.append("")

    reversals = payload["strength_sensitivity"]["strict_pairwise_reversals"]
    lines.extend(
        [
            "## 🔍 Strength sensitivity",
            "",
            f"严格 pairwise 顺序翻转共 `{len(reversals)}` 项。这里的“翻转”仅表示同一对既选 checkpoint 的差值在 p2/p5/p10 间出现严格正负号变化。",
            "",
        ]
    )
    if reversals:
        lines.extend(
            [
                "| Dataset | Metric | Comparison | p2 Δ | p5 Δ | p10 Δ |",
                "| --- | --- | --- | ---: | ---: | ---: |",
            ]
        )
        for item in reversals:
            deltas = item["deltas_arm_a_minus_arm_b"]
            lines.append(
                f"| {item['dataset']} | {item['metric']} | {item['arm_a']} − {item['arm_b']} | "
                f"{format_number(deltas.get('p2'))} | {format_number(deltas.get('p5'))} | "
                f"{format_number(deltas.get('p10'))} |"
            )
    else:
        lines.append("没有可报告的严格顺序翻转。")
    lines.extend(
        [
            "",
            "## 📦 Provenance 与缺失字段",
            "",
            "完整 checkpoint/summary/manifest 路径、SHA-256、git revision、split/bank hash 与 selector 证据见同目录 CSV 和 JSON。",
            "",
        ]
    )
    if payload["missing_fields"]:
        lines.append("既有工件缺失的 strength readout 已写为 `NA`：")
        lines.append("")
        lines.extend(f"- `{field}`" for field in payload["missing_fields"])
    else:
        lines.append("本次枚举的 14 个 best summary 均含 p2/p5/p10 HR@10 与 NDCG@10 readout；host manifest 仍按事实写为 `NA`。")
    lines.append("")
    return "\n".join(lines)


def provenance_record(record: dict[str, Any], label: str) -> dict[str, Any]:
    validate_hash(record, label)
    return {
        "label": label,
        "path": str(record.get("path")),
        "sha256": str(record.get("sha256")),
        "size_bytes": int(record.get("size_bytes", -1)),
    }


def source_artifact_records(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for entry in snapshot["entries"]:
        dataset = str(entry["dataset"])
        arm = str(entry["arm"])
        records.append(provenance_record(entry["summary"], f"{dataset}/{arm}/summary"))
        records.append(provenance_record(entry["checkpoint"], f"{dataset}/{arm}/checkpoint"))
        if arm == "host":
            records.append(
                provenance_record(entry["selection_evidence"], f"{dataset}/{arm}/selection_log")
            )
        else:
            records.append(provenance_record(entry["manifest"], f"{dataset}/{arm}/manifest"))
    if len(records) != 42:
        raise ValueError(f"expected 42 source artifacts, found {len(records)}")
    return records


def write_report(
    *,
    snapshot_path: Path,
    e0_amendment_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite dated report: {output_dir}")

    snapshot_path = snapshot_path.resolve()
    e0_amendment_path = e0_amendment_path.resolve()
    snapshot_raw = snapshot_path.read_bytes()
    e0_raw = e0_amendment_path.read_bytes()
    snapshot = json.loads(snapshot_raw.decode("utf-8"))
    e0_amendment = json.loads(e0_raw.decode("utf-8"))
    if not isinstance(snapshot, dict) or not isinstance(e0_amendment, dict):
        raise ValueError("snapshot and E0 amendment must be JSON objects")
    payload = build_report_payload(snapshot, e0_amendment)
    source_records = source_artifact_records(snapshot)
    provenance = {
        "schema_version": "aaai-e10-selector-strength-provenance-v1",
        "source_artifact_count": len(source_records),
        "source_artifacts": source_records,
        "collector": {
            "script_path": str(Path(__file__).resolve()),
            "script_sha256": sha256_file(Path(__file__).resolve()),
        },
        "source_snapshot": {
            "path": str(snapshot_path),
            "sha256": hashlib.sha256(snapshot_raw).hexdigest(),
            "size_bytes": len(snapshot_raw),
        },
        "e0_amendment": {
            "path": str(e0_amendment_path),
            "sha256": hashlib.sha256(e0_raw).hexdigest(),
            "size_bytes": len(e0_raw),
        },
        "policy": payload["policy"],
    }

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(
        tempfile.mkdtemp(prefix=".e10-selector-strength-staging-", dir=str(output_dir.parent))
    )
    try:
        paths = {name: staging_dir / name for name in OUTPUT_FILENAMES}
        paths["e10_existing_artifact_snapshot.json"].write_bytes(snapshot_raw)
        with paths["e10_selector_strength_table.csv"].open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(payload["rows"])
        paths["e10_selector_strength_report.json"].write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        paths["e10_selector_strength_report_zh.md"].write_text(
            markdown_report(payload),
            encoding="utf-8",
        )
        paths["provenance_manifest.json"].write_text(
            json.dumps(provenance, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        sum_lines = []
        for path in sorted(staging_dir.iterdir()):
            if path.is_file() and path.name != "SHA256SUMS":
                sum_lines.append(f"{sha256_file(path)}  {path.name}")
        paths["SHA256SUMS"].write_text("\n".join(sum_lines) + "\n", encoding="utf-8")
        os.rename(staging_dir, output_dir)
    except Exception:
        if staging_dir.exists() and staging_dir.parent.resolve() == output_dir.parent.resolve():
            shutil.rmtree(staging_dir)
        raise
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect and report AAAI-E10 existing selector-strength artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect = subparsers.add_parser("collect", help="Read frozen artifacts and emit a JSON snapshot to stdout.")
    collect.add_argument("--core-root", type=Path, default=Path("/data/Zijian/goal/RecDemo/checkpoints-meta"))
    collect.add_argument(
        "--run-root",
        type=Path,
        default=Path("/data/Zijian/goal/RecDemoRuns/main_table_text_side"),
    )
    collect.add_argument("--host-log-root", type=Path, default=Path("/data/Zijian/goal/RecDemo/logs"))
    collect.add_argument("--source-host")
    collect.add_argument("--collected-at")
    collect.add_argument(
        "--compact",
        action="store_true",
        help="Emit only report-required readouts while retaining remote artifact hashes.",
    )

    build = subparsers.add_parser("build", help="Build CSV/JSON/Chinese report from a collected snapshot.")
    build.add_argument("--snapshot", type=Path, required=True)
    build.add_argument("--e0-amendment", type=Path, required=True)
    build.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "collect":
        snapshot = collect_snapshot(
            core_root=args.core_root,
            run_root=args.run_root,
            host_log_root=args.host_log_root,
            source_host=args.source_host,
            collected_at=args.collected_at,
        )
        if args.compact:
            snapshot = compact_snapshot(snapshot)
        print(serialize_snapshot(snapshot, pretty=not args.compact))
        return
    payload = write_report(
        snapshot_path=args.snapshot,
        e0_amendment_path=args.e0_amendment,
        output_dir=args.output_dir,
    )
    print(f"WROTE {args.output_dir.resolve()} rows={len(payload['rows'])}")


if __name__ == "__main__":
    main()
