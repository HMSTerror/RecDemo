from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from scripts.aaai27_queue.models import QueueManifest, TaskRecord
from scripts.aaai27_queue.storage import load_json, require_within, sha256_file
from scripts.aaai27_queue.validation import validate_manifest


ALLOWED_EXITS = {"risk_gated_method", "audit_only", "submission_stop"}


class UpstreamEvidenceError(RuntimeError):
    """Raised when r7 evidence is incomplete, contradictory, or unbound."""


@dataclass(frozen=True)
class UpstreamBinding:
    queue_root: Path
    manifest_path: Path
    manifest_sha256: str
    finalizer_config_path: Path
    finalizer_config_sha256: str
    expected_active_tasks: int = 14


@dataclass(frozen=True)
class UpstreamSnapshot:
    state: str
    authorized: bool
    preserve_only: bool
    exit_value: str | None
    completed_task_count: int
    running_task_count: int
    manifest_sha256: str
    finalizer_config_sha256: str


def _require_hash(path: Path, expected: str, label: str) -> str:
    actual = sha256_file(path)
    if actual != expected:
        raise UpstreamEvidenceError(
            f"{label} SHA-256 mismatch: expected={expected} actual={actual}"
        )
    return actual


def _task_record_path(root: Path, task_id: str) -> Path:
    digest = hashlib.sha256(task_id.encode("utf-8")).hexdigest()
    return root / "state" / "tasks" / f"{digest}.json"


def _load_records(root: Path, manifest: QueueManifest) -> dict[str, TaskRecord]:
    known = {task.task_id for task in manifest.tasks}
    records: dict[str, TaskRecord] = {}
    records_dir = root / "state" / "tasks"
    if not records_dir.exists():
        return records
    if not records_dir.is_dir():
        raise UpstreamEvidenceError("r7 task-record path is not a directory")
    for path in sorted(records_dir.glob("*.json")):
        try:
            record = TaskRecord(**load_json(path))
        except (TypeError, ValueError, OSError) as exc:
            raise UpstreamEvidenceError(f"invalid r7 task record: {path.name}") from exc
        if record.task_id not in known:
            raise UpstreamEvidenceError(f"unknown r7 task record: {record.task_id}")
        if path.resolve() != _task_record_path(root, record.task_id).resolve():
            raise UpstreamEvidenceError(
                f"r7 task record path does not match identity: {record.task_id}"
            )
        if record.task_id in records:
            raise UpstreamEvidenceError(f"duplicate r7 task record: {record.task_id}")
        records[record.task_id] = record
    return records


def _load_bound_inputs(
    binding: UpstreamBinding,
) -> tuple[Path, QueueManifest, dict[str, object]]:
    try:
        root = binding.queue_root.resolve(strict=True)
        manifest_path = require_within(binding.manifest_path, root).resolve(strict=True)
        config_path = require_within(binding.finalizer_config_path, root).resolve(strict=True)
    except (FileNotFoundError, ValueError, OSError) as exc:
        raise UpstreamEvidenceError(f"r7 bound input is unavailable: {exc}") from exc
    _require_hash(manifest_path, binding.manifest_sha256, "manifest")
    _require_hash(config_path, binding.finalizer_config_sha256, "finalizer config")
    try:
        manifest = QueueManifest.from_dict(load_json(manifest_path))
        validate_manifest(manifest)
        config = load_json(config_path)
    except (TypeError, ValueError, OSError) as exc:
        raise UpstreamEvidenceError(f"r7 bound input is invalid: {exc}") from exc
    if Path(manifest.run_root).resolve(strict=False) != root:
        raise UpstreamEvidenceError("r7 manifest run_root does not match bound queue root")
    config_queue_hash = config.get("queue_manifest_sha256")
    if config_queue_hash != binding.manifest_sha256:
        raise UpstreamEvidenceError("r7 finalizer config queue hash mismatch")
    return root, manifest, config


def _validate_terminal(
    terminal: dict[str, object],
    marker: dict[str, object],
    manifest_sha256: str,
) -> str:
    exit_value = marker.get("exit")
    if exit_value not in ALLOWED_EXITS:
        raise UpstreamEvidenceError(f"unknown RISK-08 exit: {exit_value!r}")
    if marker.get("no_rescue") is not True:
        raise UpstreamEvidenceError("RISK-08 marker violates no-rescue contract")
    if marker.get("queue_manifest_sha256") != manifest_sha256:
        raise UpstreamEvidenceError("RISK-08 marker queue hash mismatch")
    if terminal.get("status") != "terminal" or terminal.get("no_rescue") is not True:
        raise UpstreamEvidenceError("r7 terminal marker is invalid")
    if terminal.get("outcome") != "risk08_exit":
        raise UpstreamEvidenceError("r7 terminal outcome is not risk08_exit")
    if terminal.get("risk08_exit") != exit_value:
        raise UpstreamEvidenceError("r7 terminal and RISK-08 exit disagree")
    embedded = terminal.get("risk08_marker")
    if embedded != marker:
        raise UpstreamEvidenceError("r7 terminal embeds a different RISK-08 marker")
    return str(exit_value)


def verify_r7_upstream(binding: UpstreamBinding) -> UpstreamSnapshot:
    root, manifest, _ = _load_bound_inputs(binding)
    records = _load_records(root, manifest)
    active = {task.task_id for task in manifest.tasks if task.branch == "e1_pass"}
    inactive = {task.task_id for task in manifest.tasks if task.branch == "e1_fail_audit"}
    if len(active) != binding.expected_active_tasks:
        raise UpstreamEvidenceError(
            f"r7 manifest active-task count is {len(active)}, expected "
            f"{binding.expected_active_tasks}"
        )
    inactive_records = sorted(set(records) & inactive)
    if inactive_records:
        raise UpstreamEvidenceError(
            f"inactive r7 branch has task records: {inactive_records}"
        )
    active_records = {task_id: records[task_id] for task_id in active if task_id in records}
    failed = sorted(
        task_id
        for task_id, record in active_records.items()
        if record.status in {"failed", "interrupted_unverified"}
    )
    if failed:
        status = active_records[failed[0]].status
        raise UpstreamEvidenceError(f"r7 contains {status} task records: {failed}")
    invalid = sorted(
        task_id
        for task_id, record in active_records.items()
        if record.status not in {"passed", "running"}
    )
    if invalid:
        raise UpstreamEvidenceError(f"r7 contains invalid task statuses: {invalid}")
    passed = sum(record.status == "passed" for record in active_records.values())
    running = sum(record.status == "running" for record in active_records.values())

    terminal_path = root / "state" / "TERMINAL.json"
    marker_path = root / "markers" / "RISK-08_EXIT.json"
    if not terminal_path.exists() and not marker_path.exists():
        return UpstreamSnapshot(
            state="waiting",
            authorized=False,
            preserve_only=False,
            exit_value=None,
            completed_task_count=passed,
            running_task_count=running,
            manifest_sha256=binding.manifest_sha256,
            finalizer_config_sha256=binding.finalizer_config_sha256,
        )
    if terminal_path.exists() != marker_path.exists():
        raise UpstreamEvidenceError(
            "r7 terminal and RISK-08 marker must appear together"
        )
    try:
        terminal = load_json(terminal_path)
        marker = load_json(marker_path)
    except (ValueError, OSError) as exc:
        raise UpstreamEvidenceError(f"invalid r7 terminal evidence: {exc}") from exc
    exit_value = _validate_terminal(terminal, marker, binding.manifest_sha256)
    if running or passed != binding.expected_active_tasks:
        raise UpstreamEvidenceError(
            f"r7 terminal exists without 14/14 passed tasks: passed={passed} running={running}"
        )
    return UpstreamSnapshot(
        state="terminal",
        authorized=exit_value == "risk_gated_method",
        preserve_only=exit_value in {"audit_only", "submission_stop"},
        exit_value=exit_value,
        completed_task_count=passed,
        running_task_count=running,
        manifest_sha256=binding.manifest_sha256,
        finalizer_config_sha256=binding.finalizer_config_sha256,
    )
