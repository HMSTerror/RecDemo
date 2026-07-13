from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath

from scripts.aaai27_queue.models import TaskSpec
from scripts.aaai27_queue.storage import require_within


@dataclass(frozen=True)
class EligibilityContext:
    now: datetime
    planned_shutdown: datetime
    maintenance_buffer_hours: float
    queue_root: Path
    free_disk_gib: float
    actual_gpu_hours: float
    gpu_budget_hours: float
    passed_task_ids: frozenset[str]


@dataclass(frozen=True)
class EligibilityDecision:
    ready: bool
    status: str
    reason: str | None


def _blocked(status: str, reason: str) -> EligibilityDecision:
    return EligibilityDecision(ready=False, status=status, reason=reason)


def _require_aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")


def _safe_marker(queue_root: Path, marker: str) -> Path:
    relative = PurePosixPath(marker)
    if (
        not marker
        or relative.is_absolute()
        or ".." in relative.parts
        or str(relative) in {"", "."}
    ):
        raise ValueError(f"unsafe required marker: {marker!r}")
    return require_within(queue_root.joinpath(*relative.parts), queue_root)


def classify_task(
    task: TaskSpec,
    context: EligibilityContext,
) -> EligibilityDecision:
    _require_aware(context.now, "now")
    _require_aware(context.planned_shutdown, "planned_shutdown")
    if context.maintenance_buffer_hours < 0:
        raise ValueError("maintenance_buffer_hours must be nonnegative")
    if not set(task.dependencies).issubset(context.passed_task_ids):
        missing = sorted(set(task.dependencies) - context.passed_task_ids)
        return _blocked(
            "blocked_dependency",
            f"dependencies are not terminal-pass: {missing}",
        )
    missing_markers = [
        marker
        for marker in task.required_markers
        if not _safe_marker(context.queue_root, marker).is_file()
    ]
    if missing_markers:
        return _blocked(
            "blocked_adapter",
            f"missing required markers: {missing_markers}",
        )
    if context.free_disk_gib < 40.0:
        return _blocked(
            "blocked_disk",
            "free /data space is below 40 GiB",
        )
    if context.actual_gpu_hours + task.gpu_hours_high > context.gpu_budget_hours:
        return _blocked(
            "blocked_budget",
            "frozen high estimate exceeds queue GPU budget",
        )
    projected_end = context.now + timedelta(
        hours=task.gpu_hours_high + context.maintenance_buffer_hours
    )
    if projected_end > context.planned_shutdown:
        return _blocked(
            "blocked_maintenance",
            "task would cross the planned shutdown after its frozen buffer",
        )
    return EligibilityDecision(ready=True, status="ready", reason=None)
