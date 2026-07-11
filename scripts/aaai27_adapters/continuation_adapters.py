"""Build-only, queue-safe method-pass continuation adapters."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .common import atomic_write_json, sha256_file, stable_sha256, write_bytes_exclusive
from scripts.aaai27_queue.models import QueueManifest
from scripts.aaai27_queue.validation import ManifestError, validate_manifest


FOUR_DOMAINS = ("Steam", "ML1M", "Beauty", "ATG")
CLASSIC_MODELS = ("SASRec", "Caser", "GRURec")
RISK13_ARMS = ("host", "risk_gated_full")
RISK14_ARMS = ("host", "text_anchor_only", "global_p", "dataset_gate_only", "full", "u_shuffle")
TRACE_STEPS = (0, 1, 100, 1000)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
DATED_RE = re.compile(r"20\d{2}-\d{2}-\d{2}")
FORBIDDEN_WORDS = {"diffurec", "bert4rec", "adaptive_backoff", "rescue", "test_metric", "validation_metric"}


class ContinuationSafetyError(ValueError):
    """Raised when a method-pass manifest cannot be trusted."""


def _load_json(path: Path, label: str) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        raise ContinuationSafetyError(f"missing {label}: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContinuationSafetyError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise ContinuationSafetyError(f"{label} must be a JSON object: {path}")
    return value


def _require_sha(value: Any, label: str) -> str:
    value = str(value)
    if SHA256_RE.fullmatch(value) is None:
        raise ContinuationSafetyError(f"{label} must be a lowercase SHA-256")
    return value


def _require_revision(value: Any, label: str) -> str:
    value = str(value)
    if REVISION_RE.fullmatch(value) is None:
        raise ContinuationSafetyError(f"{label} must be a 40-character lowercase revision")
    return value


def _finite(value: Any, label: str, minimum: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ContinuationSafetyError(f"{label} must be numeric") from exc
    if not math.isfinite(number) or number < minimum:
        raise ContinuationSafetyError(f"{label} must be finite and >= {minimum}")
    return number


def _payload_hash(value: Mapping[str, Any], field: str = "artifact_sha256") -> str:
    payload = dict(value)
    payload.pop(field, None)
    return stable_sha256(payload)


def _dated_absent(root: Path) -> Path:
    root = Path(root)
    if not any(DATED_RE.search(part) for part in root.parts):
        raise ContinuationSafetyError(f"output root must contain YYYY-MM-DD: {root}")
    if root.exists():
        raise FileExistsError(f"immutable continuation root already exists: {root}")
    return root


def _reject_forbidden(value: Any, path: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            lowered_key = str(key).casefold()
            if any(word in lowered_key for word in FORBIDDEN_WORDS):
                raise ContinuationSafetyError(f"forbidden field: {path}.{key}")
            _reject_forbidden(child, f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            _reject_forbidden(child, f"{path}[{index}]")
    elif isinstance(value, str) and any(word in value.casefold() for word in FORBIDDEN_WORDS):
        raise ContinuationSafetyError(f"forbidden value at {path}")


def _validate_e1(path: Path) -> tuple[dict[str, Any], str]:
    marker = _load_json(path, "E1 marker")
    if marker.get("risk_id") != "RISK-02" or marker.get("outcome") != "pass":
        raise ContinuationSafetyError("method-pass continuation requires an E1 PASS marker")
    if int(marker.get("random_seed", -1)) != 100 or marker.get("trace_steps") != list(TRACE_STEPS):
        raise ContinuationSafetyError("E1 PASS marker must bind seed 100 and trace steps 0,1,100,1000")
    _require_revision(marker.get("source_revision"), "E1 source_revision")
    if marker.get("first_divergence") not in (None, {}):
        raise ContinuationSafetyError("E1 PASS marker contains a first divergence")
    if "artifact_sha256" in marker and marker["artifact_sha256"] != _payload_hash(marker):
        raise ContinuationSafetyError("E1 marker self hash mismatch")
    return marker, sha256_file(Path(path))


def _validate_preregistration(path: Path, expected: str) -> tuple[dict[str, Any], str]:
    prereg = _load_json(path, "RISK-05 preregistration")
    actual = stable_sha256(prereg)
    file_hash = sha256_file(Path(path))
    accepted = {actual, file_hash, str(prereg.get("artifact_sha256", ""))}
    if expected not in accepted:
        raise ContinuationSafetyError("RISK-05 preregistration hash mismatch")
    return prereg, expected


def _validate_risk08(path: Path, *, e1_sha256: str, prereg_sha256: str) -> tuple[dict[str, Any], str]:
    marker = _load_json(path, "RISK-08 marker")
    if marker.get("risk_id") != "RISK-08" or marker.get("exit") != "risk_gated_method":
        raise ContinuationSafetyError("RISK-08 exit must be risk_gated_method")
    if marker.get("e1_outcome") != "pass":
        raise ContinuationSafetyError("RISK-08 method pass requires E1 outcome pass")
    if marker.get("e1_marker_sha256") != e1_sha256:
        raise ContinuationSafetyError("RISK-08 E1 marker hash mismatch")
    if marker.get("risk05_preregistration_sha256") != prereg_sha256:
        raise ContinuationSafetyError("RISK-08 RISK-05 preregistration hash mismatch")
    if "artifact_sha256" in marker and marker["artifact_sha256"] != _payload_hash(marker):
        raise ContinuationSafetyError("RISK-08 marker self hash mismatch")
    return marker, sha256_file(Path(path))


def _validate_protocol(protocol: Mapping[str, Any]) -> dict[str, Any]:
    required = (
        "queue_id", "created_at", "run_root", "source_root", "source_manifest_sha256",
        "ledger_path", "ledger_sha256", "code_revision", "python_bin", "continuation_entrypoint",
        "method_gate_script", "evaluator_version", "selector_version", "risk05_preregistration_sha256",
        "risk14_arms", "risk14_selection", "datasets", "estimates",
    )
    missing = [key for key in required if key not in protocol]
    if missing:
        raise ContinuationSafetyError(f"protocol missing fields: {','.join(missing)}")
    result = dict(protocol)
    _require_sha(result["source_manifest_sha256"], "source_manifest_sha256")
    _require_sha(result["ledger_sha256"], "ledger_sha256")
    _require_revision(result["code_revision"], "code_revision")
    _require_sha(result["risk05_preregistration_sha256"], "risk05_preregistration_sha256")
    run_root = str(result["run_root"]).rstrip("/")
    source_root = str(result["source_root"]).rstrip("/")
    if not run_root.startswith("/") or not source_root.startswith("/"):
        raise ContinuationSafetyError("run_root and source_root must be absolute POSIX paths")
    result["run_root"] = run_root
    result["source_root"] = source_root
    if result.get("gpu_ids") != [1]:
        raise ContinuationSafetyError(
            "continuation queue must explicitly expose GPU1 only"
        )
    if float(result.get("gpu_budget_hours", 168.0)) != 168.0:
        raise ContinuationSafetyError("continuation queue must freeze 168 GPU-hours")
    if float(result.get("min_free_disk_gib", 40.0)) != 40.0:
        raise ContinuationSafetyError("continuation queue must freeze 40 GiB")
    datasets = result["datasets"]
    if not isinstance(datasets, Mapping) or set(datasets) != set(FOUR_DOMAINS):
        raise ContinuationSafetyError("continuation protocol requires exactly four domains")
    for dataset in FOUR_DOMAINS:
        row = datasets[dataset]
        if not isinstance(row, Mapping):
            raise ContinuationSafetyError(f"dataset config is not an object: {dataset}")
        _require_sha(row.get("split_sha256"), f"{dataset} split_sha256")
        _require_sha(row.get("config_sha256"), f"{dataset} config_sha256")
    if tuple(result["risk14_arms"]) != RISK14_ARMS:
        raise ContinuationSafetyError(f"RISK-14 arms must be exactly {RISK14_ARMS}")
    selection = result["risk14_selection"]
    if not isinstance(selection, list) or len(selection) != 2:
        raise ContinuationSafetyError("RISK-14 selection must contain one high-risk and one low-risk condition")
    ranks: set[str] = set()
    for row in selection:
        if not isinstance(row, Mapping):
            raise ContinuationSafetyError("RISK-14 selection rows must be objects")
        rank = str(row.get("rank"))
        if rank not in {"high_risk", "low_risk"} or rank in ranks:
            raise ContinuationSafetyError("RISK-14 selection ranks must be unique high_risk and low_risk")
        ranks.add(rank)
        if str(row.get("dataset")) not in FOUR_DOMAINS:
            raise ContinuationSafetyError("RISK-14 selection dataset is outside four-domain protocol")
        if int(row.get("corruption_level", -1)) not in {0, 20, 40, 60, 80, 100}:
            raise ContinuationSafetyError("RISK-14 corruption level must be a frozen bank level")
        if row.get("train_only") is not True:
            raise ContinuationSafetyError("RISK-14 condition selection must be train-only")
        _require_sha(row.get("selection_sha256"), f"RISK-14 {rank} selection_sha256")
        if row.get("bank_sha256") is not None:
            _require_sha(row["bank_sha256"], f"RISK-14 {rank} bank_sha256")
    if ranks != {"high_risk", "low_risk"}:
        raise ContinuationSafetyError("RISK-14 selection must include high_risk and low_risk")
    _reject_forbidden(selection, "risk14_selection")
    estimates = result["estimates"]
    if not isinstance(estimates, Mapping):
        raise ContinuationSafetyError("estimates must be an object")
    for name in ("method_gate", "risk13", "risk14", "risk10", "risk11"):
        row = estimates.get(name)
        if not isinstance(row, Mapping):
            raise ContinuationSafetyError(f"missing estimate: {name}")
        low = _finite(row.get("low"), f"{name}.low")
        high = _finite(row.get("high"), f"{name}.high")
        if high < low:
            raise ContinuationSafetyError(f"{name}.high must be >= low")
        _finite(row.get("output_gib"), f"{name}.output_gib")
    return result


def _diffrec_audit(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"status": "diffrec_blocked", "reason": "identity/memory audit not supplied"}
    try:
        audit = _load_json(Path(path), "DiffRec identity/memory audit")
        _reject_forbidden(audit, "diffrec_audit")
        if audit.get("status") != "pass":
            raise ContinuationSafetyError("audit status is not pass")
        if audit.get("model_identity") != "DiffRec":
            raise ContinuationSafetyError("audit model identity is not DiffRec")
        _require_revision(audit.get("source_revision"), "DiffRec source_revision")
        _require_sha(audit.get("config_sha256"), "DiffRec config_sha256")
        _require_sha(audit.get("split_sha256"), "DiffRec split_sha256")
        peak = _finite(audit.get("peak_memory_gib"), "DiffRec peak_memory_gib")
        limit = _finite(audit.get("memory_limit_gib"), "DiffRec memory_limit_gib")
        if peak > limit:
            raise ContinuationSafetyError("DiffRec memory audit exceeds limit")
    except ContinuationSafetyError as exc:
        return {"status": "diffrec_blocked", "reason": str(exc), "audit_sha256": sha256_file(Path(path))}
    return {
        "status": "pass", "audit_sha256": sha256_file(Path(path)), "model_identity": "DiffRec",
        "source_revision": audit["source_revision"], "config_sha256": audit["config_sha256"],
        "split_sha256": audit["split_sha256"], "peak_memory_gib": float(audit["peak_memory_gib"]),
        "memory_limit_gib": float(audit["memory_limit_gib"]),
    }


def _relative_task_path(*parts: str) -> str:
    return "/".join(("runs", "continuation", *parts))


def _task(
    protocol: Mapping[str, Any], *, ledger_id: str, task_id: str, model: str, dataset: str, arm: str,
    relative_dir: str, dependencies: list[str], atomic_group: str | None, estimate_name: str,
    config_sha256: str, split_sha256: str, bank_sha256: str | None, extra_args: list[str] | None = None,
    extra_env: Mapping[str, str] | None = None, priority: int = 1,
) -> dict[str, Any]:
    run_dir = f"{protocol['run_root']}/{relative_dir}"
    estimate = protocol["estimates"][estimate_name]
    argv = [
        str(protocol["python_bin"]), str(protocol["continuation_entrypoint"]), "--model", model,
        "--dataset", dataset, "--arm", arm, "--seed", "100", "--run-dir", run_dir,
        "--evaluator-version", str(protocol["evaluator_version"]), "--selector-version", str(protocol["selector_version"]),
        "--config-sha256", config_sha256, "--split-sha256", split_sha256,
    ]
    if bank_sha256 is not None:
        argv.extend(["--bank-sha256", bank_sha256])
    argv.extend(str(item) for item in (extra_args or []))
    env: dict[str, str] = {
        "PYTHONHASHSEED": "100", "AAAI_DATASET": dataset, "AAAI_ARM": arm,
        "AAAI_EVALUATOR_VERSION": str(protocol["evaluator_version"]), "AAAI_SELECTOR_VERSION": str(protocol["selector_version"]),
        "AAAI_E1_MARKER_SHA256": str(protocol["_e1_marker_sha256"]),
        "AAAI_RISK08_MARKER_SHA256": str(protocol["_risk08_marker_sha256"]),
        "AAAI_RISK05_PREREG_SHA256": str(protocol["risk05_preregistration_sha256"]),
    }
    if extra_env:
        env.update({str(key): str(value) for key, value in extra_env.items()})
    return {
        "schema_version": 1, "task_id": task_id, "ledger_id": ledger_id, "phase": "continuation", "branch": "method_pass",
        "kind": "gpu", "argv": argv, "cwd": run_dir, "env": env,
        "dependencies": list(dependencies),
        "required_markers": ["markers/RISK-02_PASS.json", "markers/RISK-05_PASS.json", "markers/RISK-08_EXIT.json"],
        "success_artifacts": [f"{relative_dir}/artifact_manifest.json"], "failure_policy": "fail_closed", "max_attempts": 1,
        "gpu_slots": 1, "gpu_hours_low": float(estimate["low"]), "gpu_hours_high": float(estimate["high"]),
        "estimated_output_gib": float(estimate["output_gib"]), "seed": 100, "dataset": dataset, "arm": arm, "model": model,
        "run_dir": run_dir, "code_revision": str(protocol["code_revision"]), "config_sha256": config_sha256,
        "split_sha256": split_sha256, "bank_sha256": bank_sha256, "evaluator_version": str(protocol["evaluator_version"]),
        "selector_version": str(protocol["selector_version"]), "atomic_group": atomic_group, "priority": int(priority),
    }


def _gate_task(protocol: Mapping[str, Any]) -> dict[str, Any]:
    estimate = protocol["estimates"]["method_gate"]
    run_root = str(protocol["run_root"])
    return {
        "schema_version": 1, "task_id": "continuation.method_pass_gate", "ledger_id": "RISK-08", "phase": "continuation",
        "branch": "method_pass", "kind": "contract_gate",
        "argv": [str(protocol["python_bin"]), str(protocol["method_gate_script"]), "--queue-root", run_root,
                  "--e1-marker", "markers/RISK-02_PASS.json", "--risk08-marker", "markers/RISK-08_EXIT.json",
                  "--risk05-preregistration-sha256", str(protocol["risk05_preregistration_sha256"])],
        "cwd": str(protocol["source_root"]),
        "env": {"PYTHONHASHSEED": "100", "AAAI_E1_MARKER_SHA256": str(protocol["_e1_marker_sha256"]),
                "AAAI_RISK08_MARKER_SHA256": str(protocol["_risk08_marker_sha256"]),
                "AAAI_RISK05_PREREG_SHA256": str(protocol["risk05_preregistration_sha256"])},
        "dependencies": [], "required_markers": ["markers/RISK-02_PASS.json", "markers/RISK-05_PASS.json", "markers/RISK-08_EXIT.json"],
        "success_artifacts": ["state/method_pass_gate.json"], "failure_policy": "fail_closed", "max_attempts": 1,
        "gpu_slots": 0, "gpu_hours_low": float(estimate["low"]), "gpu_hours_high": float(estimate["high"]),
        "estimated_output_gib": float(estimate["output_gib"]), "seed": None, "dataset": None, "arm": "method_pass_gate",
        "model": None, "run_dir": f"{run_root}/gates/method_pass", "code_revision": str(protocol["code_revision"]),
        "config_sha256": str(protocol["source_manifest_sha256"]), "split_sha256": None, "bank_sha256": None,
        "evaluator_version": None, "selector_version": None, "atomic_group": None, "priority": 0,
    }


def _build_continuation_tasks(protocol: Mapping[str, Any], diffrec: Mapping[str, Any]) -> list[dict[str, Any]]:
    gate_id = "continuation.method_pass_gate"
    tasks: list[dict[str, Any]] = [_gate_task(protocol)]
    datasets = protocol["datasets"]
    for dataset in FOUR_DOMAINS:
        row = datasets[dataset]
        for arm in RISK13_ARMS:
            relative = _relative_task_path("RISK-13", dataset, arm)
            tasks.append(_task(protocol, ledger_id="RISK-13", task_id=f"continuation.RISK-13.{dataset}.{arm}.seed100",
                               model="PreferGrow", dataset=dataset, arm=arm, relative_dir=relative, dependencies=[gate_id],
                               atomic_group=f"RISK-13.{dataset}.matched", estimate_name="risk13",
                               config_sha256=str(row["config_sha256"]), split_sha256=str(row["split_sha256"]),
                               bank_sha256=str(row["bank_sha256"]) if arm == "risk_gated_full" and row.get("bank_sha256") else None,
                               extra_args=["--matched-pair", f"RISK-13.{dataset}.matched"], priority=1))
    for selection in sorted(protocol["risk14_selection"], key=lambda row: str(row["rank"])):
        rank, dataset, level = str(selection["rank"]), str(selection["dataset"]), int(selection["corruption_level"])
        row = datasets[dataset]
        bank_sha = str(selection.get("bank_sha256") or row.get("bank_sha256"))
        for arm in RISK14_ARMS:
            relative = _relative_task_path("RISK-14", rank, dataset, f"c{level}", arm)
            tasks.append(_task(protocol, ledger_id="RISK-14", task_id=f"continuation.RISK-14.{rank}.{dataset}.c{level}.{arm}.seed100",
                               model="PreferGrow", dataset=dataset, arm=arm, relative_dir=relative, dependencies=[gate_id],
                               atomic_group=f"RISK-14.{rank}.{dataset}.c{level}", estimate_name="risk14",
                               config_sha256=str(row["config_sha256"]), split_sha256=str(row["split_sha256"]), bank_sha256=bank_sha,
                               extra_args=["--condition-rank", rank, "--corruption-level", str(level),
                                           "--train-only-selection-sha256", str(selection["selection_sha256"])],
                               extra_env={"AAAI_RISK14_SELECTION_SHA256": str(selection["selection_sha256"])}, priority=2))
    for model in CLASSIC_MODELS:
        atomic_group = f"RISK-10.{model}.four-domain"
        for dataset in FOUR_DOMAINS:
            row = datasets[dataset]
            relative = _relative_task_path("RISK-10", model, dataset)
            tasks.append(_task(protocol, ledger_id="RISK-10", task_id=f"continuation.RISK-10.{model}.{dataset}.seed100",
                               model=model, dataset=dataset, arm="author_default", relative_dir=relative, dependencies=[gate_id],
                               atomic_group=atomic_group, estimate_name="risk10", config_sha256=str(row["config_sha256"]),
                               split_sha256=str(row["split_sha256"]), bank_sha256=None,
                               extra_args=["--all-four-atomic-group", atomic_group], priority=3))
    if diffrec.get("status") == "pass":
        atomic_group = "RISK-11.DiffRec.four-domain"
        for dataset in FOUR_DOMAINS:
            relative = _relative_task_path("RISK-11", "DiffRec", dataset)
            tasks.append(_task(protocol, ledger_id="RISK-11", task_id=f"continuation.RISK-11.DiffRec.{dataset}.seed100",
                               model="DiffRec", dataset=dataset, arm="author_default", relative_dir=relative, dependencies=[gate_id],
                               atomic_group=atomic_group, estimate_name="risk11",
                               config_sha256=str(diffrec["config_sha256"]), split_sha256=str(diffrec["split_sha256"]), bank_sha256=None,
                               extra_args=["--identity-audit-sha256", str(diffrec["audit_sha256"]), "--source-revision", str(diffrec["source_revision"])],
                               extra_env={"AAAI_DIFFREC_AUDIT_SHA256": str(diffrec["audit_sha256"])}, priority=4))
    return tasks


def build_method_pass_manifest(
    protocol: Mapping[str, Any], base_manifest: Mapping[str, Any] | None, output_root: Path, *,
    e1_marker_path: Path, risk08_marker_path: Path, risk05_preregistration_path: Path,
    diffrec_audit_path: Path | None = None,
) -> dict[str, Any]:
    """Build a dated continuation manifest and write only local immutable artifacts."""
    config = _validate_protocol(protocol)
    output_root = _dated_absent(Path(output_root))
    e1, e1_sha = _validate_e1(Path(e1_marker_path))
    prereg, prereg_expected = _validate_preregistration(Path(risk05_preregistration_path), str(config["risk05_preregistration_sha256"]))
    risk08, risk08_sha = _validate_risk08(Path(risk08_marker_path), e1_sha256=e1_sha, prereg_sha256=prereg_expected)
    config["_e1_marker_sha256"], config["_risk08_marker_sha256"] = e1_sha, risk08_sha
    diffrec = _diffrec_audit(Path(diffrec_audit_path) if diffrec_audit_path is not None else None)
    base_tasks: list[dict[str, Any]] = []
    if base_manifest is not None:
        if not isinstance(base_manifest, Mapping):
            raise ContinuationSafetyError("base manifest must be a JSON object")
        decoded_base = QueueManifest.from_dict(dict(base_manifest))
        try:
            validate_manifest(decoded_base)
        except ManifestError as exc:
            raise ContinuationSafetyError(f"base pilot manifest failed validation: {exc}") from exc
        if decoded_base.run_root != str(config["run_root"]):
            raise ContinuationSafetyError("base manifest run_root does not match continuation protocol")
        base_tasks = [task.to_dict() for task in decoded_base.tasks]
    continuation_tasks = _build_continuation_tasks(config, diffrec)
    all_tasks = base_tasks + continuation_tasks
    high_forecast = sum(float(task["gpu_hours_high"]) for task in all_tasks if task["gpu_slots"] == 1)
    actual_gpu_hours = _finite(config.get("actual_gpu_hours", 0.0), "actual_gpu_hours")
    if actual_gpu_hours + high_forecast > 168.0:
        raise ContinuationSafetyError(f"continuation high forecast exceeds 168 GPU-hours: actual={actual_gpu_hours:g}, high={high_forecast:g}")
    manifest: dict[str, Any] = {
        "schema_version": 1, "queue_id": str(config["queue_id"]), "created_at": str(config["created_at"]),
        "run_root": str(config["run_root"]), "source_root": str(config["source_root"]),
        "source_manifest_sha256": str(config["source_manifest_sha256"]), "ledger_path": str(config["ledger_path"]),
        "ledger_sha256": str(config["ledger_sha256"]), "gpu_ids": list(config["gpu_ids"]), "gpu_budget_hours": 168.0,
        "min_free_disk_gib": 40.0, "tasks": all_tasks,
    }
    try:
        validate_manifest(QueueManifest.from_dict(manifest))
    except ManifestError as exc:
        raise ContinuationSafetyError(f"continuation manifest failed validation: {exc}") from exc
    output_root.mkdir(parents=True)
    (output_root / "queue").mkdir()
    (output_root / "protocol").mkdir()
    queue_path = output_root / "queue" / "queue_seed100_method_pass.json"
    atomic_write_json(queue_path, manifest)
    queue_sha = sha256_file(queue_path)
    metadata: dict[str, Any] = {
        "schema_version": 1, "artifact_type": "aaai27 method-pass continuation adapter manifest",
        "queue_manifest_sha256": queue_sha, "queue_manifest_path": "queue/queue_seed100_method_pass.json",
        "bindings": {"e1_marker_sha256": e1_sha, "risk08_marker_sha256": risk08_sha,
                     "risk05_preregistration_sha256": prereg_expected, "risk08_exit": risk08["exit"],
                     "e1_outcome": e1["outcome"], "risk05_preregistration_file_sha256": sha256_file(Path(risk05_preregistration_path)),
                     "base_manifest_sha256": stable_sha256(base_manifest) if base_manifest is not None else None},
        "task_counts": {ledger: sum(task["ledger_id"] == ledger and task["phase"] == "continuation" for task in all_tasks)
                        for ledger in ("RISK-13", "RISK-14", "RISK-10", "RISK-11")},
        "continuation_task_count": len(continuation_tasks), "gpu_hours_high_forecast": float(high_forecast),
        "actual_gpu_hours": float(actual_gpu_hours), "diffrec_audit": diffrec,
        "risk14_selection": list(config["risk14_selection"]), "partial_seed100": True, "training_started": False,
        "remote_launch": False, "no_retry": True, "failure_policy": "fail_closed",
        "evaluator_version": str(config["evaluator_version"]), "selector_version": str(config["selector_version"]),
        "code_revision": str(config["code_revision"]), "preregistration_payload_sha256": stable_sha256(prereg),
    }
    metadata["artifact_sha256"] = _payload_hash(metadata)
    atomic_write_json(output_root / "adapter_manifest.json", metadata)
    snapshot = dict(config)
    snapshot.pop("_e1_marker_sha256", None)
    snapshot.pop("_risk08_marker_sha256", None)
    atomic_write_json(output_root / "protocol" / "method_pass_protocol.json", snapshot)
    markdown = "\n".join([
        "# Method-pass continuation adapter manifest", "", f"Queue manifest SHA-256: `{queue_sha}`",
        f"Continuation tasks: `{len(continuation_tasks)}`", f"High forecast (GPU-hours): `{high_forecast:.6g}` / `168`",
        "RISK-13 seed-100 status: `partial_seed100`", f"DiffRec audit: `{diffrec['status']}`", "",
        "Build-only dated artifact: `training_started=false`, `remote_launch=false`.",
        "Every continuation GPU task is seed 100, attempt one, fail-closed, and depends on `continuation.method_pass_gate`.", "",
    ])
    write_bytes_exclusive(output_root / "adapter_manifest.md", markdown.encode("utf-8"))
    return manifest
