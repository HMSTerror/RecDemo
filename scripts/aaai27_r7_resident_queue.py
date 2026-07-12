#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.aaai27_adapters.pilot_report import (
    finalize_artifact_derived_risk08,
)
from scripts.aaai27_queue.controller import (
    QueueController,
    linux_process_matches,
)
from scripts.aaai27_queue.models import QueueManifest, TaskRecord, TaskSpec
from scripts.aaai27_queue.runtime import (
    LinuxFlockBackend,
    ProcessSupervisor,
    QueueRuntime,
    linux_process_start_token,
)
from scripts.aaai27_queue.storage import (
    atomic_create_json,
    atomic_write_json,
    load_json,
    sha256_file,
)
from scripts.aaai27_queue.validation import validate_manifest


FINALIZER_CONFIG_RELATIVE = Path("protocol") / "r7_finalizer_config.json"
TERMINAL_RELATIVE = Path("state") / "TERMINAL.json"
ACTIVE_BRANCH = "e1_pass"
INACTIVE_BRANCH = "e1_fail_audit"
EXPECTED_ACTIVE_TASKS = 14
EXPECTED_INACTIVE_TASKS = 8
RISK08_EXITS = {"risk_gated_method", "audit_only", "submission_stop"}


class R7ControllerError(RuntimeError):
    """Raised when the immutable r7 execution contract cannot be proven."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_manifest(path: Path) -> QueueManifest:
    try:
        return QueueManifest.from_dict(load_json(path))
    except (OSError, ValueError, TypeError) as exc:
        raise R7ControllerError(f"invalid queue manifest: {path}") from exc


def _pilot_contract(
    manifest: QueueManifest,
) -> tuple[tuple[TaskSpec, ...], tuple[TaskSpec, ...], str]:
    active = tuple(
        task
        for task in manifest.tasks
        if task.phase == "pilot" and task.branch == ACTIVE_BRANCH
    )
    inactive = tuple(
        task
        for task in manifest.tasks
        if task.phase == "pilot" and task.branch == INACTIVE_BRANCH
    )
    other_pilot = tuple(
        task
        for task in manifest.tasks
        if task.phase == "pilot"
        and task.branch not in {ACTIVE_BRANCH, INACTIVE_BRANCH}
    )
    if len(active) != EXPECTED_ACTIVE_TASKS:
        raise R7ControllerError(
            f"r7 requires {EXPECTED_ACTIVE_TASKS} active pilot tasks, got {len(active)}"
        )
    if len(inactive) != EXPECTED_INACTIVE_TASKS:
        raise R7ControllerError(
            f"r7 requires {EXPECTED_INACTIVE_TASKS} inactive pilot tasks, got {len(inactive)}"
        )
    if other_pilot:
        raise R7ControllerError("r7 manifest contains an unsupported pilot branch")
    revisions = {task.code_revision for task in manifest.tasks}
    if len(revisions) != 1:
        raise R7ControllerError("r7 manifest does not bind one source revision")
    return active, inactive, revisions.pop()


def _require_file(path: Path, label: str) -> Path:
    resolved = Path(path).resolve(strict=False)
    if not resolved.is_file():
        raise R7ControllerError(f"{label} is missing: {resolved}")
    return resolved


def _config_path(queue_root: Path) -> Path:
    return Path(queue_root).resolve(strict=False) / FINALIZER_CONFIG_RELATIVE


def build_finalizer_config(
    queue_root: Path,
    *,
    manifest_path: Path,
    risk05_root: Path,
    risk_preflight_path: Path,
) -> dict[str, Any]:
    """Create the immutable provenance contract used by the resident finalizer."""

    root = Path(queue_root).resolve(strict=False)
    manifest_file = _require_file(manifest_path, "queue manifest")
    manifest = _load_manifest(manifest_file)
    if Path(manifest.run_root).resolve(strict=False) != root:
        raise R7ControllerError("queue root does not match manifest run_root")
    active, inactive, source_revision = _pilot_contract(manifest)

    risk05 = Path(risk05_root).resolve(strict=False)
    risk05_bundle = _require_file(risk05 / "risk05_bundle.json", "RISK-05 bundle")
    risk05_preregistration = _require_file(
        risk05 / "protocol" / "risk05_preregistration.json",
        "RISK-05 preregistration",
    )
    preflight = _require_file(risk_preflight_path, "risk preflight")
    e1_marker = _require_file(
        root / "markers" / "RISK-02_PASS.json",
        "E1 pass marker",
    )

    config: dict[str, Any] = {
        "schema_version": 1,
        "kind": "r7_artifact_derived_risk08_finalizer",
        "queue_root": str(root),
        "queue_manifest_path": str(manifest_file),
        "queue_manifest_sha256": sha256_file(manifest_file),
        "risk05_root": str(risk05),
        "risk05_bundle_path": str(risk05_bundle),
        "risk05_bundle_sha256": sha256_file(risk05_bundle),
        "risk05_preregistration_path": str(risk05_preregistration),
        "risk05_preregistration_sha256": sha256_file(risk05_preregistration),
        "risk_preflight_path": str(preflight),
        "risk_preflight_sha256": sha256_file(preflight),
        "e1_marker_path": str(e1_marker),
        "e1_marker_sha256": sha256_file(e1_marker),
        "source_revision": source_revision,
        "active_task_ids": sorted(task.task_id for task in active),
        "active_task_count": len(active),
        "inactive_task_ids": sorted(task.task_id for task in inactive),
        "inactive_task_count": len(inactive),
        "no_rescue": True,
    }
    atomic_create_json(_config_path(root), config)
    return config


_CONFIG_FIELDS = {
    "schema_version",
    "kind",
    "queue_root",
    "queue_manifest_path",
    "queue_manifest_sha256",
    "risk05_root",
    "risk05_bundle_path",
    "risk05_bundle_sha256",
    "risk05_preregistration_path",
    "risk05_preregistration_sha256",
    "risk_preflight_path",
    "risk_preflight_sha256",
    "e1_marker_path",
    "e1_marker_sha256",
    "source_revision",
    "active_task_ids",
    "active_task_count",
    "inactive_task_ids",
    "inactive_task_count",
    "no_rescue",
}


def _verify_bound_file(
    config: dict[str, Any],
    *,
    path_key: str,
    hash_key: str,
    label: str,
) -> Path:
    raw_path = config.get(path_key)
    expected_hash = config.get(hash_key)
    if not isinstance(raw_path, str):
        raise R7ControllerError(f"{label} path binding is invalid")
    path = _require_file(Path(raw_path), label)
    if not isinstance(expected_hash, str) or sha256_file(path) != expected_hash:
        raise R7ControllerError(f"{label} file hash mismatch")
    return path


def validate_finalizer_config(
    queue_root: Path,
    *,
    manifest_path: Path,
) -> dict[str, Any]:
    """Recompute every finalizer binding before a resident process may run."""

    root = Path(queue_root).resolve(strict=False)
    path = _require_file(_config_path(root), "r7 finalizer config")
    config = load_json(path)
    if set(config) != _CONFIG_FIELDS:
        raise R7ControllerError("r7 finalizer config fields differ from schema")
    if (
        config.get("schema_version") != 1
        or config.get("kind") != "r7_artifact_derived_risk08_finalizer"
        or config.get("no_rescue") is not True
    ):
        raise R7ControllerError("r7 finalizer config identity is invalid")
    if Path(str(config.get("queue_root"))).resolve(strict=False) != root:
        raise R7ControllerError("r7 finalizer queue root binding mismatch")

    requested_manifest = Path(manifest_path).resolve(strict=False)
    bound_manifest = _verify_bound_file(
        config,
        path_key="queue_manifest_path",
        hash_key="queue_manifest_sha256",
        label="queue manifest",
    )
    if bound_manifest != requested_manifest:
        raise R7ControllerError("r7 finalizer manifest path mismatch")
    manifest = _load_manifest(bound_manifest)
    if Path(manifest.run_root).resolve(strict=False) != root:
        raise R7ControllerError("queue root does not match manifest run_root")
    active, inactive, source_revision = _pilot_contract(manifest)
    if config.get("source_revision") != source_revision:
        raise R7ControllerError("r7 finalizer source revision mismatch")
    expected_active = sorted(task.task_id for task in active)
    expected_inactive = sorted(task.task_id for task in inactive)
    if (
        config.get("active_task_count") != EXPECTED_ACTIVE_TASKS
        or config.get("active_task_ids") != expected_active
        or config.get("inactive_task_count") != EXPECTED_INACTIVE_TASKS
        or config.get("inactive_task_ids") != expected_inactive
    ):
        raise R7ControllerError("r7 finalizer task matrix binding mismatch")

    risk05_root = Path(str(config.get("risk05_root"))).resolve(strict=False)
    risk05_bundle = _verify_bound_file(
        config,
        path_key="risk05_bundle_path",
        hash_key="risk05_bundle_sha256",
        label="RISK-05 bundle",
    )
    preregistration = _verify_bound_file(
        config,
        path_key="risk05_preregistration_path",
        hash_key="risk05_preregistration_sha256",
        label="RISK-05 preregistration",
    )
    if risk05_bundle != risk05_root / "risk05_bundle.json":
        raise R7ControllerError("RISK-05 bundle path binding mismatch")
    if preregistration != risk05_root / "protocol" / "risk05_preregistration.json":
        raise R7ControllerError("RISK-05 preregistration path binding mismatch")
    _verify_bound_file(
        config,
        path_key="risk_preflight_path",
        hash_key="risk_preflight_sha256",
        label="risk preflight",
    )
    e1_marker = _verify_bound_file(
        config,
        path_key="e1_marker_path",
        hash_key="e1_marker_sha256",
        label="E1 pass marker",
    )
    if e1_marker != root / "markers" / "RISK-02_PASS.json":
        raise R7ControllerError("E1 pass marker path binding mismatch")
    return config


def _load_existing_terminal(root: Path) -> dict[str, Any] | None:
    path = root / TERMINAL_RELATIVE
    if not path.is_file():
        return None
    terminal = load_json(path)
    if terminal.get("status") != "terminal" or terminal.get("no_rescue") is not True:
        raise R7ControllerError("existing r7 terminal marker is invalid")
    return terminal


def _write_terminal(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    terminal = {
        "schema_version": 1,
        "status": "terminal",
        "created_at": _utc_now(),
        "no_rescue": True,
        **payload,
    }
    atomic_create_json(root / TERMINAL_RELATIVE, terminal)
    return terminal


def maybe_finalize_r7(
    queue_root: Path,
    manifest: QueueManifest,
    records: dict[str, TaskRecord],
    *,
    stop_requested: bool,
    finalizer: Callable[[], dict[str, Any]],
) -> dict[str, Any] | None:
    """Advance the immutable r7 terminal state, or wait for more task evidence."""

    root = Path(queue_root).resolve(strict=False)
    existing = _load_existing_terminal(root)
    if existing is not None:
        return existing

    active, inactive, _ = _pilot_contract(manifest)
    active_ids = {task.task_id for task in active}
    inactive_ids = {task.task_id for task in inactive}
    known_ids = {task.task_id for task in manifest.tasks}
    unknown_ids = sorted(set(records) - known_ids)
    if unknown_ids:
        raise R7ControllerError(f"unknown task records: {unknown_ids}")
    inactive_records = sorted(set(records) & inactive_ids)
    if inactive_records:
        raise R7ControllerError(
            f"inactive E1-fail branch has task records: {inactive_records}"
        )

    active_records = {
        task_id: task_record
        for task_id, task_record in records.items()
        if task_id in active_ids
    }
    allowed_statuses = {"running", "passed", "failed", "interrupted_unverified"}
    invalid_statuses = sorted(
        task_id
        for task_id, task_record in active_records.items()
        if task_record.status not in allowed_statuses
    )
    if invalid_statuses:
        raise R7ControllerError(f"active task records have invalid status: {invalid_statuses}")

    failed = sorted(
        task_id
        for task_id, task_record in active_records.items()
        if task_record.status in {"failed", "interrupted_unverified"}
    )
    if failed:
        return _write_terminal(
            root,
            {
                "outcome": "task_failure",
                "failed_task_ids": failed,
                "completed_task_ids": sorted(
                    task_id
                    for task_id, task_record in active_records.items()
                    if task_record.status == "passed"
                ),
            },
        )

    running = sorted(
        task_id
        for task_id, task_record in active_records.items()
        if task_record.status == "running"
    )
    if stop_requested:
        if running:
            return None
        return _write_terminal(
            root,
            {
                "outcome": "stop_requested",
                "completed_task_ids": sorted(
                    task_id
                    for task_id, task_record in active_records.items()
                    if task_record.status == "passed"
                ),
            },
        )

    passed = sorted(
        task_id
        for task_id, task_record in active_records.items()
        if task_record.status == "passed"
    )
    if running or len(passed) != EXPECTED_ACTIVE_TASKS:
        return None

    marker = finalizer()
    if not isinstance(marker, dict) or marker.get("exit") not in RISK08_EXITS:
        raise R7ControllerError("RISK-08 finalizer returned an invalid exit marker")
    if marker.get("no_rescue", True) is not True:
        raise R7ControllerError("RISK-08 finalizer violated the no-rescue contract")
    return _write_terminal(
        root,
        {
            "outcome": "risk08_exit",
            "risk08_exit": marker["exit"],
            "completed_task_ids": passed,
            "risk08_marker": marker,
        },
    )


def _free_disk_gib(path: Path) -> float:
    return shutil.disk_usage(path).free / (1024**3)


def _finalizer_from_config(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    marker_path = root / "markers" / "RISK-08_EXIT.json"
    if marker_path.is_file():
        marker = load_json(marker_path)
        if (
            marker.get("exit") not in RISK08_EXITS
            or marker.get("no_rescue") is not True
            or marker.get("queue_manifest_sha256")
            != config.get("queue_manifest_sha256")
        ):
            raise R7ControllerError("existing RISK-08 marker fails recovery validation")
        return marker
    return finalize_artifact_derived_risk08(
        root,
        risk05_root=Path(str(config["risk05_root"])),
        risk_preflight_path=Path(str(config["risk_preflight_path"])),
        report_path=root / "reports" / "pilot_report.json",
    )


def _run_command(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.queue_root).resolve(strict=False)
    manifest_path = Path(args.manifest).resolve(strict=False)
    manifest = _load_manifest(manifest_path)
    validate_manifest(manifest)
    if Path(manifest.run_root).resolve(strict=False) != root:
        raise R7ControllerError("queue root does not match manifest run_root")
    config = validate_finalizer_config(root, manifest_path=manifest_path)

    lock_backend = LinuxFlockBackend()
    controller_lock = lock_backend.try_acquire(root / "state" / "controller.lock")
    if controller_lock is None:
        raise R7ControllerError("controller lock is already held")

    state_path = root / "state" / "controller.json"
    process_start_time: str
    try:
        try:
            process_start_time = linux_process_start_token(os.getpid())
        except (OSError, RuntimeError, ValueError):
            process_start_time = f"unverified:{os.getpid()}"
        state_identity = {
            "pid": os.getpid(),
            "process_start_time": process_start_time,
            "queue_root": str(root),
            "manifest_sha256": sha256_file(manifest_path),
            "finalizer_config_sha256": sha256_file(_config_path(root)),
        }
        atomic_write_json(state_path, {"status": "running", **state_identity})
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
        terminal: dict[str, Any] | None = None
        while terminal is None:
            controller.tick(runtime)
            ticks += 1
            terminal = maybe_finalize_r7(
                root,
                manifest,
                controller.load_records(),
                stop_requested=controller.stop_path.is_file(),
                finalizer=lambda: _finalizer_from_config(root, config),
            )
            if terminal is not None or args.once:
                break
            time.sleep(args.poll_seconds)
        return {
            "status": "terminal" if terminal is not None else "waiting",
            "queue_root": str(root),
            "ticks": ticks,
            "terminal": terminal,
        }
    finally:
        try:
            stopped = {
                "status": "stopped",
                "pid": os.getpid(),
                "process_start_time": locals().get("process_start_time"),
                "queue_root": str(root),
                "manifest_sha256": sha256_file(manifest_path),
                "finalizer_config_sha256": (
                    sha256_file(_config_path(root))
                    if _config_path(root).is_file()
                    else None
                ),
            }
            atomic_write_json(state_path, stopped)
        except Exception:
            pass
        controller_lock.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the immutable AAAI-27 r7 pilot queue and original RISK-08 finalizer."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare-finalizer")
    prepare.add_argument("--queue-root", type=Path, required=True)
    prepare.add_argument("--manifest", type=Path, required=True)
    prepare.add_argument("--risk05-root", type=Path, required=True)
    prepare.add_argument("--risk-preflight-json", type=Path, required=True)

    validate = commands.add_parser("validate-finalizer")
    validate.add_argument("--queue-root", type=Path, required=True)
    validate.add_argument("--manifest", type=Path, required=True)

    run = commands.add_parser("run")
    run.add_argument("--queue-root", type=Path, required=True)
    run.add_argument("--manifest", type=Path, required=True)
    run.add_argument("--once", action="store_true")
    run.add_argument("--poll-seconds", type=float, default=10.0)
    return parser


def run_cli(argv: Sequence[str] | None = None) -> tuple[dict[str, Any], int]:
    args = build_parser().parse_args(argv)
    if args.command == "prepare-finalizer":
        return (
            build_finalizer_config(
                args.queue_root,
                manifest_path=args.manifest,
                risk05_root=args.risk05_root,
                risk_preflight_path=args.risk_preflight_json,
            ),
            0,
        )
    if args.command == "validate-finalizer":
        return (
            validate_finalizer_config(
                args.queue_root,
                manifest_path=args.manifest,
            ),
            0,
        )
    if args.command == "run":
        return _run_command(args), 0
    raise R7ControllerError(f"unknown command: {args.command}")


def main(argv: Sequence[str] | None = None) -> None:
    try:
        payload, exit_code = run_cli(argv)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        raise SystemExit(2) from exc
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
