from __future__ import annotations

import hashlib
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

from .models import GateSnapshot, QueueManifest, TaskRecord, TaskSpec
from .runtime import FinishedChild, StartedChild, linux_process_start_token
from .scheduler import IntegrityError, choose_ready_tasks, select_active_branch
from .storage import append_event, atomic_write_json, load_json, require_within


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def linux_process_matches(pid: int, expected_start_time: str) -> bool:
    if pid <= 0 or not expected_start_time or expected_start_time.startswith("unverified:"):
        return False
    try:
        actual_start_time = linux_process_start_token(pid)
    except (OSError, RuntimeError, ValueError):
        return False
    return actual_start_time == expected_start_time


class RuntimeAdapter(Protocol):
    def observe_finished(self) -> list[FinishedChild]:
        raise NotImplementedError

    def start_task(self, task: TaskSpec, allowed_gpu_ids: tuple[int, ...]) -> StartedChild | None:
        raise NotImplementedError


class QueueController:
    def __init__(
        self,
        root: Path,
        manifest: QueueManifest,
        *,
        live_process: Callable[[int, str], bool],
        free_disk_gib: Callable[[], float],
        now: Callable[[], str] = utc_now,
    ) -> None:
        self.root = root.resolve(strict=False)
        self.manifest = manifest
        self._live_process = live_process
        self._free_disk_gib = free_disk_gib
        self._now = now
        self._tasks = {task.task_id: task for task in manifest.tasks}
        if len(self._tasks) != len(manifest.tasks):
            raise ValueError("duplicate task IDs in queue manifest")
        self._supervised_task_ids: set[str] = set()

    @classmethod
    def for_test(
        cls,
        root: Path,
        manifest: QueueManifest,
        live_process: Callable[[int, str], bool] = lambda pid, started: False,
        free_disk_gib: Callable[[], float] = lambda: 80.0,
        now: Callable[[], str] = utc_now,
    ) -> "QueueController":
        return cls(
            root,
            manifest,
            live_process=live_process,
            free_disk_gib=free_disk_gib,
            now=now,
        )

    def _path(self, *parts: str) -> Path:
        return require_within(self.root.joinpath(*parts), self.root)

    @property
    def records_dir(self) -> Path:
        return self._path("state", "tasks")

    @property
    def events_path(self) -> Path:
        return self._path("logs", "events.jsonl")

    @property
    def stop_path(self) -> Path:
        return self._path("state", "STOP_AFTER_CURRENT")

    def _require_known_task(self, task_id: str) -> TaskSpec:
        try:
            return self._tasks[task_id]
        except KeyError as exc:
            raise ValueError(f"unknown task record: {task_id}") from exc

    def _record_path(self, task_id: str) -> Path:
        self._require_known_task(task_id)
        digest = hashlib.sha256(task_id.encode("utf-8")).hexdigest()
        return require_within(self.records_dir / f"{digest}.json", self.root)

    def save_record(self, record: TaskRecord) -> None:
        path = self._record_path(record.task_id)
        atomic_write_json(path, asdict(record))

    def load_records(self) -> dict[str, TaskRecord]:
        records: dict[str, TaskRecord] = {}
        records_dir = self.records_dir
        if not records_dir.exists():
            return records
        if not records_dir.is_dir():
            raise ValueError(f"task record path is not a directory: {records_dir}")
        for candidate in sorted(records_dir.glob("*.json")):
            path = require_within(candidate, self.root)
            try:
                record = TaskRecord(**load_json(path))
            except TypeError as exc:
                raise ValueError(f"invalid task record schema: {path.name}") from exc
            self._require_known_task(record.task_id)
            if path != self._record_path(record.task_id):
                raise ValueError(f"task record path does not match task identity: {path.name}")
            if record.task_id in records:
                raise ValueError(f"duplicate task record: {record.task_id}")
            records[record.task_id] = record
        return records

    def _append_transition(self, record: TaskRecord, at: str, **extra: object) -> None:
        payload: dict[str, object] = {
            "at": at,
            "task_id": record.task_id,
            "to": record.status,
        }
        payload.update(extra)
        append_event(self.events_path, payload)

    def _interrupt(self, record: TaskRecord, reason: str) -> TaskRecord:
        at = self._now()
        revised = replace(
            record,
            status="interrupted_unverified",
            ended_at=at,
            reason=reason,
        )
        self.save_record(revised)
        self._append_transition(revised, at)
        return revised

    def _reconcile(self, supervised_task_ids: set[str]) -> None:
        for record in self.load_records().values():
            if record.status != "running" or record.task_id in supervised_task_ids:
                continue
            if record.pid is None or record.process_start_time is None:
                self._interrupt(record, "incomplete running process identity")
                continue
            if record.process_start_time.startswith("unverified:"):
                self._interrupt(record, "unverified process identity after controller recovery")
                continue
            try:
                is_live = self._live_process(record.pid, record.process_start_time)
            except Exception:
                is_live = False
            if not is_live:
                self._interrupt(record, "orphaned running record")

    def reconcile(self) -> None:
        self._reconcile(set())

    def load_gates(self) -> GateSnapshot:
        e1_pass = self._path("markers", "RISK-02_PASS.json")
        e1_fail = self._path("markers", "RISK-02_FAIL.json")
        if e1_pass.exists() and e1_fail.exists():
            raise RuntimeError("ambiguous RISK-02 markers")
        e1_outcome = "pass" if e1_pass.exists() else "fail" if e1_fail.exists() else None

        risk08_path = self._path("markers", "RISK-08_EXIT.json")
        risk08_exit: str | None = None
        if risk08_path.exists():
            raw = load_json(risk08_path)
            value = raw.get("exit")
            if not isinstance(value, str):
                raise IntegrityError("RISK-08 exit marker must contain a string exit")
            risk08_exit = value

        gates = GateSnapshot(e1_outcome, risk08_exit)
        select_active_branch(gates)
        return gates

    def ready_tasks(self) -> list[TaskSpec]:
        if self.stop_path.exists():
            return []
        records = self.load_records()
        actual_gpu_hours = sum(record.gpu_seconds for record in records.values()) / 3600.0
        busy_gpu_ids = {
            record.gpu_id
            for record in records.values()
            if record.status == "running" and record.gpu_id is not None
        }
        return choose_ready_tasks(
            self.manifest,
            records,
            self.load_gates(),
            actual_gpu_hours,
            self._free_disk_gib(),
            busy_gpu_ids,
        )

    def _finish_task(self, finished: FinishedChild, records: dict[str, TaskRecord]) -> None:
        self._require_known_task(finished.task_id)
        previous = records.get(finished.task_id)
        if previous is None:
            raise ValueError(f"finished task has no persisted record: {finished.task_id}")
        if previous.status != "running":
            raise ValueError(f"finished task record is not running: {finished.task_id}")

        passed = finished.exit_code == 0 and finished.artifacts_valid
        if passed:
            reason = None
        elif finished.reason is not None:
            reason = finished.reason
        elif finished.exit_code != 0:
            reason = f"exit_code={finished.exit_code}"
        else:
            reason = "success artifacts failed validation"
        at = self._now()
        terminal = replace(
            previous,
            status="passed" if passed else "failed",
            ended_at=at,
            exit_code=finished.exit_code,
            gpu_seconds=finished.gpu_seconds,
            reason=reason,
        )
        self.save_record(terminal)
        self._append_transition(terminal, at)
        records[terminal.task_id] = terminal
        self._supervised_task_ids.discard(terminal.task_id)

    def tick(self, runtime: RuntimeAdapter) -> None:
        records = self.load_records()
        for finished in runtime.observe_finished():
            self._finish_task(finished, records)

        self._reconcile(self._supervised_task_ids)
        if self.stop_path.exists():
            return

        for task in self.ready_tasks():
            child = runtime.start_task(task, self.manifest.gpu_ids)
            if child is None:
                continue
            if child.task_id != task.task_id:
                raise RuntimeError(
                    f"runtime started unexpected task {child.task_id!r} for {task.task_id!r}"
                )
            at = self._now()
            running = TaskRecord(
                task_id=task.task_id,
                status="running",
                attempt=1,
                pid=child.pid,
                process_start_time=child.process_start_time,
                gpu_id=child.gpu_id,
                started_at=at,
                ended_at=None,
                exit_code=None,
                gpu_seconds=0.0,
                reason=None,
            )
            self.save_record(running)
            self._supervised_task_ids.add(task.task_id)
            self._append_transition(running, at, gpu_id=child.gpu_id)
