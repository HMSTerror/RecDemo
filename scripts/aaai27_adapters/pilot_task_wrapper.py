from __future__ import annotations

import json
import math
import os
import re
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from .common import atomic_write_json, sha256_file, stable_sha256


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
WRAPPER_ERROR_EXIT = 97


class PilotWrapperError(RuntimeError):
    """Raised when a pilot task cannot produce trustworthy artifacts."""


def _require_env(env: Mapping[str, str], name: str) -> str:
    value = env.get(name)
    if not isinstance(value, str) or not value:
        raise PilotWrapperError(f"missing required environment variable: {name}")
    return value


def _require_sha256(value: str, label: str) -> str:
    if SHA256_RE.fullmatch(value) is None:
        raise PilotWrapperError(f"{label} must be a lowercase SHA-256")
    return value


def _require_revision(value: str) -> str:
    if REVISION_RE.fullmatch(value) is None:
        raise PilotWrapperError("AAAI_CODE_REVISION must be a 40-character revision")
    return value


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _resolve_queue_relative(root: Path, value: str, label: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts or str(relative) in {"", "."}:
        raise PilotWrapperError(f"{label} must be a safe queue-relative path")
    resolved = (root / relative).resolve()
    if not _inside(resolved, root):
        raise PilotWrapperError(f"{label} leaves the dated queue root")
    return resolved


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PilotWrapperError(f"cannot load {label}: {path}") from exc
    if not isinstance(value, dict):
        raise PilotWrapperError(f"{label} must contain a JSON object: {path}")
    return value


def _require_finite_json(value: Any, path: str = "root") -> None:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise PilotWrapperError(f"non-finite numeric value in selected summary: {path}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _require_finite_json(child, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, child in value.items():
            _require_finite_json(child, f"{path}.{key}")
        return
    raise PilotWrapperError(f"unsupported selected-summary value at {path}")


def _metric_at_10(summary: Mapping[str, Any], split: str, metric: str) -> float:
    try:
        value = summary[split]["p5"][metric][2]
    except (KeyError, IndexError, TypeError) as exc:
        raise PilotWrapperError(
            f"selected summary lacks {split}.p5.{metric}[2]"
        ) from exc
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PilotWrapperError(f"selected summary {split} {metric}@10 is not numeric")
    result = float(value)
    if not math.isfinite(result):
        raise PilotWrapperError(f"selected summary {split} {metric}@10 is non-finite")
    return result


def _validate_selected_summary(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PilotWrapperError(f"selected summary is missing: {path}")
    summary = _load_object(path, "selected summary")
    _require_finite_json(summary)
    if isinstance(summary.get("best_step"), bool) or not isinstance(
        summary.get("best_step"), int
    ):
        raise PilotWrapperError("selected summary best_step must be an integer")
    for split in ("validation", "test"):
        for metric in ("hr", "ndcg"):
            _metric_at_10(summary, split, metric)
    return summary


def _write_and_forward(handle, payload: bytes) -> None:
    handle.write(payload)
    handle.flush()
    stream = getattr(sys.stdout, "buffer", None)
    if stream is not None:
        stream.write(payload)
        stream.flush()
    else:  # pragma: no cover - normal CLI stdout has a byte buffer
        sys.stdout.write(payload.decode("utf-8", errors="replace"))
        sys.stdout.flush()


def _audit_line(event: str, payload: Mapping[str, Any]) -> bytes:
    row = {"event": event, **dict(payload)}
    return (
        json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def _validate_queue_binding(
    manifest: Mapping[str, Any],
    *,
    task_id: str,
    run_dir: Path,
    summary_relative: str,
    artifact_relative: str,
) -> None:
    tasks = manifest.get("tasks")
    if not isinstance(tasks, list):
        raise PilotWrapperError("queue manifest lacks a task list")
    matches = [
        task
        for task in tasks
        if isinstance(task, dict) and task.get("task_id") == task_id
    ]
    if len(matches) != 1:
        raise PilotWrapperError("queue manifest does not bind exactly one wrapper task")
    task = matches[0]
    if Path(str(task.get("run_dir", ""))).resolve() != run_dir:
        raise PilotWrapperError("queue task run_dir differs from wrapper run_dir")
    if task.get("success_artifacts") != [summary_relative, artifact_relative]:
        raise PilotWrapperError("queue task success artifacts differ from wrapper contract")


def _null_curve_reference(env: Mapping[str, str]) -> dict[str, Any]:
    policy = _require_env(env, "AAAI_NULL_CURVE_REFERENCE_POLICY")
    if policy == "not_applicable":
        return {"policy": policy}
    if policy != "frozen_clean_calibration":
        raise PilotWrapperError(f"unsupported null-curve reference policy: {policy}")
    path = Path(_require_env(env, "AAAI_NULL_CURVE_PATH")).resolve()
    expected_hash = _require_sha256(
        _require_env(env, "AAAI_NULL_CURVE_SHA256"),
        "AAAI_NULL_CURVE_SHA256",
    )
    if not path.is_file() or sha256_file(path) != expected_hash:
        raise PilotWrapperError("frozen clean null-curve hash mismatch")
    source_bank = _require_sha256(
        _require_env(env, "AAAI_NULL_CURVE_SOURCE_BANK_SHA256"),
        "AAAI_NULL_CURVE_SOURCE_BANK_SHA256",
    )
    current_embedding = _require_sha256(
        _require_env(env, "AAAI_CURRENT_EMBEDDING_SHA256"),
        "AAAI_CURRENT_EMBEDDING_SHA256",
    )
    declared_embedding = _require_sha256(
        _require_env(env, "AAAI_EMBEDDING_SHA256"),
        "AAAI_EMBEDDING_SHA256",
    )
    if current_embedding != declared_embedding:
        raise PilotWrapperError("current embedding hash differs from task binding")
    return {
        "policy": policy,
        "path": str(path),
        "sha256": expected_hash,
        "source_bank_sha256": source_bank,
        "current_embedding_sha256": current_embedding,
    }


def run_pilot_task(
    child_argv: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
) -> int:
    if not child_argv or any(not isinstance(token, str) or not token for token in child_argv):
        raise PilotWrapperError("child argv must be a nonempty string sequence")
    source_env = dict(os.environ if env is None else env)
    task_id = _require_env(source_env, "AAAI_TASK_ID")
    queue_root = Path(_require_env(source_env, "AAAI_QUEUE_ROOT")).resolve()
    run_dir = Path(_require_env(source_env, "AAAI_RUN_DIR")).resolve()
    if not _inside(run_dir, queue_root):
        raise PilotWrapperError("run directory leaves the dated queue root")
    if Path.cwd().resolve() != run_dir:
        raise PilotWrapperError("wrapper cwd must equal the task run directory")
    queue_manifest_path = Path(
        _require_env(source_env, "AAAI_QUEUE_MANIFEST_PATH")
    ).resolve()
    if not _inside(queue_manifest_path, queue_root) or not queue_manifest_path.is_file():
        raise PilotWrapperError("queue manifest is missing or outside the queue root")
    summary_relative = _require_env(source_env, "AAAI_SUMMARY_RELATIVE")
    artifact_relative = _require_env(
        source_env, "AAAI_ARTIFACT_MANIFEST_RELATIVE"
    )
    summary_path = _resolve_queue_relative(
        queue_root, summary_relative, "selected summary path"
    )
    artifact_path = _resolve_queue_relative(
        queue_root, artifact_relative, "artifact manifest path"
    )
    if not _inside(summary_path, run_dir) or artifact_path != run_dir / "artifact_manifest.json":
        raise PilotWrapperError("wrapper output paths differ from the task run directory")
    if artifact_path.exists():
        raise PilotWrapperError("immutable artifact manifest already exists")

    queue_manifest = _load_object(queue_manifest_path, "queue manifest")
    _validate_queue_binding(
        queue_manifest,
        task_id=task_id,
        run_dir=run_dir,
        summary_relative=summary_relative,
        artifact_relative=artifact_relative,
    )
    queue_hash_before = sha256_file(queue_manifest_path)
    code_revision = _require_revision(_require_env(source_env, "AAAI_CODE_REVISION"))
    config_hash = _require_sha256(
        _require_env(source_env, "AAAI_CONFIG_SHA256"), "AAAI_CONFIG_SHA256"
    )
    split_hash = _require_sha256(
        _require_env(source_env, "AAAI_SPLIT_SHA256"), "AAAI_SPLIT_SHA256"
    )
    bank_hash_raw = source_env.get("AAAI_BANK_SHA256")
    bank_hash = (
        _require_sha256(bank_hash_raw, "AAAI_BANK_SHA256")
        if bank_hash_raw
        else None
    )
    evaluator = _require_env(source_env, "AAAI_EVALUATOR_VERSION")
    selector = _require_env(source_env, "AAAI_SELECTOR_VERSION")
    null_reference = _null_curve_reference(source_env)
    gate_scale = None
    if source_env.get("AAAI_GATE_DATASET_SCALE") is not None:
        try:
            gate_scale = float(source_env["AAAI_GATE_DATASET_SCALE"])
        except ValueError as exc:
            raise PilotWrapperError("AAAI_GATE_DATASET_SCALE is not numeric") from exc
        if not math.isfinite(gate_scale) or not 0.0 <= gate_scale <= 1.0:
            raise PilotWrapperError("AAAI_GATE_DATASET_SCALE must be within [0,1]")

    log_path = run_dir / "single_train.log"
    process: subprocess.Popen[bytes] | None = None

    def _forward_signal(signum, _frame) -> None:
        if process is not None and process.poll() is None:
            process.send_signal(signum)

    previous_handlers: dict[int, Any] = {}
    for signum in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[signum] = signal.getsignal(signum)
        signal.signal(signum, _forward_signal)

    try:
        with log_path.open("xb", buffering=0) as log_handle:
            _write_and_forward(
                log_handle,
                _audit_line(
                    "AAAI_PILOT_WRAPPER_START",
                    {"task_id": task_id, "child_argv": list(child_argv)},
                ),
            )
            process = subprocess.Popen(
                list(child_argv),
                cwd=str(run_dir),
                env=source_env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=False,
                bufsize=0,
            )
            assert process.stdout is not None
            for chunk in iter(lambda: process.stdout.read(64 * 1024), b""):
                _write_and_forward(log_handle, chunk)
            exit_code = int(process.wait())
            _write_and_forward(
                log_handle,
                _audit_line(
                    "AAAI_PILOT_WRAPPER_END",
                    {"task_id": task_id, "child_exit_code": exit_code},
                ),
            )
            os.fsync(log_handle.fileno())
    finally:
        for signum, previous in previous_handlers.items():
            signal.signal(signum, previous)

    if exit_code != 0:
        return exit_code
    if not log_path.is_file() or log_path.stat().st_size <= 0:
        raise PilotWrapperError("run-local single_train.log is empty")
    summary = _validate_selected_summary(summary_path)
    queue_hash_after = sha256_file(queue_manifest_path)
    if queue_hash_after != queue_hash_before:
        raise PilotWrapperError("queue manifest changed while the task was running")
    log_relative = log_path.relative_to(queue_root).as_posix()
    artifact: dict[str, Any] = {
        "schema_version": 1,
        "task_id": task_id,
        "status": "pass",
        "seed": 100,
        "child_exit_code": 0,
        "queue_manifest_sha256": queue_hash_before,
        "source_revision": code_revision,
        "config_sha256": config_hash,
        "split_sha256": split_hash,
        "bank_sha256": bank_hash,
        "evaluator_version": evaluator,
        "selector_version": selector,
        "gate_dataset_scale": gate_scale,
        "metrics_provenance": {
            "path": summary_path.relative_to(queue_root).as_posix(),
            "sha256": sha256_file(summary_path),
        },
        "log_provenance": {
            "path": log_relative,
            "sha256": sha256_file(log_path),
            "size_bytes": int(log_path.stat().st_size),
        },
        "null_curve_reference": null_reference,
        "selected_metrics": {
            "best_step": int(summary["best_step"]),
            "validation_hr10": _metric_at_10(summary, "validation", "hr"),
            "validation_ndcg10": _metric_at_10(
                summary, "validation", "ndcg"
            ),
            "test_hr10": _metric_at_10(summary, "test", "hr"),
            "test_ndcg10": _metric_at_10(summary, "test", "ndcg"),
        },
    }
    artifact["artifact_sha256"] = stable_sha256(artifact)
    atomic_write_json(artifact_path, artifact)
    return 0


def cli(child_argv: Sequence[str]) -> int:
    try:
        return run_pilot_task(child_argv)
    except (PilotWrapperError, FileExistsError, OSError) as exc:
        print(f"AAAI pilot wrapper fail-closed: {exc}", file=sys.stderr, flush=True)
        return WRAPPER_ERROR_EXIT
