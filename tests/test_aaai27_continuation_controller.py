from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.aaai27_continuation.controller import (
    ContinuationController,
    MaintenanceWindow,
)
from scripts.aaai27_continuation.manifest import build_continuation_manifest
from scripts.aaai27_queue.models import QueueManifest
from scripts.aaai27_queue.runtime import FinishedChild, StartedChild
from tests.test_aaai27_continuation_manifest import _inputs
from tests.test_aaai27_continuation_upstream import _build_r7_fixture


UTC8 = timezone(timedelta(hours=8))


class FakeRuntime:
    def __init__(self) -> None:
        self.finished: list[FinishedChild] = []
        self.started: list[str] = []
        self._pid = 1000

    def observe_finished(self) -> list[FinishedChild]:
        result, self.finished = self.finished, []
        return result

    def start_task(self, task, allowed_gpu_ids):
        self._pid += 1
        self.started.append(task.task_id)
        gpu_id = None if task.gpu_slots == 0 else allowed_gpu_ids[0]
        return StartedChild(task.task_id, self._pid, str(self._pid), gpu_id)


def _controller(
    tmp_path: Path,
    *,
    exit_value: str | None,
    passed: int,
    now: datetime | None = None,
) -> ContinuationController:
    binding = _build_r7_fixture(
        tmp_path / "upstream",
        exit_value=exit_value,
        passed=passed,
    )
    root = tmp_path / "continuation"
    root.mkdir(parents=True)
    manifest = QueueManifest.from_dict(build_continuation_manifest(_inputs()))
    maintenance = MaintenanceWindow(
        planned_shutdown=datetime(2026, 7, 17, 0, 0, tzinfo=UTC8),
        launch_cutoff=datetime(2026, 7, 16, 12, 0, tzinfo=UTC8),
        buffer_hours=3.0,
    )
    return ContinuationController(
        queue_root=root,
        manifest=manifest,
        upstream_binding=binding,
        maintenance=maintenance,
        now=lambda: now or datetime(2026, 7, 15, 12, 0, tzinfo=UTC8),
        free_disk_gib=lambda: 67.0,
        live_process=lambda pid, token: True,
    )


def _write_prefergrow_marker(root: Path) -> None:
    marker = root / "protocol" / "adapters" / "prefergrow" / "PASS.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({"status": "pass"}) + "\n", encoding="utf-8")


def test_waiting_r7_starts_zero_tasks(tmp_path: Path) -> None:
    controller = _controller(tmp_path, exit_value=None, passed=8)
    runtime = FakeRuntime()
    controller.tick(runtime)
    assert runtime.started == []
    status = controller.status()
    assert status["gate"] == "waiting_r7"
    assert status["counts"]["blocked_upstream"] == 37


def test_method_pass_starts_only_contract_gate_first(tmp_path: Path) -> None:
    controller = _controller(tmp_path, exit_value="risk_gated_method", passed=14)
    _write_prefergrow_marker(controller.queue_root)
    runtime = FakeRuntime()
    controller.tick(runtime)
    assert runtime.started == ["continuation.method_pass_gate"]
    record = controller.load_records()["continuation.method_pass_gate"]
    assert record.status == "running"
    assert record.gpu_id is None


def test_preserve_only_exit_starts_zero_tasks(tmp_path: Path) -> None:
    controller = _controller(tmp_path, exit_value="submission_stop", passed=14)
    runtime = FakeRuntime()
    controller.tick(runtime)
    assert runtime.started == []
    assert controller.status()["gate"] == "submission_stop"


def test_after_gate_pass_status_separates_adapter_and_maintenance_blocks(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 7, 16, 12, 0, tzinfo=UTC8)
    controller = _controller(
        tmp_path,
        exit_value="risk_gated_method",
        passed=14,
        now=now,
    )
    _write_prefergrow_marker(controller.queue_root)
    runtime = FakeRuntime()
    controller.tick(runtime)
    runtime.finished.append(
        FinishedChild(
            task_id="continuation.method_pass_gate",
            exit_code=0,
            gpu_seconds=1.0,
            artifacts_valid=True,
            reason=None,
        )
    )
    controller.tick(runtime)
    status = controller.status()
    assert status["counts"]["blocked_adapter"] >= 1
    assert status["counts"]["blocked_maintenance"] >= 1
    assert "continuation.RISK-13.ML1M.host.seed100" not in runtime.started
