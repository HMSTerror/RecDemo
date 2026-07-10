#!/usr/bin/env python3
"""Build the fail-closed dated E0 common-evaluator amendment package."""

from __future__ import annotations

import argparse
import ctypes
import csv
import errno
import hashlib
import json
import math
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT / "docs" / "reports" / "data" / "2026-07-10-evaluator-amendment"
)
DEFAULT_GATE0_ORIGINAL = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "data"
    / "2026-07-02-gate0"
    / "gate0_u_tilde_report.json"
)
DEFAULT_GATE0_V2 = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "data"
    / "2026-07-02-gate0"
    / "gate0_v2_frozen_verdict.json"
)
DEFAULT_GATE1_REPORT = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "data"
    / "2026-07-06-gate1"
    / "sprint05_gate1_report.json"
)
DEFAULT_DIFFUREC_COMPARISON = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "data"
    / "2026-07-07-close04-diffurec"
    / "close04_diffurec_comparison.csv"
)

EXPECTED_ROWS = {
    "Steam": 80651,
    "ML1M": 85405,
    "Beauty": 2237,
    "ATG": 1942,
}

EXPECTED_CATALOG_ITEMS = {
    "Steam": 9265,
    "ML1M": 3706,
    "Beauty": 12101,
    "ATG": 11921,
}

EXPECTED_MATRIX = (
    ("host_steam", "Steam"),
    ("host_ml1m", "ML1M"),
    ("host_beauty", "Beauty"),
    ("host_atg", "ATG"),
    ("ours_full_steam", "Steam"),
    ("ours_full_ml1m", "ML1M"),
    ("ours_full_beauty", "Beauty"),
    ("ours_full_atg", "ATG"),
    ("global_p_steam", "Steam"),
    ("u_shuffle_steam", "Steam"),
    ("text_anchor_only_steam", "Steam"),
    ("global_p_beauty", "Beauty"),
    ("u_shuffle_beauty", "Beauty"),
    ("text_anchor_only_beauty", "Beauty"),
    ("diffurec_steam", "Steam"),
    ("diffurec_ml1m", "ML1M"),
    ("diffurec_beauty", "Beauty"),
    ("diffurec_atg", "ATG"),
)

EXPECTED_SHARD_ITEMS = {
    0: (
        "host_beauty",
        "diffurec_steam",
        "host_steam",
        "ours_full_steam",
        "global_p_steam",
        "u_shuffle_steam",
        "text_anchor_only_steam",
        "ours_full_beauty",
        "global_p_beauty",
        "u_shuffle_beauty",
        "text_anchor_only_beauty",
    ),
    1: (
        "diffurec_beauty",
        "diffurec_ml1m",
        "diffurec_atg",
        "host_ml1m",
        "ours_full_ml1m",
        "host_atg",
        "ours_full_atg",
    ),
}

CSV_FIELDS = (
    "artifact_id",
    "method_family",
    "dataset",
    "old_hr10",
    "corrected_hr10",
    "delta_hr10_corrected_minus_old",
    "old_ndcg10",
    "corrected_ndcg10",
    "delta_ndcg10_corrected_minus_old",
    "expected_rows",
    "evaluated_rows",
    "metric_contract_version",
    "candidate_policy",
    "valid_item_count",
    "model_item_count",
    "non_candidate_model_item_slots",
    "legacy_model_catalog_mismatch_authorized",
    "history_pad_semantics",
    "random_seed",
    "eval_seed",
    "checkpoint_selector_protocol",
    "selection_bias_not_recomputed",
    "evaluation_artifact_path",
    "evaluation_artifact_sha256",
    "summary_path",
    "summary_sha256",
    "checkpoint_path",
    "checkpoint_sha256",
    "log_path",
    "log_sha256",
    "manifest_path",
    "manifest_sha256",
    "split_path",
    "split_sha256",
)

START_RE = re.compile(
    r"^E0_SHARD_START shard=(\d+) gpu=(\d+) code_revision=([0-9a-f]{40})$",
    re.MULTILINE,
)
DONE_RE = re.compile(r"^E0_SHARD_DONE shard=(\d+) gpu=(\d+)$", re.MULTILINE)
FINISH_RE = re.compile(
    r"^E0_ITEM_FINISH id=([a-z0-9_]+) dataset=([A-Za-z0-9]+) family=(core|diffurec)$",
    re.MULTILINE,
)
ITEM_START_RE = re.compile(
    r"^E0_ITEM_START id=([a-z0-9_]+) dataset=([A-Za-z0-9]+) family=(core|diffurec)$"
)
OUTPUT_PATH_RE = re.compile(r'^\s*"output_path":\s*"([^"]+e0_eval\.json)"\s*,?\s*$')
LIFECYCLE_RE = re.compile(
    r"^(?:E0_SHARD_(?:START|DONE)|E0_ITEM_(?:START|FINISH))\b.*$", re.MULTILINE
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def publish_directory_no_clobber(staging_dir: Path, output_dir: Path) -> None:
    """Atomically publish a directory without replacing an existing destination."""
    staging_dir = Path(staging_dir)
    output_dir = Path(output_dir)
    if os.name == "nt":
        os.rename(staging_dir, output_dir)
        return
    if sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        try:
            renameat2 = libc.renameat2
        except AttributeError as exc:
            raise RuntimeError("atomic no-replace publication requires renameat2") from exc
        renameat2.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameat2.restype = ctypes.c_int
        result = renameat2(
            -100,
            os.fsencode(staging_dir),
            -100,
            os.fsencode(output_dir),
            1,
        )
        if result == 0:
            return
        error_number = ctypes.get_errno()
        if error_number in (errno.EEXIST, errno.ENOTEMPTY):
            raise FileExistsError(
                error_number, os.strerror(error_number), str(output_dir)
            )
        raise OSError(error_number, os.strerror(error_number), str(output_dir))
    raise RuntimeError(
        "atomic no-replace directory publication is unsupported on {}".format(sys.platform)
    )


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def require_sha256(value: object, label: str) -> str:
    text = str(value).lower()
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise ValueError("{} is not a SHA-256 digest: {!r}".format(label, value))
    return text


def resolve_source_path(raw_path: object, evaluation_path: Path) -> Path:
    path = Path(str(raw_path))
    if path.is_absolute():
        return path
    return (evaluation_path.parent / path).resolve()


def verify_source_hash(
    path: Path,
    expected_hash: object,
    label: str,
    cache: Dict[str, str],
) -> str:
    path = Path(path)
    if not path.is_file():
        raise ValueError("missing source file for {}: {}".format(label, path))
    expected = require_sha256(expected_hash, label + " hash")
    cache_key = str(path.resolve())
    actual = cache.get(cache_key)
    if actual is None:
        actual = sha256_file(path)
        cache[cache_key] = actual
    if actual != expected:
        raise ValueError(
            "source hash mismatch for {}: expected {}, got {}".format(label, expected, actual)
        )
    return actual


def method_family(artifact_id: str) -> str:
    if artifact_id.startswith("host_"):
        return "host"
    if artifact_id.startswith("ours_full_"):
        return "ours"
    if artifact_id.startswith("diffurec_"):
        return "DiffuRec"
    return "control"


def collect_evaluation_paths(input_root: Path) -> Dict[str, Path]:
    found: Dict[str, Path] = {}
    for path in sorted(Path(input_root).rglob("*e0_eval.json")):
        artifact_id = path.parent.name
        if artifact_id in found:
            raise ValueError("duplicate E0 artifact id: {}".format(artifact_id))
        found[artifact_id] = path
    expected_ids = {artifact_id for artifact_id, _ in EXPECTED_MATRIX}
    actual_ids = set(found)
    if actual_ids != expected_ids:
        raise ValueError(
            "E0 matrix mismatch: expected 18 artifacts; missing={}; unexpected={}".format(
                sorted(expected_ids - actual_ids), sorted(actual_ids - expected_ids)
            )
        )
    return found


def validate_execution_logs(execution_log_paths: Sequence[Path]) -> Dict[str, Any]:
    if len(execution_log_paths) != 2:
        raise ValueError("exactly two E0 execution logs are required")
    by_shard: Dict[int, Dict[str, Any]] = {}
    revisions = set()
    for raw_path in execution_log_paths:
        path = Path(raw_path)
        text = path.read_text(encoding="utf-8", errors="strict")
        starts = list(START_RE.finditer(text))
        dones = list(DONE_RE.finditer(text))
        if len(starts) != 1:
            raise ValueError("execution log must contain exactly one E0_SHARD_START: {}".format(path))
        if len(dones) != 1:
            raise ValueError("execution log must contain exactly one E0_SHARD_DONE: {}".format(path))
        start = starts[0]
        done = dones[0]
        lifecycle = list(LIFECYCLE_RE.finditer(text))
        if (
            not lifecycle
            or lifecycle[0].start() != start.start()
            or lifecycle[-1].start() != done.start()
            or start.start() >= done.start()
        ):
            raise ValueError("execution lifecycle order violation in {}".format(path))
        shard = int(start.group(1))
        gpu = int(start.group(2))
        revision = start.group(3)
        if (int(done.group(1)), int(done.group(2))) != (shard, gpu):
            raise ValueError("E0_SHARD_DONE does not match E0_SHARD_START in {}".format(path))
        if shard in by_shard:
            raise ValueError("duplicate E0 execution log for shard {}".format(shard))
        if re.search(r"Traceback \(most recent call last\)|^RuntimeError:", text, re.MULTILINE):
            raise ValueError("execution log contains a runtime failure: {}".format(path))

        finishes: List[Tuple[str, str, str]] = []
        output_paths: Dict[str, str] = {}
        active_item: Optional[Dict[str, str]] = None
        for line in text.splitlines():
            start_match = ITEM_START_RE.fullmatch(line)
            if start_match:
                if active_item is not None:
                    raise ValueError(
                        "nested E0_ITEM_START before E0_ITEM_FINISH in {}".format(path)
                    )
                active_item = {
                    "artifact_id": start_match.group(1),
                    "dataset": start_match.group(2),
                    "family": start_match.group(3),
                }
                continue

            output_match = OUTPUT_PATH_RE.fullmatch(line)
            if output_match:
                if active_item is None:
                    raise ValueError("execution output path outside an E0 item in {}".format(path))
                if "output_path" in active_item:
                    raise ValueError(
                        "duplicate execution output path for {}".format(active_item["artifact_id"])
                    )
                active_item["output_path"] = output_match.group(1)
                continue

            finish_match = FINISH_RE.fullmatch(line)
            if finish_match:
                finish = finish_match.groups()
                if active_item is None:
                    raise ValueError("E0_ITEM_FINISH without E0_ITEM_START in {}".format(path))
                start_identity = (
                    active_item["artifact_id"],
                    active_item["dataset"],
                    active_item["family"],
                )
                if finish != start_identity:
                    raise ValueError(
                        "E0_ITEM_START/FINISH identity mismatch in {}".format(path)
                    )
                if "output_path" not in active_item:
                    raise ValueError(
                        "missing execution output path for {}".format(active_item["artifact_id"])
                    )
                artifact_id = active_item["artifact_id"]
                if artifact_id in output_paths:
                    raise ValueError("duplicate E0_ITEM_FINISH in shard {}".format(shard))
                output_paths[artifact_id] = active_item["output_path"]
                finishes.append(finish)
                active_item = None

        if active_item is not None:
            raise ValueError(
                "unterminated E0_ITEM_START for {} in {}".format(
                    active_item["artifact_id"], path
                )
            )
        finish_ids = [row[0] for row in finishes]
        expected_ids = list(EXPECTED_SHARD_ITEMS.get(shard, ()))
        if len(finish_ids) != len(set(finish_ids)):
            raise ValueError("duplicate E0_ITEM_FINISH in shard {}".format(shard))
        if set(finish_ids) != set(expected_ids):
            raise ValueError(
                "E0_ITEM_FINISH matrix mismatch for shard {}: missing={}, unexpected={}".format(
                    shard,
                    sorted(set(expected_ids) - set(finish_ids)),
                    sorted(set(finish_ids) - set(expected_ids)),
                )
            )
        for artifact_id, dataset, family in finishes:
            expected_dataset = dict(EXPECTED_MATRIX)[artifact_id]
            expected_family = "diffurec" if artifact_id.startswith("diffurec_") else "core"
            if dataset != expected_dataset or family != expected_family:
                raise ValueError("E0_ITEM_FINISH identity mismatch for {}".format(artifact_id))
        revisions.add(revision)
        by_shard[shard] = {
            "shard": shard,
            "gpu": gpu,
            "code_revision": revision,
            "item_finish_ids": finish_ids,
            "output_paths_by_artifact": output_paths,
            "log_path": str(path),
            "log_sha256": sha256_file(path),
        }

    if set(by_shard) != {0, 1}:
        raise ValueError("E0 execution logs must cover shards 0 and 1")
    if len(revisions) != 1:
        raise ValueError("E0 code revision mismatch across execution logs: {}".format(sorted(revisions)))
    output_paths_by_artifact: Dict[str, str] = {}
    for shard in (0, 1):
        for artifact_id, output_path in by_shard[shard]["output_paths_by_artifact"].items():
            if artifact_id in output_paths_by_artifact:
                raise ValueError("duplicate execution output path binding for {}".format(artifact_id))
            output_paths_by_artifact[artifact_id] = output_path
    return {
        "code_revision": next(iter(revisions)),
        "shards": [by_shard[0], by_shard[1]],
        "completed_item_count": sum(len(row["item_finish_ids"]) for row in by_shard.values()),
        "output_paths_by_artifact": output_paths_by_artifact,
    }


def validate_execution_output_bindings(
    execution: Dict[str, Any], rows: Sequence[Dict[str, Any]]
) -> None:
    logged_paths = execution["output_paths_by_artifact"]
    result_paths = {row["artifact_id"]: row["evaluation_artifact_path"] for row in rows}
    if set(logged_paths) != set(result_paths):
        raise ValueError("execution output path matrix mismatch")
    for artifact_id, result_path in result_paths.items():
        logged_path = Path(logged_paths[artifact_id]).resolve()
        actual_path = Path(result_path).resolve()
        if logged_path != actual_path:
            raise ValueError(
                "execution output path mismatch for {}: logged {}, loaded {}".format(
                    artifact_id, logged_path, actual_path
                )
            )


def validate_metric_pair(hr10: object, ndcg10: object, label: str) -> Tuple[float, float]:
    hr = float(hr10)
    ndcg = float(ndcg10)
    if not math.isfinite(hr) or not math.isfinite(ndcg):
        raise ValueError("finite metric required for {}".format(label))
    if not 0.0 <= ndcg <= hr <= 1.0:
        raise ValueError("metric range/order violation for {}: hr={}, ndcg={}".format(label, hr, ndcg))
    return hr, ndcg


def validate_payload_identity(
    artifact_id: str,
    dataset: str,
    payload: Dict[str, Any],
) -> Tuple[int, int, str, int]:
    if payload.get("schema_version") != 1:
        raise ValueError("schema version mismatch for {}".format(artifact_id))
    if payload.get("dataset") != dataset:
        raise ValueError("dataset mismatch for {}".format(artifact_id))
    expected_method_id = "diffurec" if artifact_id.startswith("diffurec_") else artifact_id
    if payload.get("method_id") != expected_method_id:
        raise ValueError("method identity mismatch for {}".format(artifact_id))
    if int(payload.get("random_seed", -1)) != 100:
        raise ValueError("random seed mismatch for {}".format(artifact_id))
    if payload.get("selection_bias_not_recomputed") is not True:
        raise ValueError("selector limitation missing for {}".format(artifact_id))

    is_diffurec = artifact_id.startswith("diffurec_")
    expected_selector = (
        "legacy_equal_batch_mean_validation"
        if is_diffurec
        else "legacy_tail_skipping_validation"
    )
    if payload.get("checkpoint_selector_protocol") != expected_selector:
        raise ValueError("selector protocol mismatch for {}".format(artifact_id))
    if not is_diffurec and payload.get("strength") != "p2":
        raise ValueError("strength mismatch for {}: expected p2".format(artifact_id))

    test = payload.get("test", {})
    frozen_rows = EXPECTED_ROWS[dataset]
    expected_rows = int(test.get("expected_rows", -1))
    evaluated_rows = int(test.get("evaluated_rows", -1))
    if expected_rows != frozen_rows or evaluated_rows != frozen_rows:
        raise ValueError(
            "row count mismatch for {}: expected_rows={}, evaluated_rows={}, frozen_rows={}".format(
                artifact_id, expected_rows, evaluated_rows, frozen_rows
            )
        )

    contract = payload.get("metric_contract", {})
    required_contract = {
        "version": "e0_full_tail_v2",
        "aggregation_weight": "row",
        "tail_batch_included": True,
        "eval_seed": 100,
    }
    for key, expected in required_contract.items():
        if contract.get(key) != expected:
            raise ValueError("metric contract mismatch for {}.{}".format(artifact_id, key))
    candidate_policy = str(contract.get("candidate_policy", ""))
    expected_policy = "exclude-padding-id-0" if is_diffurec else "first-M-zero-based"
    if candidate_policy != expected_policy:
        raise ValueError("candidate policy mismatch for {}".format(artifact_id))

    if not is_diffurec:
        valid_count = int(contract.get("valid_item_count", -1))
        model_count = int(contract.get("model_item_count", -1))
        extra_slots = int(contract.get("non_candidate_model_item_slots", -1))
        mismatch_allowed = contract.get("legacy_model_catalog_mismatch_authorized")
        if valid_count != EXPECTED_CATALOG_ITEMS[dataset]:
            raise ValueError("valid catalog item count mismatch for {}".format(artifact_id))
        if model_count - valid_count != extra_slots:
            raise ValueError("model/catalog slot accounting mismatch for {}".format(artifact_id))
        domain = contract.get("test_item_domain", {})
        if int(domain.get("maximum_target_item_id", valid_count)) >= valid_count:
            raise ValueError("test target domain mismatch for {}".format(artifact_id))
        if artifact_id == "host_atg":
            if (model_count, valid_count, extra_slots, mismatch_allowed) != (
                11924,
                11921,
                3,
                True,
            ):
                raise ValueError("host_atg legacy item-count disclosure mismatch")
            if domain.get("history_pad_semantics") != "ordinary_non_candidate_legacy_model_slot":
                raise ValueError("host_atg legacy padding disclosure mismatch")
            if domain.get("history_pad_maps_to_non_candidate_model_slot") is not True:
                raise ValueError("host_atg legacy padding mapping flag missing")
        else:
            if model_count != valid_count or extra_slots != 0 or mismatch_allowed is not False:
                raise ValueError("unexpected model/catalog mismatch for {}".format(artifact_id))
    return expected_rows, evaluated_rows, candidate_policy, int(contract["eval_seed"])


def verify_payload_sources(
    artifact_id: str,
    dataset: str,
    payload: Dict[str, Any],
    evaluation_path: Path,
    hash_cache: Dict[str, str],
) -> Dict[str, Any]:
    sources = payload.get("sources", {})
    is_diffurec = artifact_id.startswith("diffurec_")
    is_host = artifact_id.startswith("host_")
    verified: Dict[str, Any] = {}
    required_names = ["checkpoint", "summary", "split"]
    if not is_diffurec:
        required_names.append("log")
    if not is_host:
        required_names.append("manifest")
    if is_host and sources.get("manifest_path"):
        raise ValueError("host manifest exception violated for {}".format(artifact_id))
    for name in required_names:
        path_key = name + "_path"
        hash_key = name + "_sha256"
        path = resolve_source_path(sources.get(path_key, ""), evaluation_path)
        actual_hash = verify_source_hash(
            path, sources.get(hash_key), "{}.{}".format(artifact_id, name), hash_cache
        )
        verified[path_key] = str(path)
        verified[hash_key] = actual_hash

    if is_diffurec:
        runner_path = resolve_source_path(sources.get("evaluator_runner_path", ""), evaluation_path)
        verified["evaluator_runner_path"] = str(runner_path)
        verified["evaluator_runner_sha256"] = verify_source_hash(
            runner_path,
            sources.get("evaluator_runner_sha256"),
            artifact_id + ".evaluator_runner",
            hash_cache,
        )
        upstream_revision = str(sources.get("upstream_revision", ""))
        wrapper_revision = str(payload.get("training_wrapper_revision", ""))
        if not re.fullmatch(r"[0-9a-f]{40}", upstream_revision):
            raise ValueError("DiffuRec upstream revision missing for {}".format(artifact_id))
        if not re.fullmatch(r"[0-9a-f]{40}", wrapper_revision):
            raise ValueError("DiffuRec wrapper revision missing for {}".format(artifact_id))
        verified["upstream_revision"] = upstream_revision
        verified["training_wrapper_revision"] = wrapper_revision

    manifest_path = verified.get("manifest_path")
    if manifest_path:
        manifest = load_json(Path(manifest_path))
        if manifest.get("dataset") != dataset or int(manifest.get("random_seed", -1)) != 100:
            raise ValueError("manifest identity mismatch for {}".format(artifact_id))
        if is_diffurec and int(manifest.get("item_num", -1)) != EXPECTED_CATALOG_ITEMS[dataset]:
            raise ValueError("DiffuRec manifest item count mismatch for {}".format(artifact_id))
    return verified


def extract_old_metrics(
    artifact_id: str,
    payload: Dict[str, Any],
    verified_sources: Dict[str, Any],
) -> Tuple[float, float]:
    summary = load_json(Path(verified_sources["summary_path"]))
    try:
        if artifact_id.startswith("diffurec_"):
            return validate_metric_pair(
                summary["test"]["HR@10"], summary["test"]["NDCG@10"], artifact_id + ".old"
            )
        strength = str(payload["strength"])
        return validate_metric_pair(
            summary["test"][strength]["hr"][2],
            summary["test"][strength]["ndcg"][2],
            artifact_id + ".old",
        )
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        if isinstance(exc, ValueError) and "metric" in str(exc):
            raise
        raise ValueError("unable to extract legacy HR@10/NDCG@10 for {}".format(artifact_id)) from exc


def build_metric_rows(input_root: Path) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    paths = collect_evaluation_paths(input_root)
    hash_cache: Dict[str, str] = {}
    rows: List[Dict[str, Any]] = []
    split_hashes: Dict[str, set] = {dataset: set() for dataset in EXPECTED_ROWS}

    for artifact_id, dataset in EXPECTED_MATRIX:
        evaluation_path = paths[artifact_id]
        payload = load_json(evaluation_path)
        expected_rows, evaluated_rows, candidate_policy, eval_seed = validate_payload_identity(
            artifact_id, dataset, payload
        )
        verified = verify_payload_sources(
            artifact_id, dataset, payload, evaluation_path, hash_cache
        )
        old_hr10, old_ndcg10 = extract_old_metrics(artifact_id, payload, verified)
        corrected_hr10, corrected_ndcg10 = validate_metric_pair(
            payload["test"]["hr10"], payload["test"]["ndcg10"], artifact_id + ".corrected"
        )
        if artifact_id.startswith("diffurec_"):
            metrics = payload["test"].get("metrics", {})
            if abs(float(metrics.get("HR@10", -1)) - corrected_hr10) > 1e-12 or abs(
                float(metrics.get("NDCG@10", -1)) - corrected_ndcg10
            ) > 1e-12:
                raise ValueError("DiffuRec metric shortcut mismatch for {}".format(artifact_id))
        else:
            if abs(float(payload["test"]["hr"][2]) - corrected_hr10) > 1e-12 or abs(
                float(payload["test"]["ndcg"][2]) - corrected_ndcg10
            ) > 1e-12:
                raise ValueError("PreferGrow metric shortcut mismatch for {}".format(artifact_id))

        split_hashes[dataset].add(verified["split_sha256"])
        contract = payload["metric_contract"]
        domain = contract.get("test_item_domain", {})
        row: Dict[str, Any] = {
            "artifact_id": artifact_id,
            "method_family": method_family(artifact_id),
            "dataset": dataset,
            "old_hr10": old_hr10,
            "corrected_hr10": corrected_hr10,
            "delta_hr10_corrected_minus_old": corrected_hr10 - old_hr10,
            "old_ndcg10": old_ndcg10,
            "corrected_ndcg10": corrected_ndcg10,
            "delta_ndcg10_corrected_minus_old": corrected_ndcg10 - old_ndcg10,
            "expected_rows": expected_rows,
            "evaluated_rows": evaluated_rows,
            "metric_contract_version": contract["version"],
            "candidate_policy": candidate_policy,
            "valid_item_count": contract.get("valid_item_count", EXPECTED_CATALOG_ITEMS[dataset]),
            "model_item_count": contract.get("model_item_count", "native_diffurec"),
            "non_candidate_model_item_slots": contract.get(
                "non_candidate_model_item_slots", "native_diffurec"
            ),
            "legacy_model_catalog_mismatch_authorized": contract.get(
                "legacy_model_catalog_mismatch_authorized", False
            ),
            "history_pad_semantics": domain.get("history_pad_semantics", "native_diffurec"),
            "random_seed": int(payload["random_seed"]),
            "eval_seed": eval_seed,
            "checkpoint_selector_protocol": payload["checkpoint_selector_protocol"],
            "selection_bias_not_recomputed": True,
            "evaluation_artifact_path": str(evaluation_path),
            "evaluation_artifact_sha256": sha256_file(evaluation_path),
            "best_epoch": payload.get("best_epoch"),
            "best_step": payload.get("best_step"),
            "source_provenance": verified,
        }
        for field in (
            "summary_path",
            "summary_sha256",
            "checkpoint_path",
            "checkpoint_sha256",
            "log_path",
            "log_sha256",
            "manifest_path",
            "manifest_sha256",
            "split_path",
            "split_sha256",
        ):
            row[field] = verified.get(field, "")
        rows.append(row)

    canonical_split_hashes: Dict[str, str] = {}
    for dataset, hashes in split_hashes.items():
        if len(hashes) != 1:
            raise ValueError("split hash mismatch across E0 methods for {}".format(dataset))
        canonical_split_hashes[dataset] = next(iter(hashes))
    return rows, canonical_split_hashes


def unique_dataset_map(rows: Sequence[Dict[str, Any]], label: str) -> Dict[str, Dict[str, Any]]:
    by_dataset: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        dataset = str(row.get("dataset", ""))
        if dataset in by_dataset:
            raise ValueError("duplicate dataset in {}: {}".format(label, dataset))
        by_dataset[dataset] = dict(row)
    if set(by_dataset) != set(EXPECTED_ROWS):
        raise ValueError("{} must contain exactly four frozen datasets".format(label))
    return by_dataset


def validate_gate0_original(payload: Dict[str, Any]) -> Dict[str, Any]:
    criterion = payload.get("criterion", {})
    if float(criterion.get("ml1m_abs_median_max", math.nan)) != 0.5:
        raise ValueError("original Gate 0 threshold drift")
    if criterion.get("steam_median_gt_ml1m") is not True or criterion.get(
        "beauty_median_gt_ml1m"
    ) is not True:
        raise ValueError("original Gate 0 ordering criterion drift")
    rows = unique_dataset_map(payload.get("datasets", []), "original Gate 0")
    medians = {dataset: float(row["median_u_tilde"]) for dataset, row in rows.items()}
    passed = (
        abs(medians["ML1M"]) < 0.5
        and medians["Steam"] > medians["ML1M"]
        and medians["Beauty"] > medians["ML1M"]
    )
    recorded = payload.get("gate0_verdict")
    recomputed = "pass" if passed else "fail"
    if recorded != recomputed:
        raise ValueError("original Gate 0 verdict mismatch")
    return {
        "criterion_unchanged": criterion,
        "old_verdict": recorded,
        "corrected_verdict": recorded,
        "verdict_flipped": False,
        "recomputed_from_e0_metrics": False,
        "reread_basis": "u_tilde_inputs_unaffected_by_e0",
    }


def validate_gate0_v2(payload: Dict[str, Any]) -> Dict[str, Any]:
    if type(payload.get("criterion_pass")) is not bool:
        raise ValueError("Gate 0-v2 criterion_pass must be a JSON boolean")
    rows = unique_dataset_map(payload.get("datasets", []), "Gate 0-v2")
    u_values = {dataset: float(row["u_ds_popularity"]) for dataset, row in rows.items()}
    phi_values = {dataset: float(row["phi_u_ds"]) for dataset, row in rows.items()}
    recomputed_conditions = {
        "condition_1_ml1m_is_max": u_values["ML1M"] == max(u_values.values()),
        "condition_2_ml1m_phi_lte_0_2": phi_values["ML1M"] <= 0.2,
        "condition_3_two_non_ml1m_phi_ge_0_5": sum(
            phi_values[name] >= 0.5 for name in ("Steam", "Beauty", "ATG")
        )
        >= 2,
    }
    recorded_conditions = {
        str(row["id"]): row.get("passed") for row in payload.get("conditions", [])
    }
    if recorded_conditions != recomputed_conditions:
        raise ValueError("Gate 0-v2 condition mismatch")
    recomputed_pass = all(recomputed_conditions.values())
    if payload["criterion_pass"] != recomputed_pass:
        raise ValueError("Gate 0-v2 verdict mismatch")
    verdict = "pass" if recomputed_pass else "fail"
    return {
        "criterion_name_unchanged": payload.get("criterion_name"),
        "conditions_unchanged": payload.get("conditions"),
        "old_verdict": verdict,
        "corrected_verdict": verdict,
        "verdict_flipped": False,
        "recomputed_from_e0_metrics": False,
        "reread_basis": "U_ds_phi_inputs_unaffected_by_e0",
    }


def prediction_outcome(dataset: str, delta: float) -> str:
    if dataset == "Steam":
        if delta >= 0.003:
            return "full_hit"
        if delta > 0.0:
            return "directional_hit_reference_miss"
        return "miss"
    return "hit" if abs(delta) < 0.01 else "miss"


def gate1_verdict(delta: float) -> str:
    if delta > -0.01:
        return "pass"
    if delta <= -0.03:
        return "diagnostic_allowed"
    return "fail_no_diagnostic"


def build_gate_reread(
    rows: List[Dict[str, Any]],
    gate0_original_payload: Dict[str, Any],
    gate0_v2_payload: Dict[str, Any],
    legacy_gate1_payload: Dict[str, Any],
) -> Dict[str, Any]:
    by_id = {str(row["artifact_id"]): row for row in rows}
    archived_rows = unique_dataset_map(
        legacy_gate1_payload.get("datasets", []), "legacy Gate-1 dataset table"
    )
    frozen_predictions: Dict[str, Dict[str, Any]] = {}
    for dataset in EXPECTED_ROWS:
        suffix = dataset.lower()
        host = by_id["host_" + suffix]
        ours = by_id["ours_full_" + suffix]
        old_host = float(host["old_ndcg10"])
        old_ours = float(ours["old_ndcg10"])
        corrected_host = float(host["corrected_ndcg10"])
        corrected_ours = float(ours["corrected_ndcg10"])
        old_delta = old_ours - old_host
        corrected_delta = corrected_ours - corrected_host
        archived = archived_rows[dataset]
        checks = (
            (old_host, float(archived["core_test_p2_ndcg10"])),
            (old_ours, float(archived["current_test_p2_ndcg10"])),
            (old_delta, float(archived["delta_test_p2_ndcg10"])),
        )
        if any(abs(extracted - recorded) > 1e-12 for extracted, recorded in checks):
            raise ValueError("legacy Gate-1 archived metric mismatch for {}".format(dataset))
        old_outcome = prediction_outcome(dataset, old_delta)
        if archived.get("dataset_verdict") != old_outcome:
            raise ValueError("legacy Gate-1 archived outcome mismatch for {}".format(dataset))
        corrected_outcome = prediction_outcome(dataset, corrected_delta)
        frozen_predictions[dataset] = {
            "gate_state": {
                "Steam": "open_phi_1.0",
                "ML1M": "closed_phi_0.0",
                "Beauty": "closed_phi_0.0",
                "ATG": "barely_open_phi_0.117375",
            }[dataset],
            "criterion_unchanged": (
                "delta > 0; reference magnitude delta >= +0.003"
                if dataset == "Steam"
                else "abs(delta) < 0.01"
            ),
            "old_host_ndcg10": old_host,
            "old_ours_ndcg10": old_ours,
            "old_delta_test_p2_ndcg10": old_delta,
            "old_outcome": old_outcome,
            "corrected_host_ndcg10": corrected_host,
            "corrected_ours_ndcg10": corrected_ours,
            "corrected_delta_test_p2_ndcg10": corrected_delta,
            "corrected_outcome": corrected_outcome,
            "outcome_flipped": old_outcome != corrected_outcome,
        }

    gate1 = legacy_gate1_payload.get("gate1", {})
    if gate1.get("dataset") != "ML1M":
        raise ValueError("Gate-1 dataset mismatch: expected ML1M")
    if float(gate1.get("pass_threshold", math.nan)) != -0.01 or float(
        gate1.get("diagnostic_threshold", math.nan)
    ) != -0.03:
        raise ValueError("Gate-1 threshold drift")
    old_gate1_delta = float(gate1["delta_test_p2_ndcg10"])
    archived_ml1m_delta = float(archived_rows["ML1M"]["delta_test_p2_ndcg10"])
    if abs(old_gate1_delta - archived_ml1m_delta) > 1e-12:
        raise ValueError("Gate-1 delta mismatch with archived ML1M row")
    old_gate1_verdict = str(gate1["verdict"])
    if gate1_verdict(old_gate1_delta) != old_gate1_verdict:
        raise ValueError("legacy Gate-1 verdict does not match frozen thresholds")
    corrected_gate1_delta = float(
        frozen_predictions["ML1M"]["corrected_delta_test_p2_ndcg10"]
    )
    corrected_gate1_verdict = gate1_verdict(corrected_gate1_delta)
    return {
        "gate0_original": validate_gate0_original(gate0_original_payload),
        "gate0_v2": validate_gate0_v2(gate0_v2_payload),
        "sprint05_preregistered_prediction_reread": frozen_predictions,
        "gate1_ml1m": {
            "criterion_unchanged": {
                "pass": "delta_test_p2_ndcg10 > -0.01",
                "diagnostic_allowed": "delta_test_p2_ndcg10 <= -0.03",
            },
            "old_delta_test_p2_ndcg10": old_gate1_delta,
            "old_verdict": old_gate1_verdict,
            "corrected_delta_test_p2_ndcg10": corrected_gate1_delta,
            "corrected_verdict": corrected_gate1_verdict,
            "verdict_flipped": corrected_gate1_verdict != old_gate1_verdict,
        },
    }


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def validate_diffurec_comparison(
    path: Path,
    rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    archived = unique_dataset_map(read_csv_rows(path), "DiffuRec comparison table")
    by_id = {str(row["artifact_id"]): row for row in rows}
    for dataset, archived_row in archived.items():
        row = by_id["diffurec_" + dataset.lower()]
        checks = {
            "baseline_method": archived_row.get("baseline_method") == "DiffuRec",
            "baseline_seed": int(archived_row.get("baseline_seed", -1)) == 100,
            "baseline_selector_metric": archived_row.get("baseline_selector_metric") == "NDCG@10",
            "baseline_best_epoch": int(archived_row.get("baseline_best_epoch", -1))
            == int(row["best_epoch"]),
            "baseline_summary_path": archived_row.get("baseline_summary_path")
            == row["summary_path"],
            "baseline_test_hr10": abs(
                float(archived_row.get("baseline_test_hr10", math.nan)) - float(row["old_hr10"])
            )
            <= 1e-12,
            "baseline_test_ndcg10": abs(
                float(archived_row.get("baseline_test_ndcg10", math.nan))
                - float(row["old_ndcg10"])
            )
            <= 1e-12,
        }
        if not all(checks.values()):
            raise ValueError("DiffuRec comparison mismatch for {}: {}".format(dataset, checks))
    return {"path": str(path), "sha256": sha256_file(path), "dataset_count": 4}


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})


def render_metric_table(rows: List[Dict[str, Any]]) -> List[str]:
    lines = [
        "| Artifact | Dataset | Old HR@10 | New HR@10 | Old NDCG@10 | New NDCG@10 | Rows |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {artifact_id} | {dataset} | {old_hr10:.6f} | {corrected_hr10:.6f} | "
            "{old_ndcg10:.6f} | {corrected_ndcg10:.6f} | {evaluated_rows} |".format(**row)
        )
    return lines


def render_prediction_table(predictions: Dict[str, Dict[str, Any]]) -> List[str]:
    lines = [
        "| Dataset | Frozen criterion | Old delta/outcome | Corrected delta/outcome | Flipped |",
        "|---|---|---|---|---|",
    ]
    for dataset in ("Steam", "ML1M", "Beauty", "ATG"):
        row = predictions[dataset]
        lines.append(
            "| {} | {} | {:.6f} / {} | {:.6f} / {} | {} |".format(
                dataset,
                row["criterion_unchanged"],
                row["old_delta_test_p2_ndcg10"],
                row["old_outcome"],
                row["corrected_delta_test_p2_ndcg10"],
                row["corrected_outcome"],
                str(row["outcome_flipped"]).lower(),
            )
        )
    return lines


def render_english(report: Dict[str, Any]) -> str:
    gate = report["gate_reread"]
    lines = [
        "# E0 dated evaluator amendment (2026-07-10)",
        "",
        "## Scope and evidence boundary",
        "",
        "This amendment is a **single-run result/observation** under the common full-tail, "
        "row-weighted, real-item test contract. Its exact scope is **legacy-selected frozen "
        "checkpoint + corrected test evaluation**. Validation selection was not recomputed.",
        "",
        "The legacy host ATG checkpoint used model item count 11,924 while the real catalog "
        "contains 11,921 items. Its history sentinel 11,921 was an ordinary non-candidate "
        "model slot during frozen training. E0 preserves that frozen input meaning and only "
        "restricts paper-facing ranking to real IDs 0--11,920; fully protocol-aligned training "
        "comparability is not claimed for that host checkpoint.",
        "",
        "No frozen checkpoint, Gate-1, SPRINT-07, DiffuRec, or Table 2 artifact was overwritten.",
        "",
        "## Old/new metrics",
        "",
    ]
    lines.extend(render_metric_table(report["rows"]))
    lines.extend(["", "## Frozen prediction reread", ""])
    lines.extend(render_prediction_table(gate["sprint05_preregistered_prediction_reread"]))
    lines.extend(
        [
            "",
            "- Original Gate 0: `{}` -> `{}`; flipped=`false`; its u-tilde inputs are unchanged.".format(
                gate["gate0_original"]["old_verdict"],
                gate["gate0_original"]["corrected_verdict"],
            ),
            "- Gate 0-v2: `{}` -> `{}`; flipped=`false`; its U_ds/phi inputs are unchanged.".format(
                gate["gate0_v2"]["old_verdict"], gate["gate0_v2"]["corrected_verdict"]
            ),
            "- Gate 1 ML1M: `{}` -> `{}`; corrected delta={:.12f}; flipped=`{}`.".format(
                gate["gate1_ml1m"]["old_verdict"],
                gate["gate1_ml1m"]["corrected_verdict"],
                gate["gate1_ml1m"]["corrected_delta_test_p2_ndcg10"],
                str(gate["gate1_ml1m"]["verdict_flipped"]).lower(),
            ),
            "",
            "DiffuRec test-evaluator comparability is confirmed under the dated corrected "
            "contract. Checkpoint-selection equivalence is not claimed. Table 2 remains frozen "
            "in this cycle; later paper backfill must use an all-system common-ruler replacement.",
            "",
        ]
    )
    return "\n".join(lines)


def render_chinese(report: Dict[str, Any]) -> str:
    gate = report["gate_reread"]
    lines = [
        "# E0 evaluator 修正案（2026-07-10）",
        "",
        "## 范围与证据边界",
        "",
        "本修正案仅报告共同全尾批、逐行加权、真实物品候选契约下的**单次运行观察**。"
        "精确范围是：**历史选择的冻结 checkpoint + 修正后的 test 评估**；validation 选择没有重算。",
        "",
        "ATG 的旧 host checkpoint 按 11,924 个模型 item 槽训练，而真实目录是 11,921。历史 sentinel "
        "11,921 在该冻结 host 中是普通非候选模型槽。E0 原样保留该输入语义，只把论文排名候选限定为"
        "真实 ID 0--11,920；不声称该 host checkpoint 的训练协议已与 ours 完全对齐。",
        "",
        "未覆盖任何冻结 checkpoint、Gate-1、SPRINT-07、DiffuRec 或 Table 2 工件。",
        "",
        "## 新旧指标",
        "",
    ]
    lines.extend(render_metric_table(report["rows"]))
    lines.extend(["", "## 冻结预测重新宣读", ""])
    lines.extend(render_prediction_table(gate["sprint05_preregistered_prediction_reread"]))
    lines.extend(
        [
            "",
            "- 原始 Gate 0：`{}` -> `{}`，翻转=`false`；u-tilde 输入不受 E0 影响。".format(
                gate["gate0_original"]["old_verdict"],
                gate["gate0_original"]["corrected_verdict"],
            ),
            "- Gate 0-v2：`{}` -> `{}`，翻转=`false`；U_ds/phi 输入不受 E0 影响。".format(
                gate["gate0_v2"]["old_verdict"], gate["gate0_v2"]["corrected_verdict"]
            ),
            "- Gate 1 ML1M：`{}` -> `{}`，修正后 delta={:.12f}，翻转=`{}`。".format(
                gate["gate1_ml1m"]["old_verdict"],
                gate["gate1_ml1m"]["corrected_verdict"],
                gate["gate1_ml1m"]["corrected_delta_test_p2_ndcg10"],
                str(gate["gate1_ml1m"]["verdict_flipped"]).lower(),
            ),
            "",
            "DiffuRec 已在本次修正后的 test evaluator 契约下完成可比性核验；不声称 checkpoint 选择"
            "过程等价。本周期 Table 2 继续冻结，后续论文回填只能执行全体系共同换尺。",
            "",
        ]
    )
    return "\n".join(lines)


def copy_provenance(
    staging_dir: Path,
    rows: List[Dict[str, Any]],
    execution: Dict[str, Any],
    gate0_original_path: Path,
    gate0_v2_path: Path,
    legacy_gate1_report_path: Path,
    diffurec_comparison_path: Path,
) -> List[Dict[str, str]]:
    entries: List[Dict[str, str]] = []
    archived_relative_paths = set()

    def archive(source: Path, relative: Path) -> None:
        relative_key = relative.as_posix()
        if relative_key in archived_relative_paths:
            raise ValueError("duplicate provenance archive path: {}".format(relative_key))
        archived_relative_paths.add(relative_key)
        destination = staging_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        entries.append(
            {
                "relative_path": relative_key,
                "sha256": sha256_file(destination),
                "original_source_path": str(source),
            }
        )

    for row in rows:
        archive(
            Path(row["evaluation_artifact_path"]),
            Path("provenance") / "e0_results" / (str(row["artifact_id"]) + ".json"),
        )
    for shard in execution["shards"]:
        archive(
            Path(shard["log_path"]),
            Path("provenance")
            / "execution_logs"
            / "shard{}.log".format(shard["shard"]),
        )
    for source, name in (
        (gate0_original_path, "gate0_original.json"),
        (gate0_v2_path, "gate0_v2.json"),
        (legacy_gate1_report_path, "gate1_legacy.json"),
        (diffurec_comparison_path, "diffurec_legacy_comparison.csv"),
    ):
        archive(Path(source), Path("provenance") / "frozen_inputs" / name)
    for source in (
        Path(__file__).resolve(),
        REPO_ROOT / "scripts" / "evaluate_frozen_checkpoint.py",
        REPO_ROOT / "scripts" / "evaluate_frozen_diffurec.py",
        REPO_ROOT / "scripts" / "run_e0_fulltail_matrix.sh",
    ):
        archive(source, Path("provenance") / "code" / source.name)
    return entries


def write_package_files(staging_dir: Path, report: Dict[str, Any]) -> None:
    write_csv(staging_dir / "e0_old_new_metrics.csv", report["rows"])
    (staging_dir / "e0_evaluator_amendment.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )
    (staging_dir / "e0_evaluator_amendment.md").write_text(
        render_english(report), encoding="utf-8"
    )
    (staging_dir / "e0_evaluator_amendment_zh.md").write_text(
        render_chinese(report), encoding="utf-8"
    )
    manifest_path = staging_dir / "provenance_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "entries": report["provenance_package"]["entries"],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    sum_lines = []
    for path in sorted(staging_dir.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            sum_lines.append("{}  {}".format(sha256_file(path), path.relative_to(staging_dir).as_posix()))
    (staging_dir / "SHA256SUMS").write_text("\n".join(sum_lines) + "\n", encoding="utf-8")


def build_amendment(
    *,
    input_root: Path,
    output_dir: Path,
    execution_log_paths: Sequence[Path],
    gate0_original_path: Path,
    gate0_v2_path: Path,
    legacy_gate1_report_path: Path,
    diffurec_comparison_path: Path,
    generated_at: Optional[str] = None,
) -> Dict[str, Any]:
    output_dir = Path(output_dir)
    if os.path.lexists(output_dir):
        raise FileExistsError("amendment output directory already exists: {}".format(output_dir))

    execution = validate_execution_logs(execution_log_paths)
    rows, split_hashes = build_metric_rows(Path(input_root))
    validate_execution_output_bindings(execution, rows)
    gate_reread = build_gate_reread(
        rows,
        load_json(gate0_original_path),
        load_json(gate0_v2_path),
        load_json(legacy_gate1_report_path),
    )
    diffurec_validation = validate_diffurec_comparison(diffurec_comparison_path, rows)

    report: Dict[str, Any] = {
        "schema_version": 1,
        "report_name": "E0 full-tail common-evaluator dated amendment",
        "generated_at": generated_at or datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope": "legacy-selected frozen checkpoints + corrected full-row real-candidate test evaluation",
        "execution": execution,
        "metric_contract": {
            "version": "e0_full_tail_v2",
            "tail_batch_included": True,
            "aggregation_weight": "row",
            "candidate_universe": "all_mapped_real_catalog_items_exactly_once",
            "eval_seed": 100,
        },
        "matrix_validation": {
            "artifact_count": len(rows),
            "expected_artifact_count": 18,
            "all_contract_checks_pass": True,
            "expected_rows": EXPECTED_ROWS,
            "expected_catalog_items": EXPECTED_CATALOG_ITEMS,
            "split_sha256_by_dataset": split_hashes,
        },
        "limitations": {
            "legacy_selected_checkpoint": True,
            "corrected_validation_selection": False,
            "corrected_test_evaluation": True,
            "selection_bias_not_recomputed": True,
            "single_seed_observation": True,
        },
        "comparability_limitations": {
            "host_atg": "legacy_training_padding_semantics_not_protocol_aligned"
        },
        "paper_backfill": {
            "table2_numeric_replacement_authorized": False,
            "selective_replacement_authorized": False,
            "future_backfill_rule": "all-system common-ruler replacement only",
        },
        "diffurec_comparability": {
            "status": "confirmed_under_e0_corrected_test_contract",
            "datasets_complete": ["Steam", "ML1M", "Beauty", "ATG"],
            "checkpoint_selection_equivalence_claimed": False,
            "legacy_comparison_validation": diffurec_validation,
        },
        "gate_reread": gate_reread,
        "rows": rows,
        "sources": {
            "input_root": str(input_root),
            "gate0_original_path": str(gate0_original_path),
            "gate0_original_sha256": sha256_file(gate0_original_path),
            "gate0_v2_path": str(gate0_v2_path),
            "gate0_v2_sha256": sha256_file(gate0_v2_path),
            "legacy_gate1_report_path": str(legacy_gate1_report_path),
            "legacy_gate1_report_sha256": sha256_file(legacy_gate1_report_path),
            "diffurec_comparison_path": str(diffurec_comparison_path),
            "diffurec_comparison_sha256": sha256_file(diffurec_comparison_path),
        },
    }

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(
        tempfile.mkdtemp(prefix=".e0-amendment-staging-", dir=str(output_dir.parent))
    )
    try:
        entries = copy_provenance(
            staging_dir,
            rows,
            execution,
            Path(gate0_original_path),
            Path(gate0_v2_path),
            Path(legacy_gate1_report_path),
            Path(diffurec_comparison_path),
        )
        report["provenance_package"] = {
            "entry_count": len(entries),
            "entries": entries,
        }
        write_package_files(staging_dir, report)
        publish_directory_no_clobber(staging_dir, output_dir)
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--execution-log", dest="execution_logs", type=Path, action="append", required=True)
    parser.add_argument("--gate0-original-path", type=Path, default=DEFAULT_GATE0_ORIGINAL)
    parser.add_argument("--gate0-v2-path", type=Path, default=DEFAULT_GATE0_V2)
    parser.add_argument("--legacy-gate1-report-path", type=Path, default=DEFAULT_GATE1_REPORT)
    parser.add_argument("--diffurec-comparison-path", type=Path, default=DEFAULT_DIFFUREC_COMPARISON)
    parser.add_argument("--generated-at")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_amendment(
        input_root=args.input_root,
        output_dir=args.output_dir,
        execution_log_paths=args.execution_logs,
        gate0_original_path=args.gate0_original_path,
        gate0_v2_path=args.gate0_v2_path,
        legacy_gate1_report_path=args.legacy_gate1_report_path,
        diffurec_comparison_path=args.diffurec_comparison_path,
        generated_at=args.generated_at,
    )
    print(
        json.dumps(
            {
                "artifact_count": report["matrix_validation"]["artifact_count"],
                "code_revision": report["execution"]["code_revision"],
                "output_dir": str(args.output_dir),
                "gate1_corrected_verdict": report["gate_reread"]["gate1_ml1m"][
                    "corrected_verdict"
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
