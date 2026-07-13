from __future__ import annotations

from .models import GateSnapshot, QueueManifest, TaskRecord, TaskSpec


class IntegrityError(RuntimeError):
    """Raised when mutually exclusive or impossible gate evidence is present."""


def select_active_branch(gates: GateSnapshot) -> str:
    if gates.e1_outcome is None:
        if gates.risk08_exit is not None:
            raise IntegrityError("RISK-08 exit cannot exist before E1 terminal outcome")
        return "common"
    if gates.e1_outcome not in {"pass", "fail"}:
        raise IntegrityError(f"unknown E1 outcome: {gates.e1_outcome}")
    if gates.risk08_exit is None:
        return "e1_pass" if gates.e1_outcome == "pass" else "e1_fail_audit"
    if gates.risk08_exit not in {"risk_gated_method", "audit_only", "submission_stop"}:
        raise IntegrityError(f"unknown RISK-08 exit: {gates.risk08_exit}")
    if gates.risk08_exit == "risk_gated_method":
        if gates.e1_outcome != "pass":
            raise IntegrityError("risk_gated_method requires E1 pass")
        return "method_pass"
    return "terminal_stop"


def choose_ready_tasks(
    manifest: QueueManifest,
    records: dict[str, TaskRecord],
    gates: GateSnapshot,
    actual_gpu_hours: float,
    free_disk_gib: float,
    busy_gpu_ids: set[int],
) -> list[TaskSpec]:
    branch = select_active_branch(gates)
    if branch == "terminal_stop" or free_disk_gib < manifest.min_free_disk_gib:
        return []

    passed = {task_id for task_id, record in records.items() if record.status == "passed"}
    started = {task_id for task_id, record in records.items() if record.attempt > 0}
    candidates: list[TaskSpec] = []
    for task in manifest.tasks:
        if task.task_id in started:
            continue
        if task.branch not in {"common", branch}:
            continue
        if not set(task.dependencies).issubset(passed):
            continue
        candidates.append(task)

    remaining_gpu_slots = len(set(manifest.gpu_ids) - busy_gpu_ids)
    reserved_gpu_hours = actual_gpu_hours
    selected: list[TaskSpec] = []
    for task in sorted(candidates, key=lambda item: (item.priority, item.task_id)):
        if task.gpu_slots == 0:
            selected.append(task)
            continue
        if remaining_gpu_slots <= 0:
            continue
        if reserved_gpu_hours + task.gpu_hours_high > manifest.gpu_budget_hours:
            continue
        selected.append(task)
        remaining_gpu_slots -= 1
        reserved_gpu_hours += task.gpu_hours_high
    return selected


def group_status(
    records: dict[str, TaskRecord],
    tasks: tuple[TaskSpec, ...],
    atomic_group: str,
) -> str:
    members = [task for task in tasks if task.atomic_group == atomic_group]
    if not members:
        return "absent"
    statuses = [records[task.task_id].status if task.task_id in records else "pending" for task in members]
    if any(status in {"failed", "interrupted_unverified"} for status in statuses):
        return "incomplete"
    if all(status == "passed" for status in statuses):
        return "passed"
    if any(status == "running" for status in statuses):
        return "running"
    return "pending"
