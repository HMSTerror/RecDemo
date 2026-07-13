from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.aaai27_continuation.policy import EligibilityContext, classify_task
from scripts.aaai27_queue.models import TaskSpec
from tests.aaai27_queue_testdata import make_task


UTC8 = timezone(timedelta(hours=8))


def _task(**overrides: object) -> TaskSpec:
    payload: dict[str, object] = {
        "task_id": "continuation.r13.ML1M.host",
        "ledger_id": "RISK-13",
        "phase": "continuation",
        "branch": "method_pass",
        "dependencies": ["continuation.method_pass_gate"],
        "required_markers": ["protocol/adapters/prefergrow/PASS.json"],
    }
    payload.update(overrides)
    raw = make_task(**payload)
    return TaskSpec.from_dict(raw)


def _context(root: Path, **overrides: object) -> EligibilityContext:
    payload: dict[str, object] = {
        "now": datetime(2026, 7, 15, 12, 0, tzinfo=UTC8),
        "planned_shutdown": datetime(2026, 7, 17, 0, 0, tzinfo=UTC8),
        "maintenance_buffer_hours": 3.0,
        "queue_root": root,
        "free_disk_gib": 67.0,
        "actual_gpu_hours": 3.5,
        "gpu_budget_hours": 168.0,
        "passed_task_ids": frozenset({"continuation.method_pass_gate"}),
    }
    payload.update(overrides)
    return EligibilityContext(**payload)


def _write_adapter_marker(root: Path, model: str = "prefergrow") -> None:
    path = root / "protocol" / "adapters" / model / "PASS.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"schema_version": 1, "status": "pass"}) + "\n",
        encoding="utf-8",
    )


def test_task_that_would_cross_shutdown_is_blocked_maintenance(tmp_path: Path) -> None:
    _write_adapter_marker(tmp_path)
    task = _task(gpu_hours_high=26.0)
    context = _context(
        tmp_path,
        now=datetime(2026, 7, 16, 0, 0, tzinfo=UTC8),
        planned_shutdown=datetime(2026, 7, 16, 16, 0, tzinfo=UTC8),
    )
    decision = classify_task(task, context)
    assert decision.ready is False
    assert decision.status == "blocked_maintenance"


def test_missing_adapter_marker_is_blocked_adapter(tmp_path: Path) -> None:
    decision = classify_task(_task(), _context(tmp_path))
    assert decision.ready is False
    assert decision.status == "blocked_adapter"
    assert "prefergrow/PASS.json" in str(decision.reason)


def test_short_task_before_latest_safe_start_is_ready(tmp_path: Path) -> None:
    _write_adapter_marker(tmp_path)
    decision = classify_task(_task(gpu_hours_high=1.0), _context(tmp_path))
    assert decision.ready is True
    assert decision.status == "ready"
    assert decision.reason is None


def test_dependency_disk_and_budget_blocks_are_distinct(tmp_path: Path) -> None:
    _write_adapter_marker(tmp_path)
    dependency = classify_task(
        _task(),
        _context(tmp_path, passed_task_ids=frozenset()),
    )
    disk = classify_task(_task(), _context(tmp_path, free_disk_gib=39.9))
    budget = classify_task(
        _task(gpu_hours_high=2.0),
        _context(tmp_path, actual_gpu_hours=167.0),
    )
    assert dependency.status == "blocked_dependency"
    assert disk.status == "blocked_disk"
    assert budget.status == "blocked_budget"


def test_exact_latest_safe_boundary_is_allowed(tmp_path: Path) -> None:
    _write_adapter_marker(tmp_path)
    shutdown = datetime(2026, 7, 17, 0, 0, tzinfo=UTC8)
    context = _context(
        tmp_path,
        now=shutdown - timedelta(hours=4),
        planned_shutdown=shutdown,
        maintenance_buffer_hours=3.0,
    )
    assert classify_task(_task(gpu_hours_high=1.0), context).status == "ready"
    late = _context(
        tmp_path,
        now=shutdown - timedelta(hours=4) + timedelta(seconds=1),
        planned_shutdown=shutdown,
        maintenance_buffer_hours=3.0,
    )
    assert classify_task(_task(gpu_hours_high=1.0), late).status == "blocked_maintenance"


def test_unsafe_marker_path_and_naive_time_fail_closed(tmp_path: Path) -> None:
    unsafe = _task(required_markers=["../PASS.json"])
    with pytest.raises(ValueError, match="unsafe required marker"):
        classify_task(unsafe, _context(tmp_path))
    naive = _context(tmp_path, now=datetime(2026, 7, 15, 12, 0))
    with pytest.raises(ValueError, match="timezone-aware"):
        classify_task(_task(), naive)
