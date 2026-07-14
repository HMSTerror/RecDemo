from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from scripts.aaai27_continuation.policy import (
    EligibilityContext,
    EligibilityDecision,
    classify_task,
)
from scripts.aaai27_continuation.upstream import (
    UpstreamBinding,
    UpstreamSnapshot,
    verify_r7_upstream,
)
from scripts.aaai27_queue.controller import QueueController, RuntimeAdapter
from scripts.aaai27_queue.models import GateSnapshot, QueueManifest, TaskRecord, TaskSpec
from scripts.aaai27_queue.scheduler import choose_ready_tasks


@dataclass(frozen=True)
class MaintenanceWindow:
    planned_shutdown: datetime
    launch_cutoff: datetime
    buffer_hours: float

    def __post_init__(self) -> None:
        for label, value in (
            ("planned_shutdown", self.planned_shutdown),
            ("launch_cutoff", self.launch_cutoff),
        ):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{label} must be timezone-aware")
        if self.launch_cutoff > self.planned_shutdown:
            raise ValueError("launch_cutoff must not follow planned_shutdown")
        if self.buffer_hours < 0:
            raise ValueError("buffer_hours must be nonnegative")


def _fixed_decision(status: str, reason: str) -> EligibilityDecision:
    return EligibilityDecision(ready=False, status=status, reason=reason)


class ContinuationController:
    def __init__(
        self,
        *,
        queue_root: Path,
        manifest: QueueManifest,
        upstream_binding: UpstreamBinding,
        maintenance: MaintenanceWindow,
        now: Callable[[], datetime],
        free_disk_gib: Callable[[], float],
        live_process: Callable[[int, str], bool],
        gpu_slots_per_card: int = 1,
        min_free_gpu_memory_mib: int = 0,
    ) -> None:
        if gpu_slots_per_card <= 0:
            raise ValueError("gpu_slots_per_card must be positive")
        if min_free_gpu_memory_mib < 0:
            raise ValueError("min_free_gpu_memory_mib must be nonnegative")
        self.queue_root = Path(queue_root).resolve(strict=False)
        self.manifest = manifest
        self.upstream_binding = upstream_binding
        self.maintenance = maintenance
        self._now = now
        self._free_disk_gib = free_disk_gib
        self.gpu_slots_per_card = gpu_slots_per_card
        self.min_free_gpu_memory_mib = min_free_gpu_memory_mib
        self._base = QueueController(
            self.queue_root,
            manifest,
            live_process=live_process,
            free_disk_gib=free_disk_gib,
            now=lambda: now().isoformat(),
        )

    def load_records(self) -> dict[str, TaskRecord]:
        return self._base.load_records()

    def _snapshot(self) -> UpstreamSnapshot:
        return verify_r7_upstream(self.upstream_binding)

    def _committed_gpu_hours(self, records: dict[str, TaskRecord]) -> float:
        actual = sum(record.gpu_seconds for record in records.values()) / 3600.0
        tasks = {task.task_id: task for task in self.manifest.tasks}
        running_reserve = sum(
            tasks[record.task_id].gpu_hours_high
            for record in records.values()
            if record.status == "running"
            and record.task_id in tasks
            and tasks[record.task_id].gpu_slots > 0
        )
        return actual + running_reserve

    def _context(self, records: dict[str, TaskRecord]) -> EligibilityContext:
        passed = frozenset(
            task_id
            for task_id, record in records.items()
            if record.status == "passed"
        )
        committed_gpu_hours = self._committed_gpu_hours(records)
        return EligibilityContext(
            now=self._now(),
            planned_shutdown=self.maintenance.planned_shutdown,
            maintenance_buffer_hours=self.maintenance.buffer_hours,
            queue_root=self.queue_root,
            free_disk_gib=self._free_disk_gib(),
            actual_gpu_hours=committed_gpu_hours,
            gpu_budget_hours=self.manifest.gpu_budget_hours,
            passed_task_ids=passed,
        )

    def eligibility(
        self,
        snapshot: UpstreamSnapshot | None = None,
    ) -> dict[str, EligibilityDecision]:
        upstream = snapshot or self._snapshot()
        records = self.load_records()
        pending = [task for task in self.manifest.tasks if task.task_id not in records]
        if upstream.state == "waiting":
            return {
                task.task_id: _fixed_decision(
                    "blocked_upstream",
                    "r7 has not produced a terminal RISK-08 exit",
                )
                for task in pending
            }
        if not upstream.authorized:
            return {
                task.task_id: _fixed_decision(
                    "preserve_only",
                    f"RISK-08 exit is {upstream.exit_value}",
                )
                for task in pending
            }
        context = self._context(records)
        return {task.task_id: classify_task(task, context) for task in pending}

    def _scheduler_candidates(
        self,
        records: dict[str, TaskRecord],
    ) -> list[TaskSpec]:
        committed_gpu_hours = self._committed_gpu_hours(records)
        busy_gpu_ids = {
            record.gpu_id
            for record in records.values()
            if record.status == "running" and record.gpu_id is not None
        }
        return choose_ready_tasks(
            self.manifest,
            records,
            GateSnapshot(e1_outcome="pass", risk08_exit="risk_gated_method"),
            committed_gpu_hours,
            self._free_disk_gib(),
            busy_gpu_ids,
            available_gpu_slots=(
                len(self.manifest.gpu_ids) * self.gpu_slots_per_card
                if self.gpu_slots_per_card > 1
                else None
            ),
        )

    def tick(self, runtime: RuntimeAdapter) -> None:
        self._base.observe(runtime)
        snapshot = self._snapshot()
        if not snapshot.authorized:
            return
        records = self.load_records()
        decisions = self.eligibility(snapshot)
        for task in self._scheduler_candidates(records):
            decision = decisions.get(task.task_id)
            if decision is not None and decision.ready:
                self._base.start_one(runtime, task)

    def status(self) -> dict[str, object]:
        snapshot = self._snapshot()
        decisions = self.eligibility(snapshot)
        records = self.load_records()
        counts = Counter(decision.status for decision in decisions.values())
        counts.update(record.status for record in records.values())
        gate = (
            "waiting_r7"
            if snapshot.state == "waiting"
            else "method_pass"
            if snapshot.authorized
            else str(snapshot.exit_value)
        )
        return {
            "schema_version": 1,
            "gate": gate,
            "risk08_exit": snapshot.exit_value,
            "queue_root": str(self.queue_root),
            "counts": dict(sorted(counts.items())),
            "completed_r7_tasks": snapshot.completed_task_count,
            "running_r7_tasks": snapshot.running_task_count,
            "planned_shutdown": self.maintenance.planned_shutdown.isoformat(),
            "launch_cutoff": self.maintenance.launch_cutoff.isoformat(),
            "maintenance_buffer_hours": self.maintenance.buffer_hours,
            "gpu_slots_per_card": self.gpu_slots_per_card,
            "min_free_gpu_memory_mib": self.min_free_gpu_memory_mib,
        }
