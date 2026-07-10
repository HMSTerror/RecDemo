from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any, TypeVar


ModelType = TypeVar("ModelType")


def _validate_exact_fields(cls: type[ModelType], raw: dict[str, Any], label: str) -> None:
    allowed = {field.name for field in fields(cls)}
    unknown = sorted(set(raw) - allowed)
    missing = sorted(allowed - set(raw))
    if unknown:
        raise ValueError(f"unknown {label} fields: {unknown}")
    if missing:
        raise ValueError(f"missing {label} fields: {missing}")


@dataclass(frozen=True)
class TaskSpec:
    schema_version: int
    task_id: str
    ledger_id: str
    phase: str
    branch: str
    kind: str
    argv: tuple[str, ...]
    cwd: str
    env: dict[str, str]
    dependencies: tuple[str, ...]
    required_markers: tuple[str, ...]
    success_artifacts: tuple[str, ...]
    failure_policy: str
    max_attempts: int
    gpu_slots: int
    gpu_hours_low: float
    gpu_hours_high: float
    estimated_output_gib: float
    seed: int | None
    dataset: str | None
    arm: str | None
    model: str | None
    run_dir: str
    code_revision: str
    config_sha256: str
    split_sha256: str | None
    bank_sha256: str | None
    evaluator_version: str | None
    selector_version: str | None
    atomic_group: str | None
    priority: int

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "TaskSpec":
        if not isinstance(raw, dict):
            raise ValueError("task must be a JSON object")
        _validate_exact_fields(cls, raw, "task")
        converted = dict(raw)
        for name in ("argv", "dependencies", "required_markers", "success_artifacts"):
            value = converted[name]
            if not isinstance(value, (list, tuple)):
                raise ValueError(f"task field {name} must be an array")
            converted[name] = tuple(value)
        if not isinstance(converted["env"], dict):
            raise ValueError("task field env must be an object")
        converted["env"] = dict(converted["env"])
        return cls(**converted)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for name in ("argv", "dependencies", "required_markers", "success_artifacts"):
            payload[name] = list(payload[name])
        return payload


@dataclass(frozen=True)
class QueueManifest:
    schema_version: int
    queue_id: str
    created_at: str
    run_root: str
    source_root: str
    source_manifest_sha256: str
    ledger_path: str
    ledger_sha256: str
    gpu_ids: tuple[int, ...]
    gpu_budget_hours: float
    min_free_disk_gib: float
    tasks: tuple[TaskSpec, ...]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "QueueManifest":
        if not isinstance(raw, dict):
            raise ValueError("queue must be a JSON object")
        _validate_exact_fields(cls, raw, "queue")
        converted = dict(raw)
        gpu_ids = converted["gpu_ids"]
        tasks = converted["tasks"]
        if not isinstance(gpu_ids, (list, tuple)):
            raise ValueError("queue field gpu_ids must be an array")
        if not isinstance(tasks, (list, tuple)):
            raise ValueError("queue field tasks must be an array")
        converted["gpu_ids"] = tuple(gpu_ids)
        converted["tasks"] = tuple(TaskSpec.from_dict(item) for item in tasks)
        return cls(**converted)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["gpu_ids"] = list(self.gpu_ids)
        payload["tasks"] = [task.to_dict() for task in self.tasks]
        return payload


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    status: str
    attempt: int
    pid: int | None
    process_start_time: str | None
    gpu_id: int | None
    started_at: str | None
    ended_at: str | None
    exit_code: int | None
    gpu_seconds: float
    reason: str | None


@dataclass(frozen=True)
class GateSnapshot:
    e1_outcome: str | None
    risk08_exit: str | None
