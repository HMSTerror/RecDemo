#!/usr/bin/env python3
"""Launch-gated deterministic E01 g-zero production-path trace.

This tool is intentionally inert unless ``--execute-production-trace`` is
supplied.  The frozen protocol constants below are not command-line options:
changing the seed, trace steps, or FP32 tolerance requires a reviewed source
change before any result is observed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import pickle
import random
import sys
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import torch


DATASET_NAME = "Beauty"
RANDOM_SEED = 100
TRACE_STEPS = (0, 1, 100, 1000)
FP32_TOLERANCE = 1e-6
SAMPLING_PROBE_SEED_BASE = 10_100
ARM_NAMES = ("host", "final_v2_closed_gate_full", "global_p")
REFERENCE_ARM = "host"
EXPECTED_ITEM_COUNT = 12_101
EXPECTED_E0_ARTIFACT_COUNT = 18
EXPECTED_E0_AMENDMENT_SHA256 = (
    "da11d9f7307ad4377c9bf02d378fbf69bddae0453be3403502ef7c0ec3c4f9e5"
)
EXPECTED_E0_CODE_REVISION = "d1b6664178b5880989c2ee2d3959c1ec6d1c67c4"
EXPECTED_BEAUTY_ASSET_FINGERPRINTS = {
    "bank_hash": "591e4f4ee24160becd190f2b5279a48a351004ff6fd09f228473188a182b5d9b",
    "split_hash": "ab2863e37b13290aa216ae4c83c725a852e2a7fdd9325afb1d501e0141e3f2b6",
    "null_curve_sha256": "7d7bb94850ddef882ae037724261b21cc2e0bba623d8e9651510297a96d0948b",
    "text_utility_sha256": "75f76a1701dd349aa49d4919c17c7d0bec0b5998e9c0f9031a1779c1bb74a420",
}
PROTOCOL_SCOPE_DECISION = (
    "Beauty is the sole E01 domain because it has the matched production trio: "
    "AdaptiveWise host, final-v2 full with phi_u_ds=0, and global_p. ML1M is "
    "excluded because its frozen host uses the hybrid graph; this trace does not "
    "claim ML1M equivalence."
)
LAST_EXECUTION_CONTEXT: dict[str, Any] = {
    "phase": "startup",
    "arm": None,
    "trace_step": None,
    "training_started": False,
}
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from scripts.aaai27_adapters.optimizer_contract import compose_optimizer_parameters
DEFAULT_E0_AMENDMENT_PATH = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "data"
    / "2026-07-10-evaluator-amendment"
    / "e0_evaluator_amendment.json"
)

CONFIG_DIFFERENCE_ALLOWLIST = {
    "graph.type": {
        "host": "adaptive",
        "final_v2_closed_gate_full": "proposal_adaptive",
        "global_p": "proposal_adaptive",
    },
    "text_side.enabled": {
        "host": False,
        "final_v2_closed_gate_full": True,
        "global_p": True,
    },
    "text_side.ablation_mode": {
        "host": "none",
        "final_v2_closed_gate_full": "none",
        "global_p": "global_p",
    },
}

SELECTOR_CONTRACT = {
    "early_stop_patience": 5,
    "early_stop_min_step": 5000,
    "best_selection_min_step": 0,
    "early_stop_metric": "ndcg10",
    "early_stop_strength": "p5",
    "early_stop_min_delta": 0.0,
}


def _json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_named_files(*paths: Path | str) -> str:
    digest = hashlib.sha256()
    for raw_path in paths:
        path = Path(raw_path)
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def capture_rng_state(*, include_cuda: bool | None = None) -> dict[str, Any]:
    if include_cuda is None:
        include_cuda = torch.cuda.is_available()
    cuda_states: list[torch.Tensor] = []
    if include_cuda:
        if not torch.cuda.is_available():
            raise ValueError("CUDA RNG state requested but CUDA is unavailable")
        cuda_states = [state.clone() for state in torch.cuda.get_rng_state_all()]
    return {
        "python": random.getstate(),
        "numpy": np.random.get_state(),
        "torch_cpu": torch.get_rng_state().clone(),
        "torch_cuda": cuda_states,
    }


def restore_rng_state(state: Mapping[str, Any]) -> None:
    random.setstate(state["python"])
    np.random.set_state(state["numpy"])
    torch.set_rng_state(state["torch_cpu"].clone())
    cuda_states = list(state.get("torch_cuda", []))
    if cuda_states:
        if not torch.cuda.is_available():
            raise ValueError("cannot restore CUDA RNG state because CUDA is unavailable")
        torch.cuda.set_rng_state_all([value.clone() for value in cuda_states])


def _pickle_sha256(value: Any) -> str:
    return hashlib.sha256(pickle.dumps(value, protocol=4)).hexdigest()


def rng_state_metadata(state: Mapping[str, Any]) -> dict[str, Any]:
    python_hash = _pickle_sha256(state["python"])
    numpy_state = state["numpy"]
    numpy_hash = _pickle_sha256(
        (
            numpy_state[0],
            np.asarray(numpy_state[1]).tobytes(),
            numpy_state[2],
            numpy_state[3],
            numpy_state[4],
        )
    )
    cpu_hash = hashlib.sha256(state["torch_cpu"].cpu().numpy().tobytes()).hexdigest()
    cuda_hashes = [
        hashlib.sha256(value.cpu().numpy().tobytes()).hexdigest()
        for value in state.get("torch_cuda", [])
    ]
    metadata = {
        "python_sha256": python_hash,
        "numpy_sha256": numpy_hash,
        "torch_cpu_sha256": cpu_hash,
        "torch_cuda_sha256": cuda_hashes,
    }
    metadata["combined_sha256"] = _json_sha256(metadata)
    return metadata


def normalize_trace_start_rng(
    runtimes: Mapping[str, Any],
    *,
    trace_start_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize the shared trace boundary without hiding constructor consumption.

    Each production arm may consume a different amount of RNG while constructing
    its model, graph, optimizer, and loaders.  That construction provenance is
    retained in the evidence, but the first comparable trace operation must start
    from one immutable RNG state.  This helper copies that state independently to
    every runtime so probes and training cannot mutate a shared object.
    """

    if set(runtimes) != set(ARM_NAMES):
        raise ValueError(
            "trace-start RNG normalization requires exactly the registered arms: "
            f"expected={ARM_NAMES}, got={tuple(runtimes)}"
        )
    if trace_start_state is None:
        trace_start_state = capture_rng_state(include_cuda=torch.cuda.is_available())

    trace_start_metadata = rng_state_metadata(trace_start_state)
    construction_metadata: dict[str, dict[str, Any]] = {}
    for arm in ARM_NAMES:
        runtime = runtimes[arm]
        construction = rng_state_metadata(runtime.rng_state)
        construction_metadata[arm] = construction
        runtime.construction_rng_metadata = deepcopy(construction)
        runtime.trace_start_rng_metadata = deepcopy(trace_start_metadata)
        runtime.rng_state = deepcopy(trace_start_state)

    return {
        "normalization": "shared_post_construction_trace_start",
        "trace_start": trace_start_metadata,
        "construction": construction_metadata,
    }


def run_forked_sampling_probe(
    *,
    model: Any,
    sampling_fn: Any,
    history: torch.Tensor,
    probe_seed: int,
    training_rng_state: Mapping[str, Any],
    include_cuda: bool,
) -> torch.Tensor:
    """Run a production sampler probe while restoring the training RNG exactly."""

    restore_rng_state(training_rng_state)
    random.seed(int(probe_seed))
    np.random.seed(int(probe_seed))
    torch.manual_seed(int(probe_seed))
    if include_cuda:
        if not torch.cuda.is_available():
            raise ValueError("CUDA sampling probe requested but CUDA is unavailable")
        torch.cuda.manual_seed_all(int(probe_seed))
    was_training = getattr(model, "training", None)
    try:
        with torch.no_grad():
            output = sampling_fn(model, (history.shape[0], 1), history)
        return output.detach().cpu().clone()
    finally:
        if was_training is not None:
            model.train(bool(was_training))
        restore_rng_state(training_rng_state)


def compute_asset_fingerprints(
    dataset_dir: Path | str,
    text_utility_report_path: Path | str,
    *,
    allow_missing_utility: bool = False,
) -> dict[str, str | None]:
    dataset_dir = Path(dataset_dir)
    utility_path = Path(text_utility_report_path)
    text_bank_path = dataset_dir / "text_bank.csv"
    embeddings_path = dataset_dir / "sentence_t5_xl_item_emb.pt"
    split_path = dataset_dir / "train_data.df"
    null_curve_path = dataset_dir / "agreement_null_curves.json"
    required = (text_bank_path, embeddings_path, split_path, null_curve_path)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing Beauty trace assets: " + ", ".join(missing))
    if not utility_path.is_file() and not allow_missing_utility:
        raise FileNotFoundError(f"missing Beauty text utility report: {utility_path}")
    return {
        "bank_hash": sha256_named_files(text_bank_path, embeddings_path),
        "split_hash": sha256_named_files(split_path),
        "null_curve_sha256": sha256_file(null_curve_path),
        "text_utility_sha256": sha256_file(utility_path) if utility_path.is_file() else None,
    }


def validate_beauty_asset_contract(
    dataset_dir: Path | str,
    text_utility_report_path: Path | str,
    *,
    expected_fingerprints: Mapping[str, str] = EXPECTED_BEAUTY_ASSET_FINGERPRINTS,
    require_runtime_item_count: bool = True,
) -> dict[str, Any]:
    dataset_dir = Path(dataset_dir)
    utility_path = Path(text_utility_report_path)
    if dataset_dir.name != DATASET_NAME:
        raise ValueError(
            f"Beauty asset contract requires a directory named {DATASET_NAME}, got {dataset_dir}"
        )
    observed = compute_asset_fingerprints(dataset_dir, utility_path)
    for key, expected in expected_fingerprints.items():
        if observed.get(key) != expected:
            raise ValueError(
                f"Beauty asset hash mismatch at {key}: expected {expected}, got {observed.get(key)}"
            )

    utility_payload = json.loads(utility_path.read_text(encoding="utf-8"))
    dataset_rows = utility_payload.get("datasets", [])
    dataset_row = next(
        (row for row in dataset_rows if str(row.get("dataset")) == DATASET_NAME),
        None,
    )
    if dataset_row is None:
        raise ValueError("Beauty asset contract: utility report has no Beauty row")
    if str(dataset_row.get("bank_hash")) != str(observed["bank_hash"]):
        raise ValueError("Beauty asset contract: utility bank_hash does not match assets")
    if str(dataset_row.get("split_hash")) != str(observed["split_hash"]):
        raise ValueError("Beauty asset contract: utility split_hash does not match train split")
    phi_u_ds = float(dataset_row.get("phi_u_ds", float("nan")))
    if phi_u_ds != 0.0:
        raise ValueError(
            f"Beauty asset contract requires the frozen closed gate phi_u_ds=0, got {phi_u_ds}"
        )

    runtime_item_count = None
    if require_runtime_item_count:
        import dataset_runtime

        runtime_item_count = dataset_runtime.infer_runtime_item_num(dataset_dir)
        if runtime_item_count != EXPECTED_ITEM_COUNT:
            raise ValueError(
                "Beauty asset contract item count mismatch: "
                f"expected {EXPECTED_ITEM_COUNT}, got {runtime_item_count}"
            )
    return {
        **observed,
        "dataset": DATASET_NAME,
        "phi_u_ds": phi_u_ds,
        "u_ds_popularity": float(dataset_row["u_ds_popularity"]),
        "runtime_item_count": runtime_item_count,
    }


def _flatten_mapping(value: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key in sorted(value):
        path = f"{prefix}.{key}" if prefix else str(key)
        child = value[key]
        if isinstance(child, Mapping):
            flattened.update(_flatten_mapping(child, path))
        else:
            flattened[path] = child
    return flattened


def validate_e0_amendment_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Require the complete E0 amendment before E01 may execute."""

    try:
        execution = payload["execution"]
        matrix = payload["matrix_validation"]
        metric = payload["metric_contract"]
        shards = execution["shards"]
        revision = str(execution["code_revision"])
        completed = int(execution["completed_item_count"])
        artifact_count = int(matrix["artifact_count"])
        expected_count = int(matrix["expected_artifact_count"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("E0 prerequisite payload is incomplete") from exc

    shard_ids = {int(row.get("shard", -1)) for row in shards}
    finish_ids = [
        str(artifact_id)
        for row in shards
        for artifact_id in row.get("item_finish_ids", [])
    ]
    checks = {
        "schema_version": payload.get("schema_version") == 1,
        "report_name": payload.get("report_name")
        == "E0 full-tail common-evaluator dated amendment",
        "revision": len(revision) == 40
        and all(character in "0123456789abcdef" for character in revision),
        "completed_item_count": completed == EXPECTED_E0_ARTIFACT_COUNT,
        "artifact_count": artifact_count == EXPECTED_E0_ARTIFACT_COUNT,
        "expected_artifact_count": expected_count == EXPECTED_E0_ARTIFACT_COUNT,
        "all_contract_checks_pass": matrix.get("all_contract_checks_pass") is True,
        "shards": shard_ids == {0, 1},
        "finish_count": len(finish_ids) == EXPECTED_E0_ARTIFACT_COUNT,
        "finish_unique": len(finish_ids) == len(set(finish_ids)),
        "metric_version": metric.get("version") == "e0_full_tail_v2",
        "tail_batch": metric.get("tail_batch_included") is True,
        "aggregation": metric.get("aggregation_weight") == "row",
        "candidate_universe": metric.get("candidate_universe")
        == "all_mapped_real_catalog_items_exactly_once",
        "eval_seed": metric.get("eval_seed") == RANDOM_SEED,
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise ValueError("E0 prerequisite failed: " + ", ".join(failed))
    return {
        "code_revision": revision,
        "completed_item_count": completed,
        "artifact_count": artifact_count,
        "payload_sha256": _json_sha256(payload),
    }


def validate_e0_amendment_file(path: Path | str) -> dict[str, Any]:
    path = Path(path)
    actual_sha256 = sha256_file(path)
    accepted_sha256 = actual_sha256
    if actual_sha256 != EXPECTED_E0_AMENDMENT_SHA256:
        # Git stores this frozen JSON with LF endings.  A Windows checkout may
        # expose CRLF bytes, so compare a newline-normalized representation
        # while still rejecting any added/removed content (including an extra
        # trailing newline).  Raw source hashes remain available in provenance.
        normalized_sha256 = hashlib.sha256(
            path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
        ).hexdigest()
        if normalized_sha256 == EXPECTED_E0_AMENDMENT_SHA256:
            accepted_sha256 = normalized_sha256
        else:
            raise ValueError(
                "authoritative E0 amendment hash mismatch: "
                f"expected {EXPECTED_E0_AMENDMENT_SHA256}, got {actual_sha256}"
            )
    payload = json.loads(path.read_text(encoding="utf-8"))
    evidence = validate_e0_amendment_payload(payload)
    if evidence["code_revision"] != EXPECTED_E0_CODE_REVISION:
        raise ValueError(
            "authoritative E0 amendment revision mismatch: "
            f"expected {EXPECTED_E0_CODE_REVISION}, got {evidence['code_revision']}"
        )
    return {
        **evidence,
        "path": str(path.resolve()),
        "file_sha256": accepted_sha256,
        "raw_file_sha256": actual_sha256,
    }


def validate_config_contract(configs: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Fail unless the arms differ only at the pre-registered path switches."""

    if tuple(configs.keys()) != ARM_NAMES and set(configs) != set(ARM_NAMES):
        raise ValueError(f"config mismatch: expected arms {ARM_NAMES}, got {sorted(configs)}")

    flattened = {arm: _flatten_mapping(configs[arm]) for arm in ARM_NAMES}
    for path, expected_by_arm in CONFIG_DIFFERENCE_ALLOWLIST.items():
        for arm in ARM_NAMES:
            observed = flattened[arm].get(path, object())
            expected = expected_by_arm[arm]
            if observed != expected:
                raise ValueError(
                    f"config mismatch at {path} for {arm}: expected {expected!r}, got {observed!r}"
                )

    selector: dict[str, Any] = {}
    for key, expected in SELECTOR_CONTRACT.items():
        path = f"training.{key}"
        for arm in ARM_NAMES:
            observed = flattened[arm].get(path, object())
            if observed != expected:
                raise ValueError(
                    f"config mismatch at {path} for {arm}: expected {expected!r}, got {observed!r}"
                )
        selector[key] = expected

    for arm in ARM_NAMES:
        required = {
            "random_seed": RANDOM_SEED,
            "training.data": DATASET_NAME,
            "data.Beauty.item_num": EXPECTED_ITEM_COUNT,
            "training.batch_size": 256,
            "training.accum": 1,
            "loss_type": "score_entropy",
            "text_side.kernel_version": "v2",
            "text_side.injection_mode": "kernel",
        }
        for path, expected in required.items():
            observed = flattened[arm].get(path, object())
            if observed != expected:
                raise ValueError(
                    f"config mismatch at {path} for {arm}: expected {expected!r}, got {observed!r}"
                )

    normalized: dict[str, dict[str, Any]] = {}
    for arm in ARM_NAMES:
        current = dict(flattened[arm])
        current.pop("work_dir", None)
        for path in CONFIG_DIFFERENCE_ALLOWLIST:
            current[path] = "<allowed-arm-switch>"
        normalized[arm] = current

    reference = normalized[REFERENCE_ARM]
    for arm in ARM_NAMES[1:]:
        keys = sorted(set(reference) | set(normalized[arm]))
        for path in keys:
            if reference.get(path, object()) != normalized[arm].get(path, object()):
                raise ValueError(
                    f"config mismatch at {path}: host={reference.get(path)!r}, "
                    f"{arm}={normalized[arm].get(path)!r}"
                )

    return {
        "status": "pass",
        "selector": selector,
        "normalized_config_sha256": _json_sha256(reference),
        "allowed_differences": CONFIG_DIFFERENCE_ALLOWLIST,
    }


def require_identical_arm_metadata(label: str, values: Mapping[str, str]) -> str:
    if set(values) != set(ARM_NAMES):
        raise ValueError(f"{label} mismatch: missing or unexpected arms")
    distinct = set(values.values())
    if len(distinct) != 1:
        detail = ", ".join(f"{arm}={values[arm]}" for arm in ARM_NAMES)
        raise ValueError(f"{label} mismatch: {detail}")
    return values[REFERENCE_ARM]


def _stable_value(value: Any) -> Any:
    if isinstance(value, torch.Tensor):
        tensor = value.detach().cpu().contiguous()
        digest = hashlib.sha256()
        digest.update(str(tensor.dtype).encode("ascii"))
        digest.update(json.dumps(list(tensor.shape)).encode("ascii"))
        digest.update(tensor.numpy().tobytes(order="C"))
        return {
            "kind": "tensor",
            "dtype": str(tensor.dtype),
            "shape": list(tensor.shape),
            "sha256": digest.hexdigest(),
        }
    if isinstance(value, float):
        if not math.isfinite(value):
            return {"kind": "float", "value": repr(value)}
        return {"kind": "float", "value": float(value)}
    if isinstance(value, (str, int, bool)) or value is None:
        return {"kind": type(value).__name__, "value": value}
    return {"kind": type(value).__name__, "value": repr(value)}


def _value_sha256(value: Any) -> str:
    return _json_sha256(_stable_value(value))


def _set_execution_context(**updates: Any) -> dict[str, Any]:
    """Update non-random provenance for the current production boundary."""

    global LAST_EXECUTION_CONTEXT
    LAST_EXECUTION_CONTEXT = {**LAST_EXECUTION_CONTEXT, **updates}
    return deepcopy(LAST_EXECUTION_CONTEXT)


def _parameter_device_counts(parameters: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for parameter in parameters:
        device = str(getattr(parameter, "device", "unknown"))
        counts[device] = counts.get(device, 0) + 1
    return dict(sorted(counts.items()))


def build_execution_failure_report(
    exc: BaseException,
    *,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    import traceback

    execution_context = dict(LAST_EXECUTION_CONTEXT if context is None else context)
    return {
        "schema_version": 1,
        "report_name": "AAAI-E01 deterministic production-path g-zero trace",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "fail",
        "protocol": {
            "dataset": DATASET_NAME,
            "random_seed": RANDOM_SEED,
            "trace_steps": list(TRACE_STEPS),
            "fp32_tolerance": FP32_TOLERANCE,
            "scope_decision": PROTOCOL_SCOPE_DECISION,
        },
        "first_divergence": {
            "step": execution_context.get("trace_step"),
            "category": "preflight_or_execution_error",
            "key": type(exc).__name__,
            "detail": str(exc),
        },
        "exception": {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": "".join(
                traceback.format_exception(type(exc), exc, exc.__traceback__)
            ),
        },
        "execution_context": execution_context,
        "downstream_launch_authorized": False,
    }


def _tensor_layout_metadata(value: torch.Tensor) -> dict[str, Any]:
    """Return bounded, non-random provenance for a sampler tensor."""

    tensor = value.detach()
    float_tensor = tensor.float()
    finite = torch.isfinite(float_tensor)
    if bool(finite.any().item()):
        finite_values = float_tensor[finite]
        value_min = float(finite_values.min().item())
        value_max = float(finite_values.max().item())
        value_sum = float(finite_values.sum().item())
    else:
        value_min = None
        value_max = None
        value_sum = None
    row_sum_min = None
    row_sum_max = None
    row_sum_mean = None
    if tensor.dim() >= 1:
        rows = float_tensor.reshape(-1, tensor.shape[-1]).sum(dim=-1)
        row_sum_min = float(rows.min().item())
        row_sum_max = float(rows.max().item())
        row_sum_mean = float(rows.mean().item())
    return {
        "dtype": str(tensor.dtype),
        "device": str(tensor.device),
        "shape": [int(size) for size in tensor.shape],
        "stride": [int(stride) for stride in tensor.stride()],
        "is_contiguous": bool(tensor.is_contiguous()),
        "is_floating_point": bool(tensor.is_floating_point()),
        "finite": bool(finite.all().item()),
        "min": value_min,
        "max": value_max,
        "sum": value_sum,
        "row_sum_min": row_sum_min,
        "row_sum_max": row_sum_max,
        "row_sum_mean": row_sum_mean,
        "sha256": _value_sha256(tensor),
    }


def _compare_values(reference: Any, observed: Any) -> tuple[bool, float | None, str]:
    reference_hash = _value_sha256(reference)
    observed_hash = _value_sha256(observed)
    if isinstance(reference, torch.Tensor) and isinstance(observed, torch.Tensor):
        if tuple(reference.shape) != tuple(observed.shape):
            return False, None, "shape_mismatch"
        if reference.dtype.is_floating_point or observed.dtype.is_floating_point:
            lhs = reference.detach().cpu().float()
            rhs = observed.detach().cpu().float()
            difference = float((lhs - rhs).abs().max().item()) if lhs.numel() else 0.0
            if not math.isfinite(difference):
                return False, None, "nonfinite_fp32_difference"
            return difference <= FP32_TOLERANCE, difference, "fp32_tolerance"
        equal = torch.equal(reference.detach().cpu(), observed.detach().cpu())
        return equal, 0.0 if equal else None, "exact_tensor"
    equal = type(reference) is type(observed) and reference == observed
    if not equal and isinstance(reference, (int, float)) and isinstance(observed, (int, float)):
        difference = abs(float(reference) - float(observed))
        return difference <= FP32_TOLERANCE, difference, "fp32_tolerance"
    return equal, 0.0 if equal else None, "exact_value"


def compare_checkpoint_snapshots(
    *,
    step: int,
    snapshots: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> dict[str, Any]:
    if int(step) not in TRACE_STEPS:
        raise ValueError(f"unregistered trace step: {step}")
    if set(snapshots) != set(ARM_NAMES):
        raise ValueError("snapshot arms do not match the frozen E01 arm set")

    comparisons: list[dict[str, Any]] = []
    reference_snapshot = snapshots[REFERENCE_ARM]
    categories = sorted(
        set().union(*(set(snapshot.keys()) for snapshot in snapshots.values()))
    )
    for category in categories:
        reference_values = reference_snapshot.get(category, {})
        keys = sorted(
            set().union(
                *(set(snapshot.get(category, {}).keys()) for snapshot in snapshots.values())
            ),
            key=lambda key: (
                0 if category == "optimizer" and key.endswith(".in_optimizer") else 1,
                key,
            ),
        )
        for key in keys:
            reference_present = key in reference_values
            reference_value = reference_values.get(key)
            for arm in ARM_NAMES[1:]:
                observed_values = snapshots[arm].get(category, {})
                observed_present = key in observed_values
                if not reference_present or not observed_present:
                    passed, max_abs_diff, rule = False, None, "topology_exact"
                    observed_value = observed_values.get(key)
                else:
                    observed_value = observed_values[key]
                    passed, max_abs_diff, rule = _compare_values(reference_value, observed_value)
                comparisons.append(
                    {
                        "category": category,
                        "key": key,
                        "reference_arm": REFERENCE_ARM,
                        "arm": arm,
                        "status": "pass" if passed else "fail",
                        "comparison_rule": rule,
                        "max_abs_diff": max_abs_diff,
                        "reference_sha256": _value_sha256(reference_value)
                        if reference_present
                        else None,
                        "observed_sha256": _value_sha256(observed_value)
                        if observed_present
                        else None,
                    }
                )

    first_failed = next((row for row in comparisons if row["status"] == "fail"), None)
    first_divergence = None
    if first_failed is not None:
        first_divergence = {"step": int(step), **first_failed}
    arm_hashes = {
        arm: _json_sha256(
            {
                category: {
                    key: _stable_value(value)
                    for key, value in sorted(values.items())
                }
                for category, values in sorted(snapshots[arm].items())
            }
        )
        for arm in ARM_NAMES
    }
    return {
        "step": int(step),
        "status": "fail" if first_divergence else "pass",
        "fp32_tolerance": FP32_TOLERANCE,
        "arm_hashes": arm_hashes,
        "comparisons": comparisons,
        "first_divergence": first_divergence,
    }


def snapshot_optimizer_state(
    optimizer: torch.optim.Optimizer,
    canonical_parameters: Mapping[str, torch.nn.Parameter],
) -> dict[str, Any]:
    """Represent optimizer state by canonical parameter name without normalizing topology."""

    snapshot: dict[str, Any] = {
        "optimizer.class": optimizer.__class__.__qualname__,
        "optimizer.param_group_count": len(optimizer.param_groups),
    }
    membership: dict[int, tuple[int, Mapping[str, Any]]] = {}
    for group_index, group in enumerate(optimizer.param_groups):
        for parameter in group["params"]:
            membership[id(parameter)] = (group_index, group)

    for name, parameter in sorted(canonical_parameters.items()):
        member = membership.get(id(parameter))
        prefix = name
        snapshot[f"{prefix}.in_optimizer"] = member is not None
        state = optimizer.state.get(parameter, {}) if member is not None else {}
        snapshot[f"{prefix}.state_field_count"] = len(state)
        if member is not None:
            group_index, group = member
            snapshot[f"{prefix}.group_index"] = group_index
            for hyperparameter in (
                "lr",
                "betas",
                "eps",
                "weight_decay",
                "amsgrad",
                "maximize",
                "capturable",
                "differentiable",
                "fused",
            ):
                if hyperparameter in group:
                    snapshot[f"{prefix}.group.{hyperparameter}"] = deepcopy(
                        group[hyperparameter]
                    )
        for state_name, state_value in sorted(state.items()):
            if isinstance(state_value, torch.Tensor):
                snapshot[f"{prefix}.state.{state_name}"] = state_value.detach().cpu().clone()
            else:
                snapshot[f"{prefix}.state.{state_name}"] = deepcopy(state_value)
    return snapshot


def copy_host_initialization_to_proposal(
    *,
    host_model: torch.nn.Module,
    host_graph: torch.nn.Module,
    proposal_model: torch.nn.Module,
) -> dict[str, Any]:
    """Copy the canonical host initialization without altering parameter ownership."""

    if not hasattr(host_graph, "p1"):
        raise ValueError("canonical host graph has no p1 parameter")
    builder = getattr(proposal_model, "text_side_builder", None)
    if builder is None or getattr(builder, "p1", None) is None:
        raise ValueError("proposal model has no v2 text_side_builder.p1 parameter")

    incompatible = proposal_model.load_state_dict(host_model.state_dict(), strict=False)
    missing = sorted(incompatible.missing_keys)
    unexpected = sorted(incompatible.unexpected_keys)
    if unexpected:
        raise ValueError(f"unexpected host initialization keys: {unexpected}")
    if not missing or any(
        not key.startswith("text_side_builder.") for key in missing
    ):
        raise ValueError(
            "proposal initialization missing-key topology is not the registered "
            f"text-side extension: {missing}"
        )
    if "text_side_builder.p1" not in missing:
        raise ValueError("proposal initialization did not expose text_side_builder.p1")
    if tuple(builder.p1.shape) != tuple(host_graph.p1.shape):
        raise ValueError(
            "canonical p1 shape mismatch: "
            f"host={tuple(host_graph.p1.shape)}, proposal={tuple(builder.p1.shape)}"
        )
    with torch.no_grad():
        builder.p1.copy_(host_graph.p1.to(builder.p1.device, dtype=builder.p1.dtype))

    host_state = host_model.state_dict()
    proposal_state = proposal_model.state_dict()
    for key, host_value in host_state.items():
        proposal_value = proposal_state[key]
        if not torch.equal(
            host_value.detach().cpu(), proposal_value.detach().cpu()
        ):
            raise ValueError(f"canonical shared state copy mismatch at {key}")
    if not torch.equal(
        host_graph.p1.detach().cpu(), builder.p1.detach().cpu()
    ):
        raise ValueError("canonical core proposal logits copy mismatch")
    return {
        "expected_missing_keys": missing,
        "unexpected_keys": unexpected,
        "shared_state_key_count": len(host_state),
        "host_shared_state_sha256": _json_sha256(
            {
                key: _stable_value(value)
                for key, value in sorted(host_state.items())
            }
        ),
    }


class GraphTraceProxy:
    """Observe production graph boundaries without changing their implementation."""

    def __init__(self, graph: Any) -> None:
        self.graph = graph
        self.records: dict[str, torch.Tensor] = {}

    def reset(self) -> None:
        self.records = {}

    def __getattr__(self, name: str) -> Any:
        return getattr(self.graph, name)

    def _invoke(self, method_name: str, *args: Any, proposal: Any = None) -> Any:
        method = getattr(self.graph, method_name)
        if proposal is None:
            return method(*args)
        return method(*args, proposal=proposal)

    def sample_prob(self, *args: Any, proposal: Any = None) -> Any:
        result = self._invoke("sample_prob", *args, proposal=proposal)
        self.records["perturbed_target"] = result.detach().clone()
        if proposal is not None:
            self.records["proposal_rows"] = proposal.detach().clone()
        return result

    def score_entropy(self, *args: Any, proposal: Any = None) -> Any:
        result = self._invoke("score_entropy", *args, proposal=proposal)
        self.records["log_score"] = args[0].detach().clone()
        self.records["raw_score_entropy"] = result.detach().clone()
        if proposal is not None:
            self.records["proposal_rows"] = proposal.detach().clone()
        return result


class NoiseTraceProxy:
    def __init__(self, noise: Any) -> None:
        self.noise = noise
        self.records: dict[str, torch.Tensor] = {}

    def reset(self) -> None:
        self.records = {}

    def __getattr__(self, name: str) -> Any:
        return getattr(self.noise, name)

    def __call__(self, t: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        sigma, dsigma = self.noise(t)
        self.records = {
            "t": t.detach().clone(),
            "sigma": sigma.detach().clone(),
            "dsigma": dsigma.detach().clone(),
        }
        return sigma, dsigma


@dataclass
class ArmRuntime:
    name: str
    cfg: Any
    device: torch.device
    graph: Any
    model: torch.nn.Module
    ema: Any
    noise: torch.nn.Module
    optimizer: torch.optim.Optimizer
    scaler: Any
    state: dict[str, Any]
    train_loader: Any
    val_loader: Any
    test_loader: Any
    val_iter: Any
    graph_trace: GraphTraceProxy
    noise_trace: NoiseTraceProxy
    train_step_fn: Any
    eval_step_fn: Any
    sampling_fns: dict[str, Any]
    rng_state: dict[str, Any]
    construction_rng_metadata: dict[str, Any] = field(default_factory=dict)
    trace_start_rng_metadata: dict[str, Any] = field(default_factory=dict)
    initial_sampling_rng_trace: dict[str, Any] = field(default_factory=dict)
    train_iter: Any = None
    batch_hashes: list[str] = field(default_factory=list)
    last_gradients: dict[str, Any] = field(default_factory=dict)
    last_loss: torch.Tensor | None = None
    last_batch: dict[str, torch.Tensor] | None = None
    initial_sampling_metrics: dict[str, Any] = field(default_factory=dict)
    selector_metrics: dict[str, Any] = field(default_factory=dict)


def canonical_parameters(runtime: ArmRuntime) -> dict[str, torch.nn.Parameter]:
    named: dict[str, torch.nn.Parameter] = {}
    for name, parameter in runtime.model.named_parameters():
        if name == "text_side_builder.p1":
            named["core_proposal_logits"] = parameter
        elif name.startswith("text_side_builder."):
            raise ValueError(f"unexpected learnable text-side parameter: {name}")
        else:
            named[f"model.{name}"] = parameter
    if runtime.name == "host":
        if "core_proposal_logits" in named:
            raise ValueError("host unexpectedly owns model.text_side_builder.p1")
        named["core_proposal_logits"] = runtime.graph.p1
    if "core_proposal_logits" not in named:
        raise ValueError(f"{runtime.name} has no canonical core proposal logits")
    for name, parameter in runtime.noise.named_parameters():
        named[f"noise.{name}"] = parameter
    return dict(sorted(named.items()))


def snapshot_parameters(runtime: ArmRuntime) -> dict[str, torch.Tensor]:
    return {
        name: parameter.detach().cpu().clone()
        for name, parameter in canonical_parameters(runtime).items()
    }


def snapshot_gradients(
    runtime: ArmRuntime,
    *,
    grad_scale: float = 1.0,
) -> dict[str, Any]:
    gradients: dict[str, Any] = {}
    scale = float(grad_scale)
    for name, parameter in canonical_parameters(runtime).items():
        if parameter.grad is None:
            gradients[name] = "<none>"
        else:
            gradients[name] = parameter.grad.detach().cpu().float().clone() / scale
    return gradients


def hash_batch(batch: Mapping[str, torch.Tensor]) -> str:
    return _json_sha256(
        {
            key: _stable_value(value.detach().cpu())
            for key, value in sorted(batch.items())
        }
    )


def _next_training_batch(runtime: ArmRuntime) -> dict[str, torch.Tensor]:
    if runtime.train_iter is None:
        runtime.train_iter = iter(runtime.train_loader)
    try:
        batch = next(runtime.train_iter)
    except StopIteration:
        runtime.train_iter = iter(runtime.train_loader)
        batch = next(runtime.train_iter)
    runtime.batch_hashes.append(hash_batch(batch))
    return batch


def _host_proposal_rows(runtime: ArmRuntime, batch_size: int) -> torch.Tensor:
    proposal = runtime.graph.nonpreference_probs()
    return proposal.unsqueeze(0).expand(batch_size, -1)


def _probe_proposal_rows(
    runtime: ArmRuntime,
    batch: Mapping[str, torch.Tensor],
) -> torch.Tensor:
    history = batch["seq"].to(runtime.device)
    with torch.no_grad():
        context = runtime.model.encode_history_context(history)
    proposal = context.get("proposal")
    if proposal is None:
        proposal = _host_proposal_rows(runtime, history.shape[0])
    return proposal.detach().cpu().clone()


def _loss_term_snapshot(runtime: ArmRuntime) -> dict[str, Any]:
    records: dict[str, Any] = {}
    records.update(
        {
            key: value.detach().cpu().clone()
            for key, value in runtime.noise_trace.records.items()
        }
    )
    records.update(
        {
            key: value.detach().cpu().clone()
            for key, value in runtime.graph_trace.records.items()
            if key != "proposal_rows"
        }
    )
    raw = runtime.graph_trace.records.get("raw_score_entropy")
    dsigma = runtime.noise_trace.records.get("dsigma")
    if raw is not None and dsigma is not None:
        records["weighted_loss_per_row"] = (
            dsigma[:, None] * raw
        ).mean(dim=-1).detach().cpu().clone()
    if runtime.last_loss is not None:
        records["training_loss"] = runtime.last_loss.detach().cpu().clone()
    return records


def _runtime_snapshot(
    runtime: ArmRuntime,
    *,
    proposal_rows: torch.Tensor,
    sampling_probe_logits: torch.Tensor,
) -> dict[str, dict[str, Any]]:
    current_batch_hash = runtime.batch_hashes[-1] if runtime.batch_hashes else "<step0>"
    return {
        "batch_order": {
            "current_batch_sha256": current_batch_hash,
            "cumulative_batch_sha256": _json_sha256(runtime.batch_hashes),
        },
        "gradients": deepcopy(runtime.last_gradients),
        "loss_terms": _loss_term_snapshot(runtime),
        "optimizer": snapshot_optimizer_state(
            runtime.optimizer, canonical_parameters(runtime)
        ),
        "parameters": snapshot_parameters(runtime),
        "proposal_rows": {"proposal": proposal_rows.detach().cpu().clone()},
        "rng": rng_state_metadata(runtime.rng_state),
        "sampling_probe": {
            **deepcopy(runtime.selector_metrics or runtime.initial_sampling_metrics),
            "p5_logits": sampling_probe_logits.detach().cpu().clone(),
        },
    }


def build_trace_report(
    *,
    e0: Mapping[str, Any],
    assets: Mapping[str, Any],
    config_contract: Mapping[str, Any],
    checkpoints: list[Mapping[str, Any]],
    source_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    observed_steps = tuple(int(checkpoint.get("step", -1)) for checkpoint in checkpoints)
    if observed_steps != TRACE_STEPS:
        raise ValueError(
            f"trace checkpoint steps mismatch: expected {TRACE_STEPS}, got {observed_steps}"
        )
    first_divergence = next(
        (
            checkpoint.get("first_divergence")
            for checkpoint in checkpoints
            if checkpoint.get("first_divergence") is not None
        ),
        None,
    )
    return {
        "schema_version": 1,
        "report_name": "AAAI-E01 deterministic production-path g-zero trace",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "fail" if first_divergence is not None else "pass",
        "protocol": {
            "dataset": DATASET_NAME,
            "random_seed": RANDOM_SEED,
            "trace_steps": list(TRACE_STEPS),
            "fp32_tolerance": FP32_TOLERANCE,
            "scope_decision": PROTOCOL_SCOPE_DECISION,
            "arms": list(ARM_NAMES),
            "reference_arm": REFERENCE_ARM,
            "canonical_mapping_policy": (
                "canonical names align shared values only; real parameter ownership and "
                "optimizer membership are never normalized"
            ),
        },
        "e0_prerequisite": dict(e0),
        "beauty_assets": dict(assets),
        "config_contract": dict(config_contract),
        "production_call_path": dict(source_manifest),
        "checkpoints": list(checkpoints),
        "first_divergence": first_divergence,
        "downstream_launch_authorized": first_divergence is None,
    }


def build_arm_configs(
    *,
    dataset_dir: Path | str,
    text_utility_report_path: Path | str,
    output_dir: Path | str,
) -> dict[str, Any]:
    """Compose the exact frozen Beauty production configs for all three arms."""

    from omegaconf import OmegaConf

    repo_root = Path(__file__).resolve().parents[1]
    config_dir = repo_root / "configs"
    dataset_dir = Path(dataset_dir)
    utility_path = Path(text_utility_report_path)
    output_dir = Path(output_dir)
    base = OmegaConf.load(config_dir / "config.yaml")
    model_config = OmegaConf.load(config_dir / "model" / "small.yaml")
    if "defaults" in base:
        del base["defaults"]
    base.model = model_config

    common_updates = {
        "random_seed": RANDOM_SEED,
        "cuda": 0,
        "loss_type": "score_entropy",
        "training.data": DATASET_NAME,
        "training.batch_size": 256,
        "training.accum": 1,
        "training.n_iters": 2_000_000,
        "training.eval_freq": 1000,
        "training.snapshot_freq": 1000,
        "training.snapshot_freq_for_preemption": 1000,
        "training.snapshot_sampling": True,
        "training.nonpreference_user_ratio": 0.1,
        "training.early_stop_patience": SELECTOR_CONTRACT["early_stop_patience"],
        "training.early_stop_min_step": SELECTOR_CONTRACT["early_stop_min_step"],
        "training.best_selection_min_step": SELECTOR_CONTRACT[
            "best_selection_min_step"
        ],
        "training.early_stop_metric": SELECTOR_CONTRACT["early_stop_metric"],
        "training.early_stop_strength": SELECTOR_CONTRACT["early_stop_strength"],
        "training.early_stop_min_delta": SELECTOR_CONTRACT["early_stop_min_delta"],
        "training.write_snapshot_checkpoint": False,
        "training.write_best_checkpoint": True,
        "data.Beauty.path": str(dataset_dir),
        "data.Beauty.item_num": EXPECTED_ITEM_COUNT,
        "data.Beauty.seq_len": 10,
        "graph.is_disliked_item": True,
        "model.hidden_size": 256,
        "model.cond_dim": 256,
        "model.score_flag": False,
        "model.score_method": "oricos",
        "optim.lr": 0.0001,
        "text_side.dataset_dir": str(dataset_dir),
        "text_side.text_bank_path": str(dataset_dir / "text_bank.csv"),
        "text_side.embeddings_path": str(
            dataset_dir / "sentence_t5_xl_item_emb.pt"
        ),
        "text_side.agreement_null_curve_path": str(
            dataset_dir / "agreement_null_curves.json"
        ),
        "text_side.text_utility_report_path": str(utility_path),
        "text_side.kernel_version": "v2",
        "text_side.temperature": 0.2,
        "text_side.g_max": 0.5,
        "text_side.agreement_k": 2.0,
        "text_side.agreement_weight": 0.45,
        "text_side.completeness_weight": 0.15,
        "text_side.history_reliability_weight": 0.40,
        "text_side.ess_weight": 0.20,
        "text_side.recency_weight": 0.30,
        "text_side.stability_weight": 0.50,
        "text_side.max_temperature_scale": 2.0,
        "text_side.min_pseudo_mass": 0.05,
        "text_side.popularity_mix_scale": 1.0,
        "text_side.popularity_mix_power": 1.0,
        "text_side.pseudo_mass_scale": 1.0,
        "text_side.pseudo_mass_power": 1.0,
        "text_side.center_embeddings": False,
        "text_side.injection_mode": "kernel",
    }

    configs: dict[str, Any] = {}
    for arm in ARM_NAMES:
        cfg = OmegaConf.create(OmegaConf.to_container(base, resolve=False))
        for path, value in common_updates.items():
            OmegaConf.update(cfg, path, value, merge=False, force_add=True)
        cfg.work_dir = str(output_dir / arm)
        cfg.graph.type = CONFIG_DIFFERENCE_ALLOWLIST["graph.type"][arm]
        cfg.text_side.enabled = CONFIG_DIFFERENCE_ALLOWLIST["text_side.enabled"][arm]
        cfg.text_side.ablation_mode = CONFIG_DIFFERENCE_ALLOWLIST[
            "text_side.ablation_mode"
        ][arm]
        configs[arm] = cfg
    return configs


def configs_to_plain_dicts(configs: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    from omegaconf import OmegaConf

    return {
        arm: OmegaConf.to_container(configs[arm], resolve=True)
        for arm in ARM_NAMES
    }


def _require_identical_initial_values(runtimes: Mapping[str, ArmRuntime]) -> str:
    snapshots = {arm: snapshot_parameters(runtimes[arm]) for arm in ARM_NAMES}
    reference = snapshots[REFERENCE_ARM]
    for arm in ARM_NAMES[1:]:
        if set(reference) != set(snapshots[arm]):
            raise ValueError(
                "unexpected canonical state-hash mismatch: parameter topology differs "
                f"between host and {arm}"
            )
        for name in sorted(reference):
            if not torch.equal(reference[name], snapshots[arm][name]):
                difference = float(
                    (reference[name].float() - snapshots[arm][name].float())
                    .abs()
                    .max()
                    .item()
                )
                raise ValueError(
                    "unexpected canonical state-hash mismatch at "
                    f"{name} for {arm}; max_abs_diff={difference}"
                )
    return _json_sha256(
        {name: _stable_value(value) for name, value in sorted(reference.items())}
    )


def _run_initial_production_sampling(runtime: ArmRuntime, utils_module: Any) -> None:
    include_cuda = runtime.device.type == "cuda"
    trace: dict[str, Any] = {
        "before_eval": rng_state_metadata(
            capture_rng_state(include_cuda=include_cuda)
        ),
        "iterator_before": None,
        "iterator_after": None,
        "sampling_calls": [],
    }
    restore_rng_state(runtime.rng_state)
    trace["before_eval"] = rng_state_metadata(
        capture_rng_state(include_cuda=include_cuda)
    )
    original_loader = runtime.val_loader
    original_sampler = runtime.sampling_fns["p2"]["fn"]
    stage_probe: dict[str, Any] = {
        "context": None,
        "graph_initial": None,
        "categorical_calls": [],
    }

    def state_metadata() -> dict[str, Any]:
        return rng_state_metadata(capture_rng_state(include_cuda=include_cuda))

    def run_with_stage_probe(model, batch_dims, history):
        if stage_probe["context"] is not None:
            return original_sampler(model, batch_dims, history)

        original_context = getattr(runtime.model, "encode_history_context", None)
        original_graph_sampler = getattr(runtime.graph, "sample_nonpreference")
        import graph_lib
        import sampling as sampling_module

        original_categorical = sampling_module.sample_categorical

        def traced_context(context_history):
            before = state_metadata()
            result = original_context(context_history)
            after = state_metadata()
            stage_probe["context"] = {
                "before": before,
                "after": after,
                "history_shape": [int(value) for value in context_history.shape],
            }
            return result

        def traced_graph_sampler(*args, **kwargs):
            if stage_probe["graph_initial"] is not None:
                return original_graph_sampler(*args, **kwargs)
            before = state_metadata()
            row_probe: dict[str, Any] = {"call_count": 0}
            original_row_sampler = graph_lib._sample_probability_rows

            def traced_row_sampler(probabilities, batch_shape):
                row_probe["call_count"] += 1
                if "input" in row_probe:
                    return original_row_sampler(probabilities, batch_shape)
                row_probe["batch_shape"] = [int(value) for value in batch_shape]
                row_probe["input"] = _tensor_layout_metadata(probabilities)
                row_before = state_metadata()
                result = original_row_sampler(probabilities, batch_shape)
                row_after = state_metadata()
                row_probe["output"] = _tensor_layout_metadata(result)
                row_probe["rng_before"] = row_before
                row_probe["rng_after"] = row_after
                return result

            graph_lib._sample_probability_rows = traced_row_sampler
            try:
                result = original_graph_sampler(*args, **kwargs)
            finally:
                graph_lib._sample_probability_rows = original_row_sampler
            after = state_metadata()
            stage_probe["graph_initial"] = {
                "before": before,
                "after": after,
                "output_shape": [int(value) for value in result.shape],
                "output": _tensor_layout_metadata(result),
                "probability_rows": row_probe,
            }
            return result

        def traced_categorical(probabilities, method="hard"):
            before = state_metadata()
            result = original_categorical(probabilities, method=method)
            after = state_metadata()
            stage_probe["categorical_calls"].append(
                {
                    "before": before,
                    "after": after,
                    "method": method,
                    "probability_shape": [int(value) for value in probabilities.shape],
                    "output_shape": [int(value) for value in result.shape],
                }
            )
            return result

        if original_context is not None:
            setattr(runtime.model, "encode_history_context", traced_context)
        setattr(runtime.graph, "sample_nonpreference", traced_graph_sampler)
        sampling_module.sample_categorical = traced_categorical
        try:
            return original_sampler(model, batch_dims, history)
        finally:
            if original_context is not None:
                setattr(runtime.model, "encode_history_context", original_context)
            setattr(runtime.graph, "sample_nonpreference", original_graph_sampler)
            sampling_module.sample_categorical = original_categorical

    class _RngTracingLoader:
        def __iter__(self):
            trace["iterator_before"] = rng_state_metadata(
                capture_rng_state(include_cuda=include_cuda)
            )
            iterator = iter(original_loader)
            trace["iterator_after"] = rng_state_metadata(
                capture_rng_state(include_cuda=include_cuda)
            )
            return iterator

        def __len__(self):
            return len(original_loader)

    def traced_sampler(model, batch_dims, history):
        before = rng_state_metadata(
            capture_rng_state(include_cuda=include_cuda)
        )
        output = run_with_stage_probe(model, batch_dims, history)
        after = rng_state_metadata(
            capture_rng_state(include_cuda=include_cuda)
        )
        trace["sampling_calls"].append(
            {
                "batch_dims": [int(value) for value in batch_dims],
                "history_shape": [int(value) for value in history.shape],
                "before": before,
                "after": after,
            }
        )
        return output

    hr, ndcg = utils_module.evaluate_loader(
        runtime.model,
        traced_sampler,
        _RngTracingLoader(),
        runtime.device,
        EXPECTED_ITEM_COUNT,
    )
    trace["after_eval"] = rng_state_metadata(
        capture_rng_state(include_cuda=include_cuda)
    )
    trace["sampling_call_count"] = len(trace["sampling_calls"])
    trace["first_call_stage_probe"] = stage_probe
    runtime.initial_sampling_rng_trace = trace
    runtime.initial_sampling_metrics = {
        **{f"initial_val_p2_hr_{index}": float(value) for index, value in enumerate(hr)},
        **{
            f"initial_val_p2_ndcg_{index}": float(value)
            for index, value in enumerate(ndcg)
        },
    }
    runtime.rng_state = capture_rng_state(include_cuda=runtime.device.type == "cuda")


def _run_step_1000_production_boundary(
    runtime: ArmRuntime,
    *,
    single_train_module: Any,
) -> None:
    try:
        eval_batch = next(runtime.val_iter)
    except StopIteration:
        runtime.val_iter = iter(runtime.val_loader)
        eval_batch = next(runtime.val_iter)
    eval_batch = {
        key: value.to(runtime.device) for key, value in eval_batch.items()
    }
    eval_loss = runtime.eval_step_fn(
        runtime.state,
        eval_batch,
        int(runtime.cfg.sampling.steps),
    )
    val_results, test_results = single_train_module.run_eval_suite(
        runtime.model,
        runtime.ema,
        runtime.sampling_fns,
        runtime.val_loader,
        runtime.test_loader,
        runtime.device,
        EXPECTED_ITEM_COUNT,
    )
    selector_value = single_train_module.extract_metric(
        val_results,
        SELECTOR_CONTRACT["early_stop_strength"],
        SELECTOR_CONTRACT["early_stop_metric"],
    )
    runtime.selector_metrics = {
        "step1000_eval_loss": float(eval_loss.detach().cpu().item()),
        "step1000_selector_value": float(selector_value),
        "step1000_val_results_sha256": _json_sha256(val_results),
        "step1000_test_results_sha256": _json_sha256(test_results),
    }


def run_production_trace(args: argparse.Namespace) -> dict[str, Any]:
    """Execute the registered three-arm trace through production factories."""

    import data
    import dataset_runtime
    import graph_lib
    import losses
    import noise_lib
    import sampling
    import single_train
    import utils
    from model.ema import ExponentialMovingAverage
    from model.transformer import SEDD4REC

    _set_execution_context(
        phase="preflight",
        arm=None,
        trace_step=None,
        device=str(args.device),
        training_started=False,
    )
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError(
            f"isolated E01 output directory already exists: {output_dir}"
        )
    device = torch.device(args.device)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise ValueError(
            "E01 production trace requires an available CUDA device; CPU is not "
            "the registered production arithmetic path"
        )

    e0_path = Path(args.e0_amendment_path)
    e0_evidence = validate_e0_amendment_file(e0_path)
    asset_evidence = validate_beauty_asset_contract(
        args.dataset_dir,
        args.text_utility_report_path,
    )
    configs = build_arm_configs(
        dataset_dir=args.dataset_dir,
        text_utility_report_path=args.text_utility_report_path,
        output_dir=output_dir,
    )
    config_contract = validate_config_contract(configs_to_plain_dicts(configs))

    runtimes: dict[str, ArmRuntime] = {}
    initialization_evidence: dict[str, Any] = {}
    host_model: torch.nn.Module | None = None
    host_graph: Any = None
    host_noise: torch.nn.Module | None = None
    full_model: torch.nn.Module | None = None

    for arm in ARM_NAMES:
        cfg = configs[arm]
        _set_execution_context(
            phase="construction",
            arm=arm,
            trace_step=0,
            device=str(device),
            training_started=False,
        )
        single_train.setup_seed(RANDOM_SEED)
        dataset_runtime.reconcile_runtime_dataset_config(cfg)
        if int(cfg.data.Beauty.item_num) != EXPECTED_ITEM_COUNT:
            raise ValueError(
                "Beauty runtime item count changed after reconciliation: "
                f"{cfg.data.Beauty.item_num}"
            )

        graph = graph_lib.get_graph(cfg, device)
        model = SEDD4REC(cfg).to(device)
        if arm == "host":
            host_model = model
            host_graph = graph
            initialization_evidence[arm] = {
                "copy_source": "seed100 production constructor",
                "graph_p1_owner": "graph.p1",
            }
        else:
            if host_model is None or host_graph is None:
                raise RuntimeError("host must initialize before proposal arms")
            copy_evidence = copy_host_initialization_to_proposal(
                host_model=host_model,
                host_graph=host_graph,
                proposal_model=model,
            )
            if arm == "global_p":
                if full_model is None:
                    raise RuntimeError("full arm must initialize before global_p")
                model.load_state_dict(full_model.state_dict(), strict=True)
                copy_evidence["full_state_strict_copy"] = True
            else:
                full_model = model
            initialization_evidence[arm] = {
                **copy_evidence,
                "copy_source": "canonical host shared state + host graph.p1",
                "core_p1_owner": "model.text_side_builder.p1",
            }

        builder = getattr(model, "text_side_builder", None)
        if arm == "host":
            if builder is not None:
                raise ValueError("host unexpectedly enabled text-side proposal builder")
        else:
            if builder is None:
                raise ValueError(f"{arm} did not construct the production text-side builder")
            if float(builder.gate_dataset_scale) != 0.0:
                raise ValueError(
                    f"{arm} is not closed-gate: gate_dataset_scale={builder.gate_dataset_scale}"
                )
            if builder.kernel_version != "v2":
                raise ValueError(f"{arm} did not construct kernel_version=v2")
            if arm == "final_v2_closed_gate_full" and builder.ablation_mode != "none":
                raise ValueError("final-v2 full arm has the wrong ablation mode")
            if arm == "global_p" and builder.ablation_mode != "global_p":
                raise ValueError("global_p arm has the wrong ablation mode")

        ema = ExponentialMovingAverage(model.parameters(), decay=float(cfg.training.ema))
        noise = noise_lib.get_noise(cfg).to(device)
        if arm == "host":
            host_noise = noise
        else:
            if host_noise is None:
                raise RuntimeError("host noise must initialize first")
            noise.load_state_dict(host_noise.state_dict(), strict=True)

        optimizer_parameters = compose_optimizer_parameters(model, graph, noise)
        optimizer = losses.get_optimizer(cfg, optimizer_parameters)
        scaler = torch.cuda.amp.GradScaler()
        _set_execution_context(
            scaler_enabled=bool(scaler.is_enabled()),
            scaler_scale=float(scaler.get_scale()) if scaler.is_enabled() else None,
            model_parameter_devices=_parameter_device_counts(model.parameters()),
            graph_parameter_devices=_parameter_device_counts(graph.parameters()),
            noise_parameter_devices=_parameter_device_counts(noise.parameters()),
            optimizer_parameter_devices=_parameter_device_counts(optimizer_parameters),
            optimizer_class=optimizer.__class__.__qualname__,
            optimizer_param_group_count=len(optimizer.param_groups),
        )
        state = {
            "optimizer": optimizer,
            "scaler": scaler,
            "model": model,
            "noise": noise,
            "ema": ema,
            "step": 0,
        }
        train_loader, val_loader, test_loader = data.get_seqdataloader(cfg)
        val_iter = iter(val_loader)

        graph_trace = GraphTraceProxy(graph)
        noise_trace = NoiseTraceProxy(noise)
        base_optimize_fn = losses.optimization_manager(cfg)
        runtime_holder: dict[str, ArmRuntime] = {}

        def traced_optimize_fn(
            optimizer_arg: Any,
            scaler_arg: Any,
            parameters_arg: Any,
            step: int,
            *,
            _base_optimize_fn: Any = base_optimize_fn,
            _runtime_holder: dict[str, ArmRuntime] = runtime_holder,
        ) -> None:
            runtime = _runtime_holder["runtime"]
            grad_scale = float(scaler_arg.get_scale()) if scaler_arg.is_enabled() else 1.0
            runtime.last_gradients = snapshot_gradients(
                runtime,
                grad_scale=grad_scale,
            )
            parameter_list = list(parameters_arg)
            _base_optimize_fn(
                optimizer_arg,
                scaler_arg,
                parameter_list,
                step=step,
            )

        train_step_fn = losses.get_step_fn(
            noise_trace,
            graph_trace,
            True,
            cfg.loss_type,
            traced_optimize_fn,
            int(cfg.training.accum),
        )
        eval_step_fn = losses.get_step_fn(
            noise,
            graph,
            False,
            cfg.loss_type,
            base_optimize_fn,
            int(cfg.training.accum),
        )
        strengths = {"base": 1.0, "p2": 2.0, "p5": 5.0, "p10": 10.0}
        sampling_fns = {
            name: {
                "label": name,
                "fn": sampling.get_sampling_fn(
                    cfg,
                    graph,
                    noise,
                    1e-5,
                    strength,
                    device,
                ),
            }
            for name, strength in strengths.items()
        }
        runtime = ArmRuntime(
            name=arm,
            cfg=cfg,
            device=device,
            graph=graph,
            model=model,
            ema=ema,
            noise=noise,
            optimizer=optimizer,
            scaler=scaler,
            state=state,
            train_loader=train_loader,
            val_loader=val_loader,
            test_loader=test_loader,
            val_iter=val_iter,
            graph_trace=graph_trace,
            noise_trace=noise_trace,
            train_step_fn=train_step_fn,
            eval_step_fn=eval_step_fn,
            sampling_fns=sampling_fns,
            rng_state=capture_rng_state(include_cuda=True),
        )
        runtime_holder["runtime"] = runtime
        runtimes[arm] = runtime

    initialization_evidence["canonical_parameter_sha256"] = (
        _require_identical_initial_values(runtimes)
    )

    initialization_evidence["rng_boundary"] = normalize_trace_start_rng(runtimes)

    # single_train.py performs a p2 validation sampler pass before its first
    # training batch whenever snapshot_sampling=True.  Replay it per arm under
    # the arm-local RNG stream so step-0 RNG metadata matches production.
    for arm in ARM_NAMES:
        _set_execution_context(
            phase="initial_sampling",
            arm=arm,
            trace_step=0,
            training_started=False,
        )
        _run_initial_production_sampling(runtimes[arm], utils)
    initialization_evidence["initial_sampling_rng_trace"] = {
        arm: deepcopy(runtimes[arm].initial_sampling_rng_trace)
        for arm in ARM_NAMES
    }

    step0_proposals: dict[str, torch.Tensor] = {}
    step0_probe_batches: dict[str, dict[str, torch.Tensor]] = {}
    for arm in ARM_NAMES:
        runtime = runtimes[arm]
        saved_rng = runtime.rng_state
        restore_rng_state(saved_rng)
        probe_batch = next(iter(runtime.train_loader))
        step0_probe_batches[arm] = probe_batch
        step0_proposals[arm] = _probe_proposal_rows(runtime, probe_batch)
        runtime.model._cached_text_side_context = None
        restore_rng_state(saved_rng)
        runtime.rng_state = saved_rng

    step0_sampling_logits = {
        arm: run_forked_sampling_probe(
            model=runtimes[arm].model,
            sampling_fn=runtimes[arm].sampling_fns["p5"]["fn"],
            history=step0_probe_batches[arm]["seq"][:4].to(device),
            probe_seed=SAMPLING_PROBE_SEED_BASE,
            training_rng_state=runtimes[arm].rng_state,
            include_cuda=True,
        )
        for arm in ARM_NAMES
    }

    checkpoints: list[dict[str, Any]] = []
    step0_snapshots = {
        arm: _runtime_snapshot(
            runtimes[arm],
            proposal_rows=step0_proposals[arm],
            sampling_probe_logits=step0_sampling_logits[arm],
        )
        for arm in ARM_NAMES
    }
    checkpoints.append(compare_checkpoint_snapshots(step=0, snapshots=step0_snapshots))

    latest_proposals: dict[str, torch.Tensor] = {}
    for step in range(1, TRACE_STEPS[-1] + 1):
        batch_hash_by_arm: dict[str, str] = {}
        for arm in ARM_NAMES:
            runtime = runtimes[arm]
            _set_execution_context(
                phase="training",
                arm=arm,
                trace_step=step,
                device=str(runtime.device),
                training_started=True,
                scaler_enabled=bool(runtime.scaler.is_enabled()),
                scaler_scale=float(runtime.scaler.get_scale())
                if runtime.scaler.is_enabled()
                else None,
                model_parameter_devices=_parameter_device_counts(
                    runtime.model.parameters()
                ),
                graph_parameter_devices=_parameter_device_counts(
                    runtime.graph.parameters()
                ),
                noise_parameter_devices=_parameter_device_counts(
                    runtime.noise.parameters()
                ),
                optimizer_parameter_devices=_parameter_device_counts(
                    parameter
                    for group in runtime.optimizer.param_groups
                    for parameter in group["params"]
                ),
            )
            restore_rng_state(runtime.rng_state)
            runtime.graph_trace.reset()
            runtime.noise_trace.reset()
            batch = _next_training_batch(runtime)
            batch_hash_by_arm[arm] = runtime.batch_hashes[-1]
            batch = {key: value.to(device) for key, value in batch.items()}
            runtime.last_batch = batch
            previous_step = int(runtime.state["step"])
            loss = runtime.train_step_fn(
                runtime.state,
                batch,
                int(runtime.cfg.sampling.steps),
            )
            if int(runtime.state["step"]) != previous_step + 1:
                raise ValueError(
                    f"{arm} production step counter did not advance exactly once at trace step {step}"
                )
            runtime.last_loss = loss
            proposal = runtime.graph_trace.records.get("proposal_rows")
            if proposal is None:
                if arm != "host":
                    raise ValueError(f"{arm} loss path did not supply proposal rows")
                proposal = _host_proposal_rows(runtime, batch["seq"].shape[0])
            latest_proposals[arm] = proposal.detach().cpu().clone()

            if step == TRACE_STEPS[-1]:
                _set_execution_context(
                    phase="step1000_eval",
                    arm=arm,
                    trace_step=step,
                    device=str(runtime.device),
                    training_started=True,
                )
                _run_step_1000_production_boundary(
                    runtime,
                    single_train_module=single_train,
                )
            runtime.rng_state = capture_rng_state(include_cuda=True)

        require_identical_arm_metadata("batch_order", batch_hash_by_arm)
        if step in TRACE_STEPS:
            sampling_logits = {
                arm: run_forked_sampling_probe(
                    model=runtimes[arm].model,
                    sampling_fn=runtimes[arm].sampling_fns["p5"]["fn"],
                    history=runtimes[arm].last_batch["seq"][:4],
                    probe_seed=SAMPLING_PROBE_SEED_BASE + step,
                    training_rng_state=runtimes[arm].rng_state,
                    include_cuda=True,
                )
                for arm in ARM_NAMES
            }
            snapshots = {
                arm: _runtime_snapshot(
                    runtimes[arm],
                    proposal_rows=latest_proposals[arm],
                    sampling_probe_logits=sampling_logits[arm],
                )
                for arm in ARM_NAMES
            }
            checkpoints.append(
                compare_checkpoint_snapshots(step=step, snapshots=snapshots)
            )

    report = build_trace_report(
        e0=e0_evidence,
        assets=asset_evidence,
        config_contract=config_contract,
        checkpoints=checkpoints,
        source_manifest=production_call_path_manifest(),
    )
    report["initialization"] = initialization_evidence
    return report


def write_trace_artifacts(
    output_dir: Path | str,
    report: Mapping[str, Any],
    *,
    allow_existing_empty: bool = False,
) -> Path:
    output_dir = Path(output_dir)
    if output_dir.exists():
        if not allow_existing_empty or any(output_dir.iterdir()):
            raise FileExistsError(f"isolated E01 output directory already exists: {output_dir}")
    else:
        output_dir.mkdir(parents=True)
    report_path = output_dir / "e01_gzero_trace.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    if report.get("status") == "pass" and report.get("first_divergence") is None:
        marker = {
            "schema_version": 1,
            "status": "pass",
            "dataset": DATASET_NAME,
            "random_seed": RANDOM_SEED,
            "trace_steps": list(TRACE_STEPS),
            "fp32_tolerance": FP32_TOLERANCE,
            "trace_report": report_path.name,
            "trace_report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        }
        (output_dir / "E01_PASS.json").write_text(
            json.dumps(marker, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return report_path


def production_call_path_manifest() -> dict[str, Any]:
    manifest = {
        "launcher": "scripts/run_text_side_main_table_tmux.sh -> single_train.py",
        "initialization_rng_loader_selector": "single_train.py:142-225",
        "proposal_builder": "model/text_side.py:502",
        "proposal_graph": "graph_lib.py:1312",
        "training_loss_dispatch": "losses.py:11",
        "sampling_graph_dispatch": "sampling.py:58",
        "scope_decision": PROTOCOL_SCOPE_DECISION,
    }
    source_paths = (
        REPO_ROOT / "single_train.py",
        REPO_ROOT / "model" / "text_side.py",
        REPO_ROOT / "graph_lib.py",
        REPO_ROOT / "losses.py",
        REPO_ROOT / "sampling.py",
        Path(__file__).resolve(),
    )
    manifest["source_sha256"] = {
        path.relative_to(REPO_ROOT).as_posix(): sha256_file(path)
        for path in source_paths
    }
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--text-utility-report-path", type=Path, required=True)
    parser.add_argument(
        "--e0-amendment-path",
        type=Path,
        default=DEFAULT_E0_AMENDMENT_PATH,
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument(
        "--execute-production-trace",
        action="store_true",
        help="Required acknowledgement that the 1000-step production trace may execute.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if not args.execute_production_trace:
        raise SystemExit(
            "refusing to execute E01 without --execute-production-trace; E0 remains a hard prerequisite"
        )
    try:
        report = run_production_trace(args)
    except Exception as exc:
        failure_report = build_execution_failure_report(exc)
        write_trace_artifacts(args.output_dir, failure_report, allow_existing_empty=True)
        print(json.dumps(failure_report, indent=2, sort_keys=True))
        raise SystemExit(3) from exc

    report_path = write_trace_artifacts(args.output_dir, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "first_divergence": report["first_divergence"],
                "output_path": str(report_path),
                "pass_marker": str(Path(args.output_dir) / "E01_PASS.json")
                if report["status"] == "pass"
                else None,
            },
            indent=2,
            sort_keys=True,
        )
    )
    if report["status"] != "pass":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
