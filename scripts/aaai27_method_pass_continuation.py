from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.aaai27_continuation.controller import (
    ContinuationController,
    MaintenanceWindow,
)
from scripts.aaai27_continuation.manifest import (
    DatasetContract,
    FrozenContinuationInputs,
    RiskCondition,
    build_continuation_manifest,
)
from scripts.aaai27_continuation.upstream import (
    UpstreamBinding,
    verify_r7_upstream,
)
from scripts.aaai27_queue.controller import linux_process_matches
from scripts.aaai27_queue.models import QueueManifest
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
    require_within,
    sha256_file,
)
from scripts.aaai27_queue.validation import validate_manifest
from scripts.audit_e05_sasrec_reuse import audit_e5_root


QUEUE_NAME = "queue_seed100_continuation.json"


class ContinuationCliError(RuntimeError):
    pass


@dataclass(frozen=True)
class PreparedQueue:
    root: Path
    manifest_path: Path
    manifest: QueueManifest
    upstream: UpstreamBinding
    maintenance: MaintenanceWindow


def _parse_inputs(raw: dict[str, Any]) -> FrozenContinuationInputs:
    payload = dict(raw)
    datasets = payload.get("datasets")
    if not isinstance(datasets, dict):
        raise ContinuationCliError("protocol inputs.datasets must be an object")
    payload["datasets"] = {
        name: DatasetContract(**contract) for name, contract in datasets.items()
    }
    payload["high_risk_condition"] = RiskCondition(**payload["high_risk_condition"])
    payload["low_risk_condition"] = RiskCondition(**payload["low_risk_condition"])
    payload["gpu_ids"] = tuple(payload.get("gpu_ids", (0, 1)))
    try:
        return FrozenContinuationInputs(**payload)
    except TypeError as exc:
        raise ContinuationCliError(f"invalid continuation inputs: {exc}") from exc


def _parse_upstream(raw: dict[str, Any]) -> UpstreamBinding:
    try:
        return UpstreamBinding(
            queue_root=Path(raw["queue_root"]),
            manifest_path=Path(raw["manifest_path"]),
            manifest_sha256=str(raw["manifest_sha256"]),
            finalizer_config_path=Path(raw["finalizer_config_path"]),
            finalizer_config_sha256=str(raw["finalizer_config_sha256"]),
            expected_active_tasks=int(raw.get("expected_active_tasks", 14)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ContinuationCliError(f"invalid upstream binding: {exc}") from exc


def _parse_maintenance(raw: dict[str, Any]) -> MaintenanceWindow:
    try:
        return MaintenanceWindow(
            planned_shutdown=datetime.fromisoformat(str(raw["planned_shutdown"])),
            launch_cutoff=datetime.fromisoformat(str(raw["launch_cutoff"])),
            buffer_hours=float(raw["buffer_hours"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ContinuationCliError(f"invalid maintenance window: {exc}") from exc


def _source_adapter_audit(
    source_root: Path,
    manifest: QueueManifest,
) -> dict[str, Any]:
    required = (
        "single_train.py",
        "graph_lib.py",
        "model/text_side.py",
        "scripts/run_aaai27_pilot_task.py",
        "scripts/audit_e05_sasrec_reuse.py",
        "scripts/aaai27_method_pass_continuation.py",
    )
    hashes: dict[str, str] = {}
    for relative in required:
        path = require_within(source_root / relative, source_root)
        if not path.is_file() or path.stat().st_size <= 0:
            raise ContinuationCliError(f"missing production source: {relative}")
        hashes[relative] = sha256_file(path)
    risk13 = [task for task in manifest.tasks if task.ledger_id == "RISK-13"]
    if len(risk13) != 8:
        raise ContinuationCliError("PreferGrow adapter audit requires eight RISK-13 tasks")
    for task in risk13:
        if len(task.argv) < 5 or not task.argv[1].endswith("run_aaai27_pilot_task.py"):
            raise ContinuationCliError(f"RISK-13 task lacks production wrapper: {task.task_id}")
        if "--" not in task.argv or not any(token.endswith("single_train.py") for token in task.argv):
            raise ContinuationCliError(f"RISK-13 task lacks single_train.py: {task.task_id}")
    return {
        "schema_version": 1,
        "status": "pass",
        "adapter": "prefergrow",
        "source_root": str(source_root),
        "source_hashes": hashes,
        "risk13_task_count": len(risk13),
    }


def _adapter_marker(
    adapter: str,
    queue_manifest_sha256: str,
    audit: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "pass",
        "adapter": adapter,
        "queue_manifest_sha256": queue_manifest_sha256,
        "audit": audit,
    }


def prepare_queue(protocol_path: Path) -> dict[str, Any]:
    protocol_path = Path(protocol_path).resolve(strict=True)
    protocol = load_json(protocol_path)
    if protocol.get("schema_version") != 1:
        raise ContinuationCliError("unsupported prepare protocol schema")
    inputs_raw = protocol.get("inputs")
    upstream_raw = protocol.get("upstream")
    maintenance_raw = protocol.get("maintenance")
    if not all(isinstance(value, dict) for value in (inputs_raw, upstream_raw, maintenance_raw)):
        raise ContinuationCliError("prepare protocol lacks inputs/upstream/maintenance objects")
    inputs = _parse_inputs(inputs_raw)
    upstream = _parse_upstream(upstream_raw)
    maintenance = _parse_maintenance(maintenance_raw)
    root = Path(inputs.queue_root).resolve(strict=False)
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"refusing existing nonempty continuation root: {root}")
    source_root = Path(inputs.source_root).resolve(strict=True)
    source_manifest_path = Path(str(protocol.get("source_manifest_path", ""))).resolve(strict=True)
    require_within(source_manifest_path, source_root)
    if sha256_file(source_manifest_path) != inputs.source_manifest_sha256:
        raise ContinuationCliError("source manifest SHA-256 mismatch")
    ledger_path = Path(inputs.ledger_path).resolve(strict=True)
    require_within(ledger_path, source_root)
    if sha256_file(ledger_path) != inputs.ledger_sha256:
        raise ContinuationCliError("ledger SHA-256 mismatch")

    manifest_raw = build_continuation_manifest(inputs)
    manifest = QueueManifest.from_dict(manifest_raw)
    validate_manifest(manifest)
    root.mkdir(parents=True, exist_ok=True)
    for relative in ("queue", "protocol", "state/tasks", "logs/tasks", "runs"):
        (root / relative).mkdir(parents=True, exist_ok=True)
    manifest_path = root / "queue" / QUEUE_NAME
    atomic_create_json(manifest_path, manifest.to_dict())
    manifest_sha256 = sha256_file(manifest_path)
    atomic_create_json(root / "protocol" / "prepare_protocol.json", protocol)
    atomic_create_json(root / "protocol" / "upstream_binding.json", upstream_raw)
    atomic_create_json(root / "protocol" / "maintenance_window.json", maintenance_raw)

    prefergrow_audit = _source_adapter_audit(source_root, manifest)
    for dataset, contract in inputs.datasets.items():
        if not contract.adapter_authorized:
            continue
        dataset_audit = {
            **prefergrow_audit,
            "dataset": dataset,
            "config_sha256": contract.config_sha256,
            "split_sha256": contract.split_sha256,
            "bank_sha256": contract.bank_sha256,
            "embedding_sha256": contract.embedding_sha256,
            "null_curve_sha256": contract.null_curve_sha256,
            "phi_r": contract.phi_r,
        }
        atomic_create_json(
            root
            / "protocol"
            / "adapters"
            / "prefergrow"
            / dataset
            / "PASS.json",
            _adapter_marker("prefergrow", manifest_sha256, dataset_audit),
        )
    sasrec_audit = audit_e5_root(Path(inputs.e5_root))
    atomic_create_json(
        root / "protocol" / "adapters" / "sasrec" / "e5_reuse_audit.json",
        sasrec_audit,
    )
    atomic_create_json(
        root / "protocol" / "adapters" / "sasrec" / "PASS.json",
        _adapter_marker("sasrec", manifest_sha256, sasrec_audit),
    )
    meta = {
        "schema_version": 1,
        "status": "prepared",
        "queue_root": str(root),
        "queue_manifest_path": f"queue/{QUEUE_NAME}",
        "queue_manifest_sha256": manifest_sha256,
        "source_manifest_path": str(source_manifest_path),
        "source_manifest_sha256": inputs.source_manifest_sha256,
        "ledger_sha256": inputs.ledger_sha256,
        "upstream_manifest_sha256": upstream.manifest_sha256,
        "training_started": False,
        "backup_performed": False,
    }
    atomic_create_json(root / "queue" / "queue_manifest_meta.json", meta)
    return meta


def _load_prepared(root: Path) -> PreparedQueue:
    root = Path(root).resolve(strict=True)
    manifest_path = root / "queue" / QUEUE_NAME
    meta = load_json(root / "queue" / "queue_manifest_meta.json")
    if meta.get("queue_manifest_sha256") != sha256_file(manifest_path):
        raise ContinuationCliError("prepared queue manifest SHA-256 mismatch")
    manifest = QueueManifest.from_dict(load_json(manifest_path))
    validate_manifest(manifest)
    if Path(manifest.run_root).resolve(strict=False) != root:
        raise ContinuationCliError("prepared manifest run_root mismatch")
    upstream = _parse_upstream(load_json(root / "protocol" / "upstream_binding.json"))
    maintenance = _parse_maintenance(load_json(root / "protocol" / "maintenance_window.json"))
    protocol = load_json(root / "protocol" / "prepare_protocol.json")
    source_manifest_path = Path(str(protocol["source_manifest_path"])).resolve(strict=True)
    if sha256_file(source_manifest_path) != manifest.source_manifest_sha256:
        raise ContinuationCliError("prepared source manifest SHA-256 mismatch")
    sasrec_marker = load_json(
        root / "protocol" / "adapters" / "sasrec" / "PASS.json"
    )
    if (
        sasrec_marker.get("status") != "pass"
        or sasrec_marker.get("adapter") != "sasrec"
        or sasrec_marker.get("queue_manifest_sha256") != sha256_file(manifest_path)
    ):
        raise ContinuationCliError("invalid prepared adapter marker: sasrec")
    inputs = _parse_inputs(protocol["inputs"])
    for dataset, contract in inputs.datasets.items():
        marker_path = (
            root
            / "protocol"
            / "adapters"
            / "prefergrow"
            / dataset
            / "PASS.json"
        )
        if not contract.adapter_authorized:
            if marker_path.exists():
                raise ContinuationCliError(
                    f"unauthorized PreferGrow dataset has a marker: {dataset}"
                )
            continue
        marker = load_json(marker_path)
        if (
            marker.get("status") != "pass"
            or marker.get("adapter") != "prefergrow"
            or marker.get("queue_manifest_sha256") != sha256_file(manifest_path)
        ):
            raise ContinuationCliError(
                f"invalid prepared PreferGrow marker: {dataset}"
            )
    return PreparedQueue(root, manifest_path, manifest, upstream, maintenance)


def validate_queue(root: Path) -> dict[str, Any]:
    prepared = _load_prepared(root)
    upstream = verify_r7_upstream(prepared.upstream)
    return {
        "schema_version": 1,
        "status": "valid",
        "queue_root": str(prepared.root),
        "queue_manifest_sha256": sha256_file(prepared.manifest_path),
        "upstream_state": upstream.state,
        "risk08_exit": upstream.exit_value,
    }


def _controller(
    prepared: PreparedQueue,
    *,
    now: Callable[[], datetime] = lambda: datetime.now().astimezone(),
) -> ContinuationController:
    return ContinuationController(
        queue_root=prepared.root,
        manifest=prepared.manifest,
        upstream_binding=prepared.upstream,
        maintenance=prepared.maintenance,
        now=now,
        free_disk_gib=lambda: shutil.disk_usage(prepared.root).free / (1024**3),
        live_process=linux_process_matches,
    )


def status_queue(
    root: Path,
    *,
    now: Callable[[], datetime] = lambda: datetime.now().astimezone(),
) -> dict[str, object]:
    prepared = _load_prepared(root)
    return _controller(prepared, now=now).status()


def internal_method_gate(root: Path) -> dict[str, Any]:
    prepared = _load_prepared(root)
    snapshot = verify_r7_upstream(prepared.upstream)
    if not snapshot.authorized:
        raise ContinuationCliError(
            f"method gate is not authorized: state={snapshot.state} exit={snapshot.exit_value}"
        )
    payload = {
        "schema_version": 1,
        "status": "pass",
        "task_id": "continuation.method_pass_gate",
        "risk08_exit": snapshot.exit_value,
        "upstream_manifest_sha256": snapshot.manifest_sha256,
        "continuation_manifest_sha256": sha256_file(prepared.manifest_path),
    }
    atomic_create_json(prepared.root / "state" / "method_pass_gate.json", payload)
    return payload


def run_queue(root: Path, *, once: bool, poll_seconds: float) -> dict[str, Any]:
    prepared = _load_prepared(root)
    lock_backend = LinuxFlockBackend()
    lock = lock_backend.try_acquire(prepared.root / "state" / "controller.lock")
    if lock is None:
        raise ContinuationCliError("continuation controller lock is already held")
    state_path = prepared.root / "state" / "controller.json"
    try:
        try:
            token = linux_process_start_token(os.getpid())
        except (OSError, RuntimeError, ValueError):
            token = f"unverified:{os.getpid()}"
        atomic_write_json(
            state_path,
            {
                "status": "running",
                "pid": os.getpid(),
                "process_start_time": token,
                "queue_root": str(prepared.root),
                "queue_manifest_sha256": sha256_file(prepared.manifest_path),
            },
        )
        runtime = QueueRuntime(
            queue_root=prepared.root,
            supervisor=ProcessSupervisor(),
            lock_backend=lock_backend,
        )
        controller = _controller(prepared)
        ticks = 0
        while True:
            controller.tick(runtime)
            ticks += 1
            status = controller.status()
            if once or status["gate"] in {"audit_only", "submission_stop"}:
                return {"status": "waiting" if not once else "once", "ticks": ticks, "snapshot": status}
            time.sleep(poll_seconds)
    finally:
        try:
            atomic_write_json(
                state_path,
                {
                    "status": "stopped",
                    "pid": os.getpid(),
                    "queue_root": str(prepared.root),
                    "queue_manifest_sha256": sha256_file(prepared.manifest_path),
                },
            )
        finally:
            lock.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the maintenance-aware r7 method-pass continuation queue"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--protocol", type=Path, required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--queue-root", type=Path, required=True)
    status = commands.add_parser("status")
    status.add_argument("--queue-root", type=Path, required=True)
    run = commands.add_parser("run")
    run.add_argument("--queue-root", type=Path, required=True)
    run.add_argument("--once", action="store_true")
    run.add_argument("--poll-seconds", type=float, default=10.0)
    gate = commands.add_parser("internal-method-gate")
    gate.add_argument("--queue-root", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "prepare":
            payload = prepare_queue(args.protocol)
        elif args.command == "validate":
            payload = validate_queue(args.queue_root)
        elif args.command == "status":
            payload = status_queue(args.queue_root)
        elif args.command == "internal-method-gate":
            payload = internal_method_gate(args.queue_root)
        else:
            payload = run_queue(
                args.queue_root,
                once=bool(args.once),
                poll_seconds=float(args.poll_seconds),
            )
    except (ContinuationCliError, FileExistsError, OSError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "error", "reason": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
