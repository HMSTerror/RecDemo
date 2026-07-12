"""Queue-safe, dated adapters for the RISK-04--RISK-08 evidence wave.

The functions in this module only create immutable manifests and validate
artifacts.  They never invoke a trainer, a queue controller, SSH, tmux, or a
GPU process.  A later controller invocation must consume the dated manifest
and the atomic markers produced here.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .bank_builder import CORRUPTION_SEED, build_corruption_bank
from .common import atomic_write_json, sha256_file, stable_sha256, write_bytes_exclusive
from .pilot_adapters import build_pilot_manifest
from .preregistration import build_preregistration
from scripts.aaai27_queue.models import QueueManifest
from scripts.aaai27_queue.validation import ManifestError, validate_manifest


DATASETS = ("Beauty", "Steam")
RISK04_LEVELS = (0, 20, 40, 60, 80, 100)
PILOT_LEVELS = (0, 60, 100)
TRACE_STEPS = (0, 1, 100, 1000)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
DATED_RE = re.compile(r"20\d{2}-\d{2}-\d{2}")


class QueueSafetyError(ValueError):
    """Raised when a dated queue artifact cannot be trusted."""


def _load_object(path: Path, label: str) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise QueueSafetyError(f"{label} must contain a JSON object: {path}")
    return value


def _dated_absent(root: Path, label: str) -> Path:
    root = Path(root)
    if not any(DATED_RE.search(part) for part in root.parts):
        raise QueueSafetyError(f"{label} must be a dated path containing YYYY-MM-DD: {root}")
    if root.exists():
        raise FileExistsError(f"immutable {label} already exists: {root}")
    return root


def _require_revision(value: Any, label: str) -> str:
    value = str(value)
    if REVISION_RE.fullmatch(value) is None:
        raise QueueSafetyError(f"{label} must be a 40-character lowercase revision")
    return value


def _require_hash(value: Any, label: str) -> str:
    value = str(value)
    if SHA256_RE.fullmatch(value) is None:
        raise QueueSafetyError(f"{label} must be a lowercase SHA-256")
    return value


def _payload_hash(payload: Mapping[str, Any], field: str = "artifact_sha256") -> str:
    copy = dict(payload)
    copy.pop(field, None)
    return stable_sha256(copy)


def _reject_non_train_path(path: Path, label: str) -> None:
    lowered = str(path).casefold().replace("\\", "/")
    components = re.split(r"[/_.-]+", lowered)
    if any(component in {"val", "valid", "validation", "test", "testing"} for component in components):
        raise QueueSafetyError(f"{label} must be train-only: {path}")


def _finite_float(value: Any, label: str) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise QueueSafetyError(f"{label} must be numeric") from exc
    if not math.isfinite(value):
        raise QueueSafetyError(f"{label} must be finite")
    return value


def _risk04_dataset_config(config: Mapping[str, Any], dataset: str) -> Mapping[str, Any]:
    datasets = config.get("datasets")
    if not isinstance(datasets, Mapping) or set(datasets) != set(DATASETS):
        raise QueueSafetyError("RISK-04 requires exactly Beauty and Steam dataset configurations")
    row = datasets.get(dataset)
    if not isinstance(row, Mapping):
        raise QueueSafetyError(f"RISK-04 dataset configuration is not an object: {dataset}")
    return row


def _get_path(row: Mapping[str, Any], *keys: str) -> Path:
    for key in keys:
        if row.get(key):
            return Path(str(row[key]))
    raise QueueSafetyError(f"missing required path; expected one of {keys}")


def _severe_gate(config: Mapping[str, Any]) -> dict[str, Any]:
    raw = config.get("severe_gate", {})
    if raw is None:
        raw = {}
    if not isinstance(raw, Mapping):
        raise QueueSafetyError("severe_gate must be an object")
    clean_raw = raw.get("clean_mean_gate", raw.get("mean_gate_clean"))
    severe_raw = raw.get("steam_c60_mean_gate", raw.get("c60_mean_gate", raw.get("mean_gate_c60")))
    result: dict[str, Any] = {
        "dataset": "Steam",
        "corruption_level": 60,
        "threshold_relative_clean_drop": 0.20,
        "clean_mean_gate": None,
        "steam_c60_mean_gate": None,
        "relative_clean_drop": None,
        "status": "pending",
        "training_start_authorized": False,
        "adaptive_backoff": False,
    }
    if clean_raw is None or severe_raw is None:
        return result
    clean = _finite_float(clean_raw, "severe_gate.clean_mean_gate")
    severe = _finite_float(severe_raw, "severe_gate.steam_c60_mean_gate")
    if clean <= 0:
        raise QueueSafetyError("severe_gate.clean_mean_gate must be positive")
    drop = (clean - severe) / abs(clean)
    result.update(
        {
            "clean_mean_gate": clean,
            "steam_c60_mean_gate": severe,
            "relative_clean_drop": float(drop),
            "status": "pass" if drop >= 0.20 else "stop",
            "training_start_authorized": bool(drop >= 0.20),
        }
    )
    return result


def build_risk04_bundle(
    config: Mapping[str, Any],
    output_root: Path,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build all twelve immutable corruption banks under one dated root."""

    output_root = _dated_absent(Path(output_root), "RISK-04 output root")
    if int(config.get("corruption_seed", CORRUPTION_SEED)) != CORRUPTION_SEED:
        raise QueueSafetyError("RISK-04 corruption seed is frozen at 100")
    code_revision = _require_revision(config.get("code_revision"), "RISK-04 code_revision")
    strata_count = int(config.get("strata_count", 10))
    if strata_count <= 0:
        raise QueueSafetyError("RISK-04 strata_count must be positive")

    prepared: dict[str, dict[str, Any]] = {}
    for dataset in DATASETS:
        row = _risk04_dataset_config(config, dataset)
        clean_path = _get_path(row, "clean_embeddings_path", "clean_embeddings", "embedding_path")
        train_path = _get_path(row, "train_transitions_path", "train_transitions", "train_path")
        _reject_non_train_path(train_path, f"{dataset} train transition path")
        if not clean_path.is_file() or not train_path.is_file():
            raise FileNotFoundError(f"RISK-04 input does not exist for {dataset}: {clean_path}, {train_path}")
        split_hash = _require_hash(row.get("split_sha256", sha256_file(train_path)), f"{dataset} split_sha256")
        expected_item_ids = row.get("expected_item_ids")
        if isinstance(expected_item_ids, (str, Path)):
            expected_item_ids = json.loads(Path(expected_item_ids).read_text(encoding="utf-8"))
        prepared[dataset] = {
            "clean_path": clean_path,
            "train_path": train_path,
            "expected_item_ids": expected_item_ids,
            "split_sha256": split_hash,
            "source_hashes": {
                "clean_embeddings_sha256": sha256_file(clean_path),
                "train_transitions_sha256": sha256_file(train_path),
                "split_sha256": split_hash,
            },
        }

    generated_at = generated_at or datetime.now().astimezone().isoformat(timespec="seconds")
    gate = _severe_gate(config)
    output_root.mkdir(parents=True)
    datasets_report: dict[str, Any] = {}
    for dataset in DATASETS:
        row = prepared[dataset]
        banks: dict[str, Any] = {}
        for level in RISK04_LEVELS:
            bank_dir = output_root / "banks" / dataset / f"level-{level:03d}"
            bank = build_corruption_bank(
                row["clean_path"],
                row["train_path"],
                output_dir=bank_dir,
                dataset=dataset,
                corruption_level=level,
                corruption_seed=CORRUPTION_SEED,
                strata_count=strata_count,
                expected_item_ids=row["expected_item_ids"],
            )
            banks[str(level)] = {
                "level": level,
                "relative_dir": bank_dir.relative_to(output_root).as_posix(),
                "embedding_path": bank_dir.joinpath("embeddings.pt").relative_to(output_root).as_posix(),
                "bank_manifest_path": bank_dir.joinpath("bank_manifest.json").relative_to(output_root).as_posix(),
                "bank_sha256": bank["bank_sha256"],
                "embedding_sha256": bank["embedding_artifacts"]["torch_sha256"],
                "selected_count": bank["permutation"]["selected_count"],
                "row_norm_max_abs_diff": bank["row_norm_max_abs_diff"],
                "strata_count": bank["strata_count"],
            }
        datasets_report[dataset] = {
            "split_sha256": row["split_sha256"],
            "source_hashes": row["source_hashes"],
            "clean_embeddings_path": str(row["clean_path"]),
            "train_transitions_path": str(row["train_path"]),
            "banks": banks,
        }

    report: dict[str, Any] = {
        "schema_version": 1,
        "risk_id": "RISK-04",
        "report_name": "AAAI-RISK-04 dated popularity-stratified corruption bank bundle",
        "generated_at": generated_at,
        "code_revision": code_revision,
        "protocol": {
            "datasets": list(DATASETS),
            "corruption_levels": list(RISK04_LEVELS),
            "corruption_seed": CORRUPTION_SEED,
            "strata_count": strata_count,
            "split": "train-only",
            "algorithm": "popularity-stratified item-embedding permutation with row-norm preservation",
            "pseudo_item_policy": "real-item rows only; padding and pseudo-item rows are excluded",
            "no_training_started": True,
        },
        "severe_gate": gate,
        "datasets": datasets_report,
        "training_start_authorized": bool(gate["training_start_authorized"]),
        "adaptive_backoff": False,
    }
    report["artifact_sha256"] = _payload_hash(report)
    atomic_write_json(output_root / "risk04_bundle.json", report)
    assets_marker = {
        "schema_version": 1,
        "risk_id": "RISK-04",
        "outcome": "assets_ready",
        "no_training_started": True,
        "severe_gate": gate,
        "risk04_bundle_sha256": sha256_file(output_root / "risk04_bundle.json"),
    }
    assets_marker["artifact_sha256"] = _payload_hash(assets_marker)
    atomic_write_json(output_root / "RISK-04_ASSETS_READY.json", assets_marker)
    terminal_name = "RISK-04_PASS.json" if gate["status"] == "pass" else "RISK-04_STOP.json" if gate["status"] == "stop" else "RISK-04_PENDING.json"
    terminal_marker = {
        "schema_version": 1,
        "risk_id": "RISK-04",
        "outcome": "pass" if gate["status"] == "pass" else "stop" if gate["status"] == "stop" else "pending",
        "training_start_authorized": bool(gate["training_start_authorized"]),
        "risk04_bundle_sha256": sha256_file(output_root / "risk04_bundle.json"),
        "severe_gate": gate,
    }
    terminal_marker["artifact_sha256"] = _payload_hash(terminal_marker)
    atomic_write_json(output_root / terminal_name, terminal_marker)

    lines = []
    for dataset in DATASETS:
        for level in RISK04_LEVELS:
            bank = datasets_report[dataset]["banks"][str(level)]
            lines.append(f"{bank['bank_sha256']}  {bank['relative_dir']}/bank_manifest.json")
            lines.append(f"{bank['embedding_sha256']}  {bank['embedding_path']}")
    write_bytes_exclusive(output_root / "SHA256SUMS", ("\n".join(lines) + "\n").encode("ascii"))
    return report


def _validate_bank_hash(root: Path, row: Mapping[str, Any], dataset: str, level: int) -> None:
    manifest_path = root / str(row["bank_manifest_path"])
    if not manifest_path.is_file():
        raise QueueSafetyError(f"missing RISK-04 bank manifest: {manifest_path}")
    manifest = _load_object(manifest_path, "bank manifest")
    if manifest.get("dataset") != dataset or int(manifest.get("corruption_level", -1)) != level:
        raise QueueSafetyError(f"bank identity mismatch: {manifest_path}")
    if int(manifest.get("corruption_seed", -1)) != CORRUPTION_SEED:
        raise QueueSafetyError(f"bank seed mismatch: {manifest_path}")
    numpy_path = manifest_path.parent / str(manifest["embedding_artifacts"]["numpy_filename"])
    torch_path = manifest_path.parent / str(manifest["embedding_artifacts"]["torch_filename"])
    item_ids_path = manifest_path.parent / "item_ids.json"
    if sha256_file(numpy_path) != manifest["embedding_artifacts"]["numpy_sha256"]:
        raise QueueSafetyError(f"numpy bank hash mismatch: {numpy_path}")
    if sha256_file(torch_path) != manifest["embedding_artifacts"]["torch_sha256"]:
        raise QueueSafetyError(f"torch bank hash mismatch: {torch_path}")
    item_ids = json.loads(item_ids_path.read_text(encoding="utf-8"))
    if stable_sha256(item_ids) != manifest.get("item_id_mapping", {}).get("sha256"):
        raise QueueSafetyError(f"item ID mapping hash mismatch: {item_ids_path}")
    expected_bank = stable_sha256(
        {
            "manifest": {key: value for key, value in manifest.items() if key != "bank_sha256"},
            "numpy_sha256": sha256_file(numpy_path),
            "torch_sha256": sha256_file(torch_path),
            "item_ids_sha256": sha256_file(item_ids_path),
        }
    )
    if expected_bank != manifest.get("bank_sha256") or expected_bank != row.get("bank_sha256"):
        raise QueueSafetyError(f"bank_sha256 mismatch: {manifest_path}")


def validate_risk04_bundle(bundle_root: Path, *, require_severe_gate: bool = True) -> dict[str, Any]:
    root = Path(bundle_root)
    report_path = root / "risk04_bundle.json"
    if not report_path.is_file():
        raise QueueSafetyError(f"missing RISK-04 bundle report: {report_path}")
    report = _load_object(report_path, "RISK-04 report")
    if report.get("risk_id") != "RISK-04" or report.get("artifact_sha256") != _payload_hash(report):
        raise QueueSafetyError("RISK-04 report hash or identity mismatch")
    if report.get("protocol", {}).get("corruption_seed") != CORRUPTION_SEED:
        raise QueueSafetyError("RISK-04 report is not seed 100")
    if report.get("protocol", {}).get("corruption_levels") != list(RISK04_LEVELS):
        raise QueueSafetyError("RISK-04 report does not contain all six frozen levels")
    bank_hashes: dict[str, dict[str, str]] = {}
    for dataset in DATASETS:
        dataset_row = report.get("datasets", {}).get(dataset)
        if not isinstance(dataset_row, Mapping):
            raise QueueSafetyError(f"RISK-04 report lacks {dataset}")
        clean_source = Path(str(dataset_row["clean_embeddings_path"]))
        train_source = Path(str(dataset_row["train_transitions_path"]))
        _reject_non_train_path(train_source, f"{dataset} train transition path")
        if not clean_source.is_file() or not train_source.is_file():
            raise QueueSafetyError(f"RISK-04 source input is missing for {dataset}")
        source_hashes = dataset_row.get("source_hashes", {})
        if not isinstance(source_hashes, Mapping):
            raise QueueSafetyError(f"RISK-04 source hashes are missing for {dataset}")
        if sha256_file(clean_source) != source_hashes.get("clean_embeddings_sha256") or sha256_file(train_source) != source_hashes.get("train_transitions_sha256"):
            raise QueueSafetyError(f"RISK-04 source input hash mismatch for {dataset}")
        for level in RISK04_LEVELS:
            row = dataset_row.get("banks", {}).get(str(level))
            if not isinstance(row, Mapping):
                raise QueueSafetyError(f"RISK-04 report lacks {dataset} level {level}")
            _validate_bank_hash(root, row, dataset, level)
        bank_hashes[dataset] = {str(level): str(dataset_row["banks"][str(level)]["bank_sha256"]) for level in RISK04_LEVELS}
    gate = report.get("severe_gate")
    if not isinstance(gate, Mapping):
        raise QueueSafetyError("RISK-04 report lacks severe gate")
    if require_severe_gate and gate.get("status") != "pass":
        raise QueueSafetyError(f"Steam severe corruption gate is not passed: {gate.get('status')}")
    return {
        "status": "pass",
        "risk04_bundle_sha256": sha256_file(report_path),
        "bank_hashes": bank_hashes,
        "severe_gate": dict(gate),
        "training_start_authorized": bool(gate.get("training_start_authorized", False)),
    }


def _validate_e1_marker(path: Path) -> dict[str, Any]:
    path = Path(path)
    if path.name not in {"RISK-02_PASS.json", "RISK-02_FAIL.json"}:
        raise QueueSafetyError("E1 marker must be named RISK-02_PASS.json or RISK-02_FAIL.json")
    siblings = [path.parent / "RISK-02_PASS.json", path.parent / "RISK-02_FAIL.json"]
    if all(candidate.exists() for candidate in siblings):
        raise QueueSafetyError("ambiguous E1 markers: both pass and fail exist")
    marker = _load_object(path, "E1 marker")
    if marker.get("risk_id") != "RISK-02" or marker.get("outcome") not in {"pass", "fail"}:
        raise QueueSafetyError("E1 marker is not a terminal pass/fail marker")
    if int(marker.get("random_seed", -1)) != 100 or marker.get("trace_steps") != list(TRACE_STEPS):
        raise QueueSafetyError("E1 marker does not bind seed 100 and trace steps 0,1,100,1000")
    _require_revision(marker.get("source_revision"), "E1 source_revision")
    if marker["outcome"] == "pass" and marker.get("first_divergence") not in (None, {}):
        raise QueueSafetyError("E1 pass marker contains a first divergence")
    return marker


def build_risk05_bundle(
    risk04_root: Path,
    preflight_report_path: Path,
    e1_marker_path: Path,
    output_root: Path,
    *,
    generated_at: str | None = None,
    code_revision: str | None = None,
) -> dict[str, Any]:
    """Freeze RISK-05 only after dated RISK-04 and terminal E1 evidence exist."""

    risk04_root = Path(risk04_root)
    risk04 = validate_risk04_bundle(risk04_root, require_severe_gate=True)
    preflight_report_path = Path(preflight_report_path)
    e1_marker_path = Path(e1_marker_path)
    if not preflight_report_path.is_file():
        raise FileNotFoundError(preflight_report_path)
    preflight = _load_object(preflight_report_path, "RISK-04 preflight report")
    if preflight.get("protocol", {}).get("split") != "train-only":
        raise QueueSafetyError("RISK-05 accepts only a train-only preflight report")
    _reject_validation_test_keys(preflight)
    if set(preflight.get("datasets", {})) != set(DATASETS):
        raise QueueSafetyError("RISK-05 preflight must contain Beauty and Steam")
    for dataset in DATASETS:
        preflight_row = preflight["datasets"][dataset]
        risk04_hashes = risk04["bank_hashes"][dataset]
        preflight_sources = preflight_row.get("source_hashes", {}) if isinstance(preflight_row, Mapping) else {}
        preflight_banks = preflight_sources.get("banks") if isinstance(preflight_sources, Mapping) else None
        if not isinstance(preflight_banks, Mapping):
            raise QueueSafetyError(f"RISK-05 preflight lacks bank hashes for {dataset}")
        if {str(level): str(preflight_banks.get(str(level))) for level in RISK04_LEVELS} != risk04_hashes:
            raise QueueSafetyError(f"RISK-05 preflight bank hashes do not match RISK-04 for {dataset}")
    e1 = _validate_e1_marker(e1_marker_path)
    output_root = _dated_absent(Path(output_root), "RISK-05 output root")
    generated_at = generated_at or datetime.now().astimezone().isoformat(timespec="seconds")
    revision = _require_revision(code_revision or e1["source_revision"], "RISK-05 code_revision")
    output_root.mkdir(parents=True)
    (output_root / "markers").mkdir()
    (output_root / "manifests").mkdir()
    bindings = {
        "risk04_bundle_sha256": risk04["risk04_bundle_sha256"],
        "preflight_report_sha256": sha256_file(preflight_report_path),
        "e1_marker_sha256": sha256_file(e1_marker_path),
        "e1_outcome": e1["outcome"],
        "e1_source_revision": e1["source_revision"],
        "no_test_metric": True,
        "no_rescue": True,
        "single_seed_observation": True,
    }
    result = build_preregistration(
        preflight,
        output_root / "protocol",
        generated_at=generated_at,
        code_revision=revision,
        bindings=bindings,
    )
    atomic_write_json(output_root / "protocol" / "risk05_preregistration.json", result)
    atomic_write_json(output_root / "protocol" / "risk04_bundle.json", _load_object(risk04_root / "risk04_bundle.json", "RISK-04 report"))
    atomic_write_json(output_root / "markers" / e1_marker_path.name, e1)
    risk05_marker_name = "RISK-05_PASS.json" if result["pilot_authorized"] else "RISK-05_STOP.json"
    risk05_marker = _load_object(output_root / "protocol" / risk05_marker_name, "RISK-05 marker")
    risk05_marker.update(bindings)
    risk05_marker["preregistration_sha256"] = stable_sha256(result)
    risk05_marker["artifact_sha256"] = _payload_hash(risk05_marker)
    atomic_write_json(output_root / "markers" / risk05_marker_name, risk05_marker)
    source_manifest = {
        "schema_version": 1,
        "risk04_bundle_sha256": risk04["risk04_bundle_sha256"],
        "preflight_report_sha256": sha256_file(preflight_report_path),
        "e1_marker_sha256": sha256_file(e1_marker_path),
        "risk05_preregistration_sha256": stable_sha256(result),
    }
    atomic_write_json(output_root / "manifests" / "source_hashes.json", source_manifest)
    metadata = {
        "schema_version": 1,
        "risk_id": "RISK-05",
        "generated_at": generated_at,
        "risk04_bundle_root": str(risk04_root),
        "risk04_bundle_sha256": risk04["risk04_bundle_sha256"],
        "risk05_preregistration_sha256": stable_sha256(result),
        "preregistration_sha256": stable_sha256(result),
        "risk05_marker": f"markers/{risk05_marker_name}",
        "e1_marker_sha256": sha256_file(e1_marker_path),
        "e1_outcome": e1["outcome"],
        "pilot_authorized": bool(result["pilot_authorized"]),
        "no_training_started": True,
    }
    metadata["artifact_sha256"] = _payload_hash(metadata)
    atomic_write_json(output_root / "risk05_bundle.json", metadata)
    return metadata


def _reject_validation_test_keys(value: Any, path: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).casefold() in {
                "validation_metric",
                "test_metric",
                "validation_result",
                "test_result",
                "validation_ndcg10",
                "test_ndcg10",
            }:
                raise QueueSafetyError(f"validation/test metric entered frozen protocol: {path}.{key}")
            _reject_validation_test_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_validation_test_keys(child, f"{path}[{index}]")


def _posix_path(value: Any, label: str) -> str:
    value = str(value)
    if not value.startswith("/"):
        raise QueueSafetyError(f"{label} must be an absolute POSIX path")
    return value.rstrip("/") or "/"


def build_risk0607_manifest(
    risk05_root: Path,
    e1_marker_path: Path,
    output_root: Path,
    protocol_template: Mapping[str, Any],
) -> dict[str, Any]:
    """Create and validate the dated 14-task/8-task seed-100 pilot manifest."""

    risk05_root = Path(risk05_root)
    metadata = _load_object(risk05_root / "risk05_bundle.json", "RISK-05 bundle")
    if metadata.get("artifact_sha256") != _payload_hash(metadata) or not metadata.get("pilot_authorized"):
        raise QueueSafetyError("RISK-05 is not an authorized pilot freeze")
    e1 = _validate_e1_marker(Path(e1_marker_path))
    if sha256_file(Path(e1_marker_path)) != metadata.get("e1_marker_sha256"):
        raise QueueSafetyError("E1 marker does not match RISK-05 freeze")
    risk05_marker_path = risk05_root / str(metadata["risk05_marker"])
    risk05_marker = _load_object(risk05_marker_path, "RISK-05 marker")
    if risk05_marker.get("outcome") != "pass":
        raise QueueSafetyError("RISK-05 marker is not PASS")
    risk04_report = _load_object(risk05_root / "protocol" / "risk04_bundle.json", "bound RISK-04 report")
    if risk04_report.get("artifact_sha256") is None:
        raise QueueSafetyError("bound RISK-04 report lacks an artifact hash")
    output_root = _dated_absent(Path(output_root), "RISK-06/RISK-07 queue root")
    queue_root_posix = _posix_path(protocol_template.get("queue_root_posix"), "queue_root_posix")
    run_root_posix = _posix_path(
        protocol_template.get("run_root_posix", queue_root_posix),
        "run_root_posix",
    )
    source_root_posix = _posix_path(protocol_template.get("source_root_posix"), "source_root_posix")
    gpu_ids = protocol_template.get("gpu_ids")
    if gpu_ids != [0, 1]:
        raise QueueSafetyError(
            "RISK-06/RISK-07 pilot gpu_ids must explicitly equal [0, 1]"
        )
    if run_root_posix != queue_root_posix:
        raise QueueSafetyError(
            "run_root_posix is the manifest containment root and must equal queue_root_posix"
        )
    risk04_root_posix = _posix_path(
        protocol_template.get("risk04_root_posix"),
        "risk04_root_posix",
    )
    bound_risk04_root = Path(str(metadata["risk04_bundle_root"])).resolve()
    bound_risk04_root_posix = bound_risk04_root.as_posix()
    if (
        bound_risk04_root_posix.startswith("/")
        and bound_risk04_root_posix != risk04_root_posix
    ):
        raise QueueSafetyError(
            "risk04_root_posix does not match the RISK-05-bound RISK-04 root"
        )
    datasets_template = protocol_template.get("datasets")
    if not isinstance(datasets_template, Mapping) or set(datasets_template) != set(DATASETS):
        raise QueueSafetyError("RISK-06/RISK-07 requires exactly Beauty and Steam dataset settings")
    code_revision = _require_revision(protocol_template.get("code_revision"), "pilot code_revision")
    source_manifest_sha256 = _require_hash(protocol_template.get("source_manifest_sha256"), "source_manifest_sha256")
    ledger_sha256 = _require_hash(protocol_template.get("ledger_sha256"), "ledger_sha256")
    config_sha256 = _require_hash(protocol_template.get("config_sha256"), "config_sha256")
    risk05_prereg = _load_object(
        risk05_root / "protocol" / "risk05_preregistration.json",
        "RISK-05 preregistration",
    )
    risk05_preregistration_sha256 = stable_sha256(risk05_prereg)
    if risk05_preregistration_sha256 != metadata.get(
        "risk05_preregistration_sha256"
    ):
        raise QueueSafetyError("RISK-05 preregistration hash disagrees with bundle metadata")
    phi_r = risk05_prereg.get("phi_R")
    if not isinstance(phi_r, Mapping) or set(phi_r) != set(DATASETS):
        raise QueueSafetyError("RISK-05 preregistration lacks the two-domain phi_R map")

    protocol: dict[str, Any] = {
        "queue_id": str(protocol_template["queue_id"]),
        "created_at": str(protocol_template["created_at"]),
        "run_root": run_root_posix,
        "source_root": source_root_posix,
        "source_manifest_sha256": source_manifest_sha256,
        "ledger_path": _posix_path(protocol_template.get("ledger_path_posix"), "ledger_path_posix"),
        "ledger_sha256": ledger_sha256,
        "gpu_ids": list(gpu_ids),
        "code_revision": code_revision,
        "config_sha256": config_sha256,
        "python_bin": str(protocol_template["python_bin"]),
        "single_train": str(protocol_template["single_train"]),
        "risk04_root": risk04_root_posix,
        "risk05_preregistration_sha256": risk05_preregistration_sha256,
        "training_overrides": [str(item) for item in protocol_template.get("training_overrides", [])],
        "estimated_gpu_hours": dict(protocol_template.get("estimated_gpu_hours", {"low": 0.5, "high": 1.0, "output_gib": 0.2})),
        "datasets": {},
    }
    for dataset in DATASETS:
        template = datasets_template[dataset]
        if not isinstance(template, Mapping):
            raise QueueSafetyError(f"pilot dataset template is not an object: {dataset}")
        risk04_dataset = risk04_report["datasets"][dataset]
        banks: dict[str, Any] = {}
        for level in PILOT_LEVELS:
            source_bank = risk04_dataset["banks"][str(level)]
            relative_embedding = PurePosixPath(str(source_bank["embedding_path"]))
            if relative_embedding.is_absolute() or ".." in relative_embedding.parts:
                raise QueueSafetyError(
                    f"RISK-04 embedding path is not a safe relative path: {relative_embedding}"
                )
            embedding_sha256 = _require_hash(
                source_bank.get("embedding_sha256"),
                f"{dataset} level {level} embedding_sha256",
            )
            bound_embedding = bound_risk04_root.joinpath(*relative_embedding.parts)
            if not bound_embedding.is_file():
                raise QueueSafetyError(
                    f"bound RISK-04 embedding is missing: {bound_embedding}"
                )
            if sha256_file(bound_embedding) != embedding_sha256:
                raise QueueSafetyError(
                    f"bound RISK-04 embedding hash mismatch: {bound_embedding}"
                )
            banks[str(level)] = {
                "embedding_path": (
                    f"{risk04_root_posix}/{relative_embedding.as_posix()}"
                ),
                "embedding_sha256": embedding_sha256,
                "bank_sha256": str(source_bank["bank_sha256"]),
                "phi_R": float(phi_r[dataset][str(level)]),
            }
        protocol["datasets"][dataset] = {
            "dataset_dir": str(template["dataset_dir"]),
            "split_sha256": str(risk04_dataset["split_sha256"]),
            "text_bank_path": str(template["text_bank_path"]),
            "null_curve_path": str(template["null_curve_path"]),
            "null_curve_sha256": _require_hash(
                template.get("null_curve_sha256"),
                f"{dataset} null_curve_sha256",
            ),
            "phi_R": {
                str(level): float(phi_r[dataset][str(level)])
                for level in PILOT_LEVELS
            },
            "config_sha256": _require_hash(template.get("config_sha256", config_sha256), f"{dataset} config_sha256"),
            "banks": banks,
        }
    manifest = build_pilot_manifest(protocol)
    decoded = QueueManifest.from_dict(manifest)
    try:
        validate_manifest(decoded)
    except ManifestError as exc:
        raise QueueSafetyError(f"generated RISK-06/RISK-07 queue failed validation: {exc}") from exc
    task_ids = [task["task_id"] for task in manifest["tasks"]]
    if len(task_ids) != len(set(task_ids)) or len(task_ids) != 22:
        raise QueueSafetyError("pilot manifest must contain exactly 22 unique tasks")
    run_dirs = [str(task["run_dir"]) for task in manifest["tasks"]]
    if len(run_dirs) != len(set(run_dirs)):
        raise QueueSafetyError("pilot manifest contains duplicate run directories")
    if any(task["seed"] != 100 or task["max_attempts"] != 1 or task["failure_policy"] != "fail_closed" for task in manifest["tasks"]):
        raise QueueSafetyError("pilot manifest violates seed-100/attempt-one/fail-closed contract")
    if any("diffurec" in str(task.get("model", "")).casefold() or "bert4rec" in str(task.get("model", "")).casefold() for task in manifest["tasks"]):
        raise QueueSafetyError("forbidden baseline identity entered pilot manifest")
    if any(any(token in {"rm", "rmdir", "del", "--force", "--no-skip-existing"} for token in task["argv"]) for task in manifest["tasks"]):
        raise QueueSafetyError("destructive argv entered pilot manifest")
    output_root.mkdir(parents=True)
    for relative in ("queue", "protocol", "markers", "manifests"):
        (output_root / relative).mkdir()
    atomic_write_json(output_root / "protocol" / "risk04_manifest.json", risk04_report)
    atomic_write_json(output_root / "protocol" / "risk05_preregistration.json", risk05_prereg)
    protocol["risk04_bundle_sha256"] = metadata["risk04_bundle_sha256"]
    protocol["risk05_preregistration_sha256"] = metadata["risk05_preregistration_sha256"]
    protocol["e1_marker_sha256"] = sha256_file(Path(e1_marker_path))
    protocol["e1_outcome"] = e1["outcome"]
    protocol["no_training_started"] = True
    atomic_write_json(output_root / "protocol" / "risk0607_protocol.json", protocol)
    atomic_write_json(output_root / "markers" / Path(e1_marker_path).name, e1)
    atomic_write_json(output_root / "markers" / risk05_marker_path.name, risk05_marker)
    source_hashes = {
        "risk04_bundle_sha256": metadata["risk04_bundle_sha256"],
        "risk05_preregistration_sha256": metadata["risk05_preregistration_sha256"],
        "e1_marker_sha256": sha256_file(Path(e1_marker_path)),
        "code_revision": code_revision,
        "ledger_sha256": ledger_sha256,
        "source_manifest_sha256": source_manifest_sha256,
        "bank_hashes": {
            dataset: {str(level): str(risk04_report["datasets"][dataset]["banks"][str(level)]["bank_sha256"]) for level in RISK04_LEVELS}
            for dataset in DATASETS
        },
    }
    atomic_write_json(output_root / "manifests" / "input_hashes.json", source_hashes)
    atomic_write_json(output_root / "queue" / "queue_seed100.json", manifest)
    queue_meta = {
        "schema_version": 1,
        "queue_id": manifest["queue_id"],
        "queue_manifest_sha256": sha256_file(output_root / "queue" / "queue_seed100.json"),
        "task_count": len(manifest["tasks"]),
        "e1_outcome": e1["outcome"],
        "no_training_started": True,
    }
    queue_meta["artifact_sha256"] = _payload_hash(queue_meta)
    atomic_write_json(output_root / "queue" / "queue_manifest_meta.json", queue_meta)
    return manifest


def _resolve_below(root: Path, value: str | Path, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    resolved_root = root.resolve()
    resolved = path.resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise QueueSafetyError(f"{label} leaves dated queue root: {value}")
    return resolved


def _inside_path(path: Path, root: Path) -> bool:
    resolved = Path(path).resolve()
    resolved_root = Path(root).resolve()
    return resolved == resolved_root or resolved_root in resolved.parents


def _validate_artifact_manifest(root: Path, path: Path, task: Mapping[str, Any], queue_hash: str) -> str:
    task_run_dir = str(task.get("run_dir", ""))
    if "/runs/" not in task_run_dir:
        raise QueueSafetyError(f"pilot task has no dated run directory: {task.get('task_id')}")
    expected_run = root / "runs" / task_run_dir.split("/runs/", 1)[1]
    resolved_path = path.resolve()
    resolved_run = expected_run.resolve()
    if resolved_path != resolved_run and resolved_run not in resolved_path.parents:
        raise QueueSafetyError(f"pilot artifact is outside its task run directory: {path}")
    artifact = _load_object(path, "pilot artifact manifest")
    if artifact.get("task_id") != task["task_id"] or artifact.get("status") != "pass":
        raise QueueSafetyError(f"pilot artifact identity/status mismatch: {path}")
    if artifact.get("queue_manifest_sha256") != queue_hash:
        raise QueueSafetyError(f"pilot artifact queue hash mismatch: {path}")
    if artifact.get("artifact_sha256") != _payload_hash(artifact):
        raise QueueSafetyError(f"pilot artifact self hash mismatch: {path}")
    identity_fields = {
        "source_revision": "code_revision",
        "config_sha256": "config_sha256",
        "split_sha256": "split_sha256",
        "bank_sha256": "bank_sha256",
        "evaluator_version": "evaluator_version",
        "selector_version": "selector_version",
    }
    for artifact_field, task_field in identity_fields.items():
        if artifact.get(artifact_field) != task.get(task_field):
            label = "source revision" if artifact_field == "source_revision" else artifact_field
            raise QueueSafetyError(
                f"pilot artifact {label} mismatch: {path}"
            )
    success_artifacts = task.get("success_artifacts")
    if not isinstance(success_artifacts, (list, tuple)) or len(success_artifacts) != 2:
        raise QueueSafetyError(f"pilot task lacks summary/manifest artifact contract: {path}")
    expected_metrics_path = _resolve_below(
        root, str(success_artifacts[0]), "expected metrics path"
    )
    expected_manifest_path = _resolve_below(
        root, str(success_artifacts[1]), "expected artifact-manifest path"
    )
    if resolved_path != expected_manifest_path:
        raise QueueSafetyError(f"pilot artifact manifest path mismatch: {path}")
    provenance = artifact.get("metrics_provenance")
    if not isinstance(provenance, Mapping) or not provenance.get("path") or not provenance.get("sha256"):
        raise QueueSafetyError(f"pilot metrics lack artifact provenance: {path}")
    metrics_path = _resolve_below(root, str(provenance["path"]), "metrics provenance path")
    if metrics_path != expected_metrics_path or not _inside_path(metrics_path, resolved_run):
        raise QueueSafetyError(f"pilot metrics provenance path mismatch: {metrics_path}")
    if not metrics_path.is_file() or sha256_file(metrics_path) != str(provenance["sha256"]):
        raise QueueSafetyError(f"pilot metrics provenance hash mismatch: {metrics_path}")
    log_provenance = artifact.get("log_provenance")
    if not isinstance(log_provenance, Mapping):
        raise QueueSafetyError(f"pilot log provenance is missing: {path}")
    log_path = _resolve_below(
        root, str(log_provenance.get("path", "")), "log provenance path"
    )
    if log_path != resolved_run / "single_train.log" or not _inside_path(
        log_path, resolved_run
    ):
        raise QueueSafetyError(f"pilot log provenance path mismatch: {log_path}")
    expected_log_size = log_provenance.get("size_bytes")
    if (
        not log_path.is_file()
        or not isinstance(expected_log_size, int)
        or isinstance(expected_log_size, bool)
        or expected_log_size <= 0
        or log_path.stat().st_size != expected_log_size
        or sha256_file(log_path) != str(log_provenance.get("sha256", ""))
    ):
        raise QueueSafetyError(f"pilot log provenance hash/size mismatch: {log_path}")
    task_env = task.get("env")
    if not isinstance(task_env, Mapping):
        raise QueueSafetyError(f"pilot task environment binding is missing: {path}")
    null_reference = artifact.get("null_curve_reference")
    if not isinstance(null_reference, Mapping):
        raise QueueSafetyError(f"pilot null-curve provenance is missing: {path}")
    expected_policy = str(task_env.get("AAAI_NULL_CURVE_REFERENCE_POLICY", ""))
    if null_reference.get("policy") != expected_policy:
        raise QueueSafetyError(f"pilot null-curve policy mismatch: {path}")
    if expected_policy == "frozen_clean_calibration":
        expected_null_path = Path(str(task_env.get("AAAI_NULL_CURVE_PATH", ""))).resolve()
        expected_null_hash = str(task_env.get("AAAI_NULL_CURVE_SHA256", ""))
        if (
            Path(str(null_reference.get("path", ""))).resolve() != expected_null_path
            or null_reference.get("sha256") != expected_null_hash
            or not expected_null_path.is_file()
            or sha256_file(expected_null_path) != expected_null_hash
            or null_reference.get("source_bank_sha256")
            != task_env.get("AAAI_NULL_CURVE_SOURCE_BANK_SHA256")
            or null_reference.get("current_embedding_sha256")
            != task_env.get("AAAI_CURRENT_EMBEDDING_SHA256")
            or task_env.get("AAAI_CURRENT_EMBEDDING_SHA256")
            != task_env.get("AAAI_EMBEDDING_SHA256")
        ):
            raise QueueSafetyError(f"pilot null-curve provenance mismatch: {path}")
    elif expected_policy != "not_applicable":
        raise QueueSafetyError(f"pilot null-curve policy is unsupported: {path}")
    expected_gate = task_env.get("AAAI_GATE_DATASET_SCALE")
    observed_gate = artifact.get("gate_dataset_scale")
    if expected_gate is None:
        if observed_gate is not None:
            raise QueueSafetyError(f"pilot gate-scale provenance mismatch: {path}")
    else:
        try:
            gate_matches = float(expected_gate) == float(observed_gate)
        except (TypeError, ValueError):
            gate_matches = False
        if not gate_matches:
            raise QueueSafetyError(f"pilot gate-scale provenance mismatch: {path}")
    return sha256_file(path)


def run_risk08_decision(
    queue_root: Path,
    *,
    e1_marker_path: Path,
    risk05_root: Path,
    pilot_report_path: Path,
) -> dict[str, Any]:
    """Validate completed pilot artifacts and emit exactly one RISK-08 exit."""

    queue_root = Path(queue_root)
    exit_path = queue_root / "markers" / "RISK-08_EXIT.json"
    if exit_path.exists():
        raise FileExistsError(f"RISK-08 exit already exists: {exit_path}")
    queue_manifest_path = queue_root / "queue" / "queue_seed100.json"
    manifest_raw = _load_object(queue_manifest_path, "queue manifest")
    manifest = QueueManifest.from_dict(manifest_raw)
    try:
        validate_manifest(manifest)
    except ManifestError as exc:
        raise QueueSafetyError(f"queue manifest failed validation: {exc}") from exc
    queue_hash = sha256_file(queue_manifest_path)
    e1 = _validate_e1_marker(Path(e1_marker_path))
    risk05_metadata = _load_object(Path(risk05_root) / "risk05_bundle.json", "RISK-05 bundle")
    risk05_marker_path = Path(risk05_root) / str(risk05_metadata["risk05_marker"])
    risk05_marker = _load_object(risk05_marker_path, "RISK-05 marker")
    if risk05_marker.get("outcome") != "pass":
        raise QueueSafetyError("RISK-08 requires a RISK-05 PASS marker")
    prereg_path = Path(risk05_root) / "protocol" / "risk05_preregistration.json"
    prereg = _load_object(prereg_path, "RISK-05 preregistration")
    prereg_hash = stable_sha256(prereg)
    if risk05_marker.get("preregistration_sha256") != prereg_hash:
        raise QueueSafetyError("RISK-05 preregistration hash mismatch")
    if risk05_marker.get("e1_marker_sha256") != sha256_file(Path(e1_marker_path)):
        raise QueueSafetyError("RISK-05 and E1 marker hashes disagree")
    report = _load_object(Path(pilot_report_path), "pilot report")
    branch = str(report.get("branch", ""))
    expected_branch = "e1_pass" if e1["outcome"] == "pass" else "e1_fail_audit"
    if branch != expected_branch:
        raise QueueSafetyError("pilot branch does not match terminal E1 outcome")
    completed = report.get("completed_task_ids")
    if not isinstance(completed, list) or len(completed) != len(set(completed)):
        raise QueueSafetyError("pilot report completed_task_ids must be a unique list")
    expected_ids = {task.task_id for task in manifest.tasks if task.branch == branch and task.phase == "pilot"}
    if set(completed) != expected_ids:
        raise QueueSafetyError("pilot report does not contain the complete frozen branch matrix")
    if "metrics" in report:
        raise QueueSafetyError("pilot report may not contain hand-entered metrics")
    if report.get("decision_source") != "artifact_metrics":
        raise QueueSafetyError("pilot report must identify artifact_metrics as its decision source")
    phenomenon_pass = report.get("phenomenon_pass")
    if not isinstance(phenomenon_pass, bool):
        raise QueueSafetyError("pilot report requires a frozen boolean phenomenon_pass")
    checks = report.get("phenomenon_checks")
    if not isinstance(checks, Mapping) or set(checks.get("artifact_task_ids", [])) != expected_ids:
        raise QueueSafetyError("phenomenon checks are not bound to every pilot artifact")
    artifact_paths = report.get("artifact_manifests")
    if not isinstance(artifact_paths, Mapping) or set(artifact_paths) != expected_ids:
        raise QueueSafetyError("pilot report must bind one artifact manifest per completed task")
    tasks_by_id = {task.task_id: task.to_dict() for task in manifest.tasks}
    artifact_hashes: dict[str, str] = {}
    for task_id in sorted(expected_ids):
        artifact_path = _resolve_below(queue_root, str(artifact_paths[task_id]), f"artifact path for {task_id}")
        artifact_hashes[task_id] = _validate_artifact_manifest(queue_root, artifact_path, tasks_by_id[task_id], queue_hash)
    if e1["outcome"] == "pass" and phenomenon_pass:
        exit_value = "risk_gated_method"
    elif e1["outcome"] == "fail" and phenomenon_pass:
        exit_value = "audit_only"
    else:
        exit_value = "submission_stop"
    marker: dict[str, Any] = {
        "schema_version": 1,
        "risk_id": "RISK-08",
        "exit": exit_value,
        "e1_outcome": e1["outcome"],
        "pilot_branch": branch,
        "queue_manifest_sha256": queue_hash,
        "risk05_preregistration_sha256": prereg_hash,
        "risk05_marker_sha256": sha256_file(risk05_marker_path),
        "e1_marker_sha256": sha256_file(Path(e1_marker_path)),
        "pilot_report_sha256": sha256_file(Path(pilot_report_path)),
        "artifact_manifest_sha256": artifact_hashes,
        "phenomenon_pass": phenomenon_pass,
        "no_rescue": True,
        "single_seed_observation": True,
        "continuation_launch": False,
    }
    marker["artifact_sha256"] = _payload_hash(marker)
    atomic_write_json(exit_path, marker)
    return marker
