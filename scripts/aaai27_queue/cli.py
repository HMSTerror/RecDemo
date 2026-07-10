from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Sequence

from .controller import QueueController, linux_process_matches
from .models import GateSnapshot, QueueManifest
from .runtime import LinuxFlockBackend, ProcessSupervisor, QueueRuntime, linux_process_start_token
from .scheduler import select_active_branch
from .storage import atomic_create_json, load_json, sha256_file
from .validation import validate_manifest


def _json_print(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _load_manifest(path: Path) -> QueueManifest:
    return QueueManifest.from_dict(load_json(path))


def _free_disk_gib(path: Path) -> float:
    return shutil.disk_usage(path).free / (1024**3)


def _gate_value(value: str) -> str | None:
    return None if value == "pending" else value


def _validate_command(args: argparse.Namespace) -> dict[str, Any]:
    manifest = _load_manifest(args.manifest)
    validate_manifest(manifest)
    return {
        "status": "valid",
        "queue_id": manifest.queue_id,
        "task_count": len(manifest.tasks),
        "gpu_ids": list(manifest.gpu_ids),
        "seed_values": sorted({task.seed for task in manifest.tasks if task.seed is not None}),
    }


def _dry_run_command(args: argparse.Namespace) -> dict[str, Any]:
    manifest = _load_manifest(args.manifest)
    validate_manifest(manifest)
    gates = GateSnapshot(_gate_value(args.e1_outcome), _gate_value(args.risk08_exit))
    branch = select_active_branch(gates)
    if branch == "terminal_stop":
        tasks = []
    else:
        tasks = [task for task in manifest.tasks if task.branch in {"common", branch}]
    return {
        "status": "dry_run",
        "queue_id": manifest.queue_id,
        "branch": branch,
        "selected_count": len(tasks),
        "task_ids": [task.task_id for task in tasks],
        "seed_values": sorted({task.seed for task in tasks if task.seed is not None}),
        "training_tasks": sum(task.gpu_slots > 0 for task in tasks),
        "queue_root": str(args.queue_root),
    }


def _read_task_records(root: Path) -> dict[str, dict[str, Any]]:
    records_dir = root / "state" / "tasks"
    if not records_dir.is_dir():
        return {}
    records: dict[str, dict[str, Any]] = {}
    for path in sorted(records_dir.glob("*.json")):
        raw = load_json(path)
        task_id = raw.get("task_id")
        if not isinstance(task_id, str) or task_id in records:
            raise ValueError(f"invalid or duplicate task record: {path.name}")
        records[task_id] = raw
    return records


def _read_gate_snapshot(root: Path) -> tuple[GateSnapshot, str]:
    markers = root / "markers"
    pass_path = markers / "RISK-02_PASS.json"
    fail_path = markers / "RISK-02_FAIL.json"
    if pass_path.is_file() and fail_path.is_file():
        raise ValueError("ambiguous RISK-02 markers")
    e1_outcome = "pass" if pass_path.is_file() else "fail" if fail_path.is_file() else None
    risk08_path = markers / "RISK-08_EXIT.json"
    risk08_exit = None
    if risk08_path.is_file():
        raw = load_json(risk08_path)
        value = raw.get("exit")
        if not isinstance(value, str):
            raise ValueError("RISK-08 exit marker must contain a string exit")
        risk08_exit = value
    gates = GateSnapshot(e1_outcome, risk08_exit)
    return gates, select_active_branch(gates)


def _latest_event_at(root: Path) -> str | None:
    events_path = root / "logs" / "events.jsonl"
    if not events_path.is_file():
        return None
    lines = events_path.read_text(encoding="utf-8").splitlines()
    if not lines:
        return None
    try:
        event = json.loads(lines[-1])
    except json.JSONDecodeError:
        return None
    value = event.get("at")
    return value if isinstance(value, str) else None


def _status_payload(root: Path) -> dict[str, Any]:
    if not root.exists():
        return {"status": "absent", "queue_root": str(root), "stop_requested": False}
    if not root.is_dir():
        raise ValueError(f"queue root is not a directory: {root}")
    stop_requested = (root / "state" / "STOP_AFTER_CURRENT").is_file()
    smoke_path = root / "markers" / "SMOKE_PASS.json"
    if smoke_path.is_file():
        marker = load_json(smoke_path)
        status = "smoke_pass" if marker.get("status") == "pass" else "smoke_invalid"
        return {
            "status": status,
            "queue_root": str(root),
            "stop_requested": stop_requested,
            "training_started": bool(marker.get("training_started", True)),
        }

    manifest_path = root / "queue" / "queue_seed100.json"
    records = _read_task_records(root)
    payload: dict[str, Any] = {
        "status": "present",
        "queue_root": str(root),
        "stop_requested": stop_requested,
        "manifest_present": manifest_path.is_file(),
        "record_count": len(records),
        "free_disk_gib": _free_disk_gib(root),
        "latest_event_at": _latest_event_at(root),
        "paths": {
            "manifest": str(manifest_path),
            "state": str(root / "state"),
            "events": str(root / "logs" / "events.jsonl"),
            "markers": str(root / "markers"),
            "runs": str(root / "runs"),
        },
    }
    payload["controller"] = None
    payload["tmux"] = None
    for name in ("controller.json", "tmux_session.json"):
        path = root / "state" / name
        if path.is_file():
            key = name.removesuffix(".json")
            value = load_json(path)
            if key == "controller" and value.get("status") == "running":
                pid = value.get("pid")
                token = value.get("process_start_time")
                value["liveness"] = (
                    linux_process_matches(pid, token)
                    if isinstance(pid, int) and isinstance(token, str)
                    else False
                )
            payload[key] = value
    if not manifest_path.is_file():
        return payload

    payload["manifest_sha256"] = sha256_file(manifest_path)
    try:
        manifest = _load_manifest(manifest_path)
        gates, branch = _read_gate_snapshot(root)
    except Exception as exc:
        payload["status"] = "invalid_manifest"
        payload["error"] = str(exc)
        return payload

    statuses = {"pending": 0, "ready": 0, "running": 0, "passed": 0, "failed": 0, "blocked": 0, "stopped": 0, "interrupted_unverified": 0}
    passed: set[str] = set()
    for task in manifest.tasks:
        raw = records.get(task.task_id)
        if raw is None:
            statuses["pending"] += 1
            continue
        status = raw.get("status")
        if status not in statuses:
            statuses["blocked"] += 1
            continue
        statuses[status] += 1
        if status == "passed":
            passed.add(task.task_id)
    if not stop_requested and branch != "terminal_stop":
        for task in manifest.tasks:
            if task.task_id not in records and task.branch in {"common", branch} and set(task.dependencies).issubset(passed):
                statuses["ready"] += 1
        statuses["pending"] = max(0, statuses["pending"] - statuses["ready"])

    actual_gpu_hours = sum(float(raw.get("gpu_seconds", 0.0)) for raw in records.values()) / 3600.0
    forecast_gpu_hours = actual_gpu_hours + sum(
        task.gpu_hours_high for task in manifest.tasks if task.task_id not in records
    )
    current_gpu: dict[str, dict[str, Any]] = {}
    for raw in records.values():
        if raw.get("status") == "running" and raw.get("gpu_id") is not None:
            current_gpu[str(raw["gpu_id"])] = {
                "task_id": raw.get("task_id"),
                "pid": raw.get("pid"),
                "started_at": raw.get("started_at"),
                "process_start_time": raw.get("process_start_time"),
            }
    payload.update(
        {
            "queue_id": manifest.queue_id,
            "task_count": len(manifest.tasks),
            "branch": branch,
            "gate_e1_outcome": gates.e1_outcome,
            "gate_risk08_exit": gates.risk08_exit,
            "task_counts": statuses,
            "current_gpu_tasks": current_gpu,
            "actual_gpu_hours": actual_gpu_hours,
            "forecast_gpu_hours": forecast_gpu_hours,
            "gpu_budget_hours": manifest.gpu_budget_hours,
            "min_free_disk_gib": manifest.min_free_disk_gib,
        }
    )
    return payload


def _status_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    payload = _status_payload(args.queue_root)
    return payload, 0 if payload["status"] != "absent" else 2


def _request_stop_command(args: argparse.Namespace) -> dict[str, Any]:
    root = args.queue_root
    if not root.is_dir():
        raise ValueError(f"request-stop requires an existing queue root: {root}")
    state = root / "state"
    state.mkdir(exist_ok=True)
    stop_path = state / "STOP_AFTER_CURRENT"
    if not stop_path.exists():
        with stop_path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write("requested\n")
            handle.flush()
    return {"status": "stop_requested", "queue_root": str(root), "path": str(stop_path)}


def _smoke_command(args: argparse.Namespace) -> dict[str, Any]:
    root = args.queue_root
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise ValueError("smoke requires an absent or empty queue root")
    root.mkdir(parents=True, exist_ok=True)
    for name in ("state", "logs", "markers"):
        (root / name).mkdir(exist_ok=True)
    marker = {
        "schema_version": 1,
        "status": "pass",
        "kind": "no-op-smoke",
        "training_started": False,
        "checkpoint_created": False,
        "runs_created": False,
    }
    atomic_create_json(root / "markers" / "SMOKE_PASS.json", marker)
    return {"status": "smoke_pass", "queue_root": str(root), "training_started": False}


def _run_command(args: argparse.Namespace) -> dict[str, Any]:
    root = args.queue_root.resolve(strict=False)
    manifest = _load_manifest(args.manifest)
    validate_manifest(manifest)
    manifest_root = Path(manifest.run_root).resolve(strict=False)
    if root != manifest_root:
        raise ValueError(f"queue root does not match manifest run_root: {root} != {manifest_root}")
    root.mkdir(parents=True, exist_ok=True)
    lock_backend = LinuxFlockBackend()
    controller_lock = lock_backend.try_acquire(root / "state" / "controller.lock")
    if controller_lock is None:
        raise RuntimeError("controller lock is already held")
    controller_state_path = root / "state" / "controller.json"
    try:
        try:
            process_start_time = linux_process_start_token(os.getpid())
        except (OSError, RuntimeError, ValueError):
            process_start_time = f"unverified:{os.getpid()}"
        from .storage import atomic_write_json

        atomic_write_json(
            controller_state_path,
            {
                "status": "running",
                "pid": os.getpid(),
                "process_start_time": process_start_time,
                "queue_root": str(root),
                "manifest_sha256": sha256_file(args.manifest),
            },
        )
        runtime = QueueRuntime(
            queue_root=root,
            supervisor=ProcessSupervisor(),
            lock_backend=lock_backend,
        )
        controller = QueueController(
            root,
            manifest,
            live_process=linux_process_matches,
            free_disk_gib=lambda: _free_disk_gib(root),
        )
        ticks = 0
        while True:
            controller.tick(runtime)
            ticks += 1
            if args.once:
                break
            time.sleep(args.poll_seconds)
        return {"status": "running", "queue_root": str(root), "ticks": ticks}
    finally:
        try:
            from .storage import atomic_write_json

            atomic_write_json(
                controller_state_path,
                {
                    "status": "stopped",
                    "pid": os.getpid(),
                    "queue_root": str(root),
                },
            )
        except Exception:
            pass
        controller_lock.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the AAAI-27 seed-100 resident queue.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "dry-run", "run", "status", "request-stop", "smoke"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--queue-root", type=Path, required=True)
        if name in {"validate", "dry-run", "run"}:
            sub.add_argument("--manifest", type=Path, required=True)
        if name in {"validate", "dry-run", "status"}:
            sub.add_argument("--json", action="store_true")
        if name == "dry-run":
            sub.add_argument("--e1-outcome", choices=("pending", "pass", "fail"), required=True)
            sub.add_argument(
                "--risk08-exit",
                choices=("pending", "risk_gated_method", "audit_only", "submission_stop"),
                required=True,
            )
        if name == "run":
            sub.add_argument("--once", action="store_true")
            sub.add_argument("--poll-seconds", type=float, default=10.0)
    return parser


def run_cli(argv: Sequence[str] | None = None) -> tuple[dict[str, Any], int]:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        return _validate_command(args), 0
    if args.command == "dry-run":
        return _dry_run_command(args), 0
    if args.command == "status":
        return _status_command(args)
    if args.command == "request-stop":
        return _request_stop_command(args), 0
    if args.command == "smoke":
        return _smoke_command(args), 0
    if args.command == "run":
        return _run_command(args), 0
    raise ValueError(f"unknown command: {args.command}")


def main(argv: Sequence[str] | None = None) -> None:
    try:
        payload, exit_code = run_cli(argv)
    except Exception as exc:
        _json_print({"status": "error", "error": str(exc), "error_type": type(exc).__name__})
        raise SystemExit(2) from exc
    _json_print(payload)
    raise SystemExit(exit_code)
