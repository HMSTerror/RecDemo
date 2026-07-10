from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Sequence

from .controller import QueueController, linux_process_matches
from .models import GateSnapshot, QueueManifest
from .runtime import LinuxFlockBackend, ProcessSupervisor, QueueRuntime
from .scheduler import select_active_branch
from .storage import atomic_create_json, load_json
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
    records_dir = root / "state" / "tasks"
    record_count = len(list(records_dir.glob("*.json"))) if records_dir.is_dir() else 0
    return {
        "status": "present",
        "queue_root": str(root),
        "stop_requested": stop_requested,
        "record_count": record_count,
        "manifest_present": manifest_path.is_file(),
    }


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
    try:
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
