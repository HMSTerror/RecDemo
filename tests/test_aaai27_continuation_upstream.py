from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.aaai27_continuation.upstream import (
    UpstreamBinding,
    UpstreamEvidenceError,
    verify_r7_upstream,
)
from scripts.aaai27_queue.models import QueueManifest
from scripts.aaai27_queue.validation import validate_manifest
from tests.aaai27_queue_testdata import make_manifest, valid_pilots


FROZEN_MANIFEST_SHA256 = "387636c8c5dc5b09bb9c509db26b0f335ecac3ed1525e3c4bee3289612bb966e"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _record_path(root: Path, task_id: str) -> Path:
    name = hashlib.sha256(task_id.encode("utf-8")).hexdigest() + ".json"
    return root / "state" / "tasks" / name


def _build_r7_fixture(
    tmp_path: Path,
    *,
    exit_value: str | None,
    passed: int,
    running: int = 0,
) -> UpstreamBinding:
    root = tmp_path / "r7"
    manifest_path = root / "queue" / "queue_seed100.json"
    manifest_run_root = root.as_posix()
    if len(manifest_run_root) >= 2 and manifest_run_root[1] == ":":
        manifest_run_root = manifest_run_root[2:]
    manifest_raw = make_manifest(valid_pilots(), run_root=manifest_run_root)
    manifest = QueueManifest.from_dict(manifest_raw)
    validate_manifest(manifest)
    _write_json(manifest_path, manifest.to_dict())

    config_path = root / "protocol" / "r7_finalizer_config.json"
    _write_json(config_path, {"schema_version": 1, "queue_manifest_sha256": _sha256(manifest_path)})

    active = [task for task in manifest.tasks if task.branch == "e1_pass"]
    assert len(active) == 14
    for task in active[:passed]:
        _write_json(
            _record_path(root, task.task_id),
            {
                "task_id": task.task_id,
                "status": "passed",
                "attempt": 1,
                "pid": 123,
                "process_start_time": "100",
                "gpu_id": 0,
                "started_at": "2026-07-12T00:00:00+00:00",
                "ended_at": "2026-07-12T01:00:00+00:00",
                "exit_code": 0,
                "gpu_seconds": 3600.0,
                "reason": None,
            },
        )
    for task in active[passed : passed + running]:
        _write_json(
            _record_path(root, task.task_id),
            {
                "task_id": task.task_id,
                "status": "running",
                "attempt": 1,
                "pid": 456,
                "process_start_time": "200",
                "gpu_id": 1,
                "started_at": "2026-07-12T01:00:00+00:00",
                "ended_at": None,
                "exit_code": None,
                "gpu_seconds": 0.0,
                "reason": None,
            },
        )

    manifest_sha256 = _sha256(manifest_path)
    if exit_value is not None:
        marker = {
            "schema_version": 1,
            "exit": exit_value,
            "no_rescue": True,
            "queue_manifest_sha256": manifest_sha256,
        }
        _write_json(root / "markers" / "RISK-08_EXIT.json", marker)
        _write_json(
            root / "state" / "TERMINAL.json",
            {
                "schema_version": 1,
                "status": "terminal",
                "outcome": "risk08_exit",
                "risk08_exit": exit_value,
                "no_rescue": True,
                "risk08_marker": marker,
            },
        )

    return UpstreamBinding(
        queue_root=root,
        manifest_path=manifest_path,
        manifest_sha256=manifest_sha256,
        finalizer_config_path=config_path,
        finalizer_config_sha256=_sha256(config_path),
        expected_active_tasks=14,
    )


def test_waiting_r7_is_not_authorized(tmp_path: Path) -> None:
    binding = _build_r7_fixture(tmp_path, exit_value=None, passed=8)
    snapshot = verify_r7_upstream(binding)
    assert snapshot.state == "waiting"
    assert snapshot.authorized is False
    assert snapshot.preserve_only is False
    assert snapshot.exit_value is None
    assert snapshot.completed_task_count == 8


def test_risk_gated_method_with_fourteen_passes_unlocks(tmp_path: Path) -> None:
    binding = _build_r7_fixture(tmp_path, exit_value="risk_gated_method", passed=14)
    snapshot = verify_r7_upstream(binding)
    assert snapshot.state == "terminal"
    assert snapshot.authorized is True
    assert snapshot.preserve_only is False
    assert snapshot.exit_value == "risk_gated_method"
    assert snapshot.completed_task_count == 14


@pytest.mark.parametrize("exit_value", ["audit_only", "submission_stop"])
def test_preserve_only_exits_never_unlock(tmp_path: Path, exit_value: str) -> None:
    binding = _build_r7_fixture(tmp_path, exit_value=exit_value, passed=14)
    snapshot = verify_r7_upstream(binding)
    assert snapshot.authorized is False
    assert snapshot.preserve_only is True
    assert snapshot.exit_value == exit_value


def test_manifest_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    binding = _build_r7_fixture(tmp_path, exit_value="risk_gated_method", passed=14)
    bad = UpstreamBinding(
        queue_root=binding.queue_root,
        manifest_path=binding.manifest_path,
        manifest_sha256="0" * 64,
        finalizer_config_path=binding.finalizer_config_path,
        finalizer_config_sha256=binding.finalizer_config_sha256,
        expected_active_tasks=14,
    )
    with pytest.raises(UpstreamEvidenceError, match="manifest SHA-256 mismatch"):
        verify_r7_upstream(bad)


def test_terminal_requires_marker_and_fourteen_passes(tmp_path: Path) -> None:
    binding = _build_r7_fixture(tmp_path, exit_value="risk_gated_method", passed=13)
    with pytest.raises(UpstreamEvidenceError, match="14/14"):
        verify_r7_upstream(binding)


def test_interrupted_record_fails_closed_while_waiting(tmp_path: Path) -> None:
    binding = _build_r7_fixture(tmp_path, exit_value=None, passed=8, running=1)
    record_path = next((binding.queue_root / "state" / "tasks").glob("*.json"))
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["status"] = "interrupted_unverified"
    _write_json(record_path, record)
    with pytest.raises(UpstreamEvidenceError, match="interrupted_unverified"):
        verify_r7_upstream(binding)
