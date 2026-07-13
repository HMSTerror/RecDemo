from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any

from .models import TaskSpec


def require_within(path: Path, root: Path) -> Path:
    resolved = path.resolve(strict=False)
    allowed = root.resolve(strict=False)
    if resolved != allowed and allowed not in resolved.parents:
        raise ValueError(f"path outside allowed root: {resolved}")
    return resolved


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _write_temporary_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with temporary.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    return temporary


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = _write_temporary_json(path, payload)
    try:
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_create_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = _write_temporary_json(path, payload)
    try:
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise FileExistsError(f"refusing to overwrite immutable JSON: {path.name}") from exc
    finally:
        if temporary.exists():
            temporary.unlink()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def append_event(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def load_exclusive_gate(markers_dir: Path, pass_name: str, fail_name: str) -> tuple[str, dict[str, Any]] | None:
    pass_path = markers_dir / pass_name
    fail_path = markers_dir / fail_name
    if pass_path.exists() and fail_path.exists():
        raise ValueError(f"ambiguous gate markers: {pass_name} and {fail_name}")
    if pass_path.exists():
        return "pass", load_json(pass_path)
    if fail_path.exists():
        return "fail", load_json(fail_path)
    return None


def validate_marker(
    marker: dict[str, Any],
    expected_task: TaskSpec,
    queue_sha256: str,
    queue_root: Path,
) -> None:
    required = {
        "schema_version",
        "task_id",
        "ledger_id",
        "status",
        "created_at",
        "queue_manifest_sha256",
        "code_revision",
        "config_sha256",
        "split_sha256",
        "bank_sha256",
        "exit_code",
        "artifacts",
        "validation",
    }
    if set(marker) != required:
        raise ValueError("marker fields differ from schema")
    if marker["schema_version"] != 1:
        raise ValueError("marker schema mismatch")
    if marker["task_id"] != expected_task.task_id or marker["ledger_id"] != expected_task.ledger_id:
        raise ValueError("marker task identity mismatch")
    if marker["queue_manifest_sha256"] != queue_sha256:
        raise ValueError("marker queue hash mismatch")
    if marker["code_revision"] != expected_task.code_revision:
        raise ValueError("marker code revision mismatch")
    if marker["config_sha256"] != expected_task.config_sha256:
        raise ValueError("marker config mismatch")
    if marker["split_sha256"] != expected_task.split_sha256 or marker["bank_sha256"] != expected_task.bank_sha256:
        raise ValueError("marker data identity mismatch")
    if marker["status"] not in {"pass", "fail"} or not isinstance(marker["exit_code"], int):
        raise ValueError("marker terminal status invalid")
    validation = marker["validation"]
    validation_ok = (
        isinstance(validation, dict)
        and validation.get("result") == "pass"
        and isinstance(validation.get("checks"), list)
    )
    if marker["status"] == "pass" and (marker["exit_code"] != 0 or not validation_ok):
        raise ValueError("pass marker lacks successful exit and validation")
    artifacts = marker["artifacts"]
    if not isinstance(artifacts, list) or artifacts != list(expected_task.success_artifacts):
        raise ValueError("marker artifacts differ from task contract")
    for relative in artifacts:
        if not isinstance(relative, str):
            raise ValueError("marker artifact path must be a string")
        artifact = require_within(queue_root / relative, queue_root)
        if not artifact.is_file():
            raise ValueError(f"marker artifact missing: {relative}")
