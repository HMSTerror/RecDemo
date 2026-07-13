# r7 Method-Pass Continuation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, validate, and deploy a separate seed-100 continuation queue that consumes the immutable r7 RISK-08 exit, starts Stage D only for `risk_gated_method`, and blocks tasks that cannot safely finish before the 2026-07-17 maintenance shutdown.

**Architecture:** Import the tested r7 queue core from the immutable server bundle into an isolated Git worktree, then add three focused units: an upstream-evidence verifier, a maintenance/adapter eligibility policy, and a continuation-specific controller/manifest builder. The continuation queue remains separate from r7, uses required-marker gates for adapters, reuses E5 SASRec only after identity validation, and records maintenance-blocked tasks without creating scientific failures.

**Tech Stack:** Python 3.10+, `dataclasses`, `pathlib`, `json`, `hashlib`, `subprocess`, `fcntl` on Linux, `pytest`, Hydra argv arrays for PreferGrow, tmux for detached deployment, SHA-256 provenance.

---

## Scope decomposition

This plan delivers the control plane and every Stage D queue slot. It makes RISK-13 and RISK-14 production-ready from the PreferGrow runner, validates E5 SASRec reuse, and represents Caser, GRURec, and DiffRec as real manifest tasks guarded by production-adapter markers. It does not fabricate those three model implementations. Their separate adapter work may proceed while r7 is running; until a dated adapter marker exists, the controller reports `blocked_adapter` and launches zero tasks for that model.

## File map

### Provenance-imported queue core

- Create: `scripts/aaai27_queue/__init__.py`
- Create: `scripts/aaai27_queue/models.py`
- Create: `scripts/aaai27_queue/storage.py`
- Create: `scripts/aaai27_queue/scheduler.py`
- Create: `scripts/aaai27_queue/validation.py`
- Create: `scripts/aaai27_queue/runtime.py`
- Create: `scripts/aaai27_queue/controller.py`
- Create: `tests/aaai27_queue_testdata.py`
- Create: `tests/test_aaai27_queue_models.py`
- Create: `tests/test_aaai27_queue_storage.py`
- Create: `tests/test_aaai27_queue_scheduler.py`
- Create: `tests/test_aaai27_queue_validation.py`
- Create: `tests/test_aaai27_queue_runtime.py`
- Create: `tests/test_aaai27_queue_controller.py`
- Create: `scripts/aaai27_adapters/__init__.py`
- Create: `scripts/aaai27_adapters/common.py`
- Create: `scripts/aaai27_adapters/pilot_adapters.py`
- Create: `scripts/run_aaai27_pilot_task.py`
- Create: `tests/test_aaai27_pilot_task_wrapper.py`

These files are copied byte-for-byte from `/data/Zijian/goal/RecDemo_aaai27_risk0607_987eb19_r7`, verified by SHA-256, and committed before new behavior is added.

### New continuation units

- Create: `scripts/aaai27_continuation/upstream.py` — validate r7 terminal, exit marker, active task records, and frozen hashes.
- Create: `scripts/aaai27_continuation/policy.py` — classify adapter, maintenance, disk, budget, dependency, and gate blocks.
- Create: `scripts/aaai27_continuation/controller.py` — marker-aware continuation scheduling and status projection.
- Create: `scripts/aaai27_continuation/manifest.py` — build the frozen Stage D seed-100 manifest.
- Create: `scripts/aaai27_continuation/adapters.py` — build production PreferGrow argv and E5 SASRec reuse-audit argv.
- Create: `scripts/aaai27_continuation/__init__.py` — package exports.
- Create: `scripts/aaai27_method_pass_continuation.py` — CLI for prepare, validate, status, once, and resident run.
- Create: `scripts/audit_e05_sasrec_reuse.py` — validate the completed four-domain E5 group before zero-GPU reuse.
- Create: `tests/test_aaai27_continuation_upstream.py`
- Create: `tests/test_aaai27_continuation_policy.py`
- Create: `tests/test_aaai27_continuation_controller.py`
- Create: `tests/test_aaai27_continuation_manifest.py`
- Create: `tests/test_aaai27_continuation_adapters.py`
- Create: `tests/test_aaai27_method_pass_continuation_cli.py`
- Create: `tests/test_audit_e05_sasrec_reuse.py`

### Operations and evidence

- Create: `docs/reports/data/2026-07-13-method-pass-continuation/OPERATIONS_RUNBOOK.md`
- Create: `docs/reports/data/2026-07-13-method-pass-continuation/LOCAL_TEST_REPORT.md`
- Modify: `issues/2026-07-10_21-18-20-aaai27-evidence-risk-rescue.csv`

## Task 1: Create an isolated worktree and import the trusted queue core

**Files:** all provenance-imported files listed above.

- [ ] **Step 1: Read and follow the worktree safety instructions**

Run:

```powershell
Get-Content -Raw C:\Users\14466\.codex\skills\using-git-worktrees\SKILL.md
```

Expected: instructions require an isolated worktree and baseline verification.

- [ ] **Step 2: Create the clean branch from the approved spec commit**

Run:

```powershell
git worktree add E:\PreferGrow-r7-continuation -b codex/r7-method-pass-continuation 110e5af
```

Expected: a clean worktree on `codex/r7-method-pass-continuation`; the dirty main worktree remains untouched.

- [ ] **Step 3: Export the exact r7 queue core into a temporary provenance directory**

Run from `E:\PreferGrow-r7-continuation`:

```powershell
New-Item -ItemType Directory -Force .provenance\r7-core | Out-Null
scp -r zijian@172.18.0.40:/data/Zijian/goal/RecDemo_aaai27_risk0607_987eb19_r7/scripts/aaai27_queue .provenance/r7-core/
scp zijian@172.18.0.40:/data/Zijian/goal/RecDemo_aaai27_risk0607_987eb19_r7/tests/aaai27_queue_testdata.py .provenance/r7-core/
scp zijian@172.18.0.40:/data/Zijian/goal/RecDemo_aaai27_risk0607_987eb19_r7/tests/test_aaai27_queue_models.py .provenance/r7-core/
scp zijian@172.18.0.40:/data/Zijian/goal/RecDemo_aaai27_risk0607_987eb19_r7/tests/test_aaai27_queue_storage.py .provenance/r7-core/
scp zijian@172.18.0.40:/data/Zijian/goal/RecDemo_aaai27_risk0607_987eb19_r7/tests/test_aaai27_queue_scheduler.py .provenance/r7-core/
scp zijian@172.18.0.40:/data/Zijian/goal/RecDemo_aaai27_risk0607_987eb19_r7/tests/test_aaai27_queue_validation.py .provenance/r7-core/
scp zijian@172.18.0.40:/data/Zijian/goal/RecDemo_aaai27_risk0607_987eb19_r7/tests/test_aaai27_queue_runtime.py .provenance/r7-core/
scp zijian@172.18.0.40:/data/Zijian/goal/RecDemo_aaai27_risk0607_987eb19_r7/tests/test_aaai27_queue_controller.py .provenance/r7-core/
scp zijian@172.18.0.40:/data/Zijian/goal/RecDemo_aaai27_risk0607_987eb19_r7/scripts/aaai27_adapters/__init__.py .provenance/r7-core/aaai27_adapters_init.py
scp zijian@172.18.0.40:/data/Zijian/goal/RecDemo_aaai27_risk0607_987eb19_r7/scripts/aaai27_adapters/common.py .provenance/r7-core/adapter_common.py
scp zijian@172.18.0.40:/data/Zijian/goal/RecDemo_aaai27_risk0607_987eb19_r7/scripts/aaai27_adapters/pilot_adapters.py .provenance/r7-core/pilot_adapters.py
scp zijian@172.18.0.40:/data/Zijian/goal/RecDemo_aaai27_risk0607_987eb19_r7/scripts/run_aaai27_pilot_task.py .provenance/r7-core/
scp zijian@172.18.0.40:/data/Zijian/goal/RecDemo_aaai27_risk0607_987eb19_r7/tests/test_aaai27_pilot_task_wrapper.py .provenance/r7-core/
```

Expected: only queue core and its tests are retrieved; no checkpoint, dataset, log, or backup is copied.

- [ ] **Step 4: Record and compare remote/local SHA-256**

Run:

```powershell
ssh zijian@172.18.0.40 "cd /data/Zijian/goal/RecDemo_aaai27_risk0607_987eb19_r7 && find scripts/aaai27_queue tests -maxdepth 2 -type f | grep -E 'scripts/aaai27_queue/.*\.py$|tests/(aaai27_queue_testdata|test_aaai27_queue_(models|storage|scheduler|validation|runtime|controller))\.py$' | sort | xargs sha256sum" | Set-Content -Encoding ascii .provenance\r7-core\REMOTE_SHA256SUMS.txt
ssh zijian@172.18.0.40 "cd /data/Zijian/goal/RecDemo_aaai27_risk0607_987eb19_r7 && sha256sum scripts/aaai27_adapters/__init__.py scripts/aaai27_adapters/common.py scripts/aaai27_adapters/pilot_adapters.py scripts/run_aaai27_pilot_task.py tests/test_aaai27_pilot_task_wrapper.py" | Add-Content -Encoding ascii .provenance\r7-core\REMOTE_SHA256SUMS.txt
Get-ChildItem .provenance\r7-core -Recurse -File -Filter *.py | Get-FileHash -Algorithm SHA256 | Sort-Object Path | Format-Table -AutoSize
```

Expected: every imported Python file matches its remote source hash. A mismatch stops the import.

- [ ] **Step 5: Copy the verified source into tracked paths without modifying content**

Run:

```powershell
Copy-Item -Recurse -Force .provenance\r7-core\aaai27_queue scripts\aaai27_queue
Copy-Item -Force .provenance\r7-core\aaai27_queue_testdata.py tests\aaai27_queue_testdata.py
Copy-Item -Force .provenance\r7-core\test_aaai27_queue_*.py tests\
New-Item -ItemType Directory -Force scripts\aaai27_adapters | Out-Null
Copy-Item -Force .provenance\r7-core\aaai27_adapters_init.py scripts\aaai27_adapters\__init__.py
Copy-Item -Force .provenance\r7-core\adapter_common.py scripts\aaai27_adapters\common.py
Copy-Item -Force .provenance\r7-core\pilot_adapters.py scripts\aaai27_adapters\pilot_adapters.py
Copy-Item -Force .provenance\r7-core\run_aaai27_pilot_task.py scripts\run_aaai27_pilot_task.py
Copy-Item -Force .provenance\r7-core\test_aaai27_pilot_task_wrapper.py tests\test_aaai27_pilot_task_wrapper.py
```

Expected: tracked paths contain byte-identical imported source. This is a provenance import, not a behavioral edit.

- [ ] **Step 6: Run the imported baseline tests**

Run:

```powershell
python -m pytest tests/test_aaai27_queue_models.py tests/test_aaai27_queue_storage.py tests/test_aaai27_queue_scheduler.py tests/test_aaai27_queue_validation.py tests/test_aaai27_queue_runtime.py tests/test_aaai27_queue_controller.py tests/test_aaai27_pilot_task_wrapper.py -q
```

Expected: all imported queue-core tests pass before any continuation code exists.

- [ ] **Step 7: Commit the provenance import**

Run:

```powershell
git add scripts/aaai27_queue scripts/aaai27_adapters/__init__.py scripts/aaai27_adapters/common.py scripts/aaai27_adapters/pilot_adapters.py scripts/run_aaai27_pilot_task.py tests/aaai27_queue_testdata.py tests/test_aaai27_queue_*.py tests/test_aaai27_pilot_task_wrapper.py
git commit -m "chore: import verified r7 queue core"
```

Expected: one isolated commit containing only the verified queue core and tests.

## Task 2: Verify immutable r7 upstream evidence

**Files:**

- Create: `scripts/aaai27_continuation/__init__.py`
- Create: `scripts/aaai27_continuation/upstream.py`
- Create: `tests/test_aaai27_continuation_upstream.py`

- [ ] **Step 1: Write failing tests for the only valid unlock**

Create tests that call the wished-for API:

```python
from pathlib import Path

import pytest

from scripts.aaai27_continuation.upstream import (
    UpstreamBinding,
    UpstreamEvidenceError,
    verify_r7_upstream,
)


def test_risk_gated_method_with_14_passed_tasks_unlocks(tmp_path: Path) -> None:
    binding = build_r7_fixture(tmp_path, exit_value="risk_gated_method", passed=14)
    snapshot = verify_r7_upstream(binding)
    assert snapshot.authorized is True
    assert snapshot.exit_value == "risk_gated_method"
    assert snapshot.completed_task_count == 14


def test_missing_terminal_and_marker_is_a_valid_waiting_state(tmp_path: Path) -> None:
    binding = build_r7_fixture(tmp_path, exit_value=None, passed=8, running=0)
    snapshot = verify_r7_upstream(binding)
    assert snapshot.state == "waiting"
    assert snapshot.authorized is False
    assert snapshot.exit_value is None


@pytest.mark.parametrize("exit_value", ["audit_only", "submission_stop"])
def test_preserve_only_exits_never_unlock(tmp_path: Path, exit_value: str) -> None:
    binding = build_r7_fixture(tmp_path, exit_value=exit_value, passed=14)
    snapshot = verify_r7_upstream(binding)
    assert snapshot.authorized is False
    assert snapshot.preserve_only is True


def test_manifest_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    binding = build_r7_fixture(tmp_path, exit_value="risk_gated_method", passed=14)
    binding = UpstreamBinding(**{**binding.__dict__, "manifest_sha256": "0" * 64})
    with pytest.raises(UpstreamEvidenceError, match="manifest SHA-256 mismatch"):
        verify_r7_upstream(binding)
```

Fixture helper `build_r7_fixture` must create a real manifest file, finalizer config, `state/TERMINAL.json`, `markers/RISK-08_EXIT.json`, and 14 hashed task-record JSON files. It must not mock `sha256_file`.

- [ ] **Step 2: Run the tests and observe RED**

Run:

```powershell
python -m pytest tests/test_aaai27_continuation_upstream.py -q
```

Expected: collection fails because `scripts.aaai27_continuation.upstream` does not exist.

- [ ] **Step 3: Implement the minimal immutable verifier**

Create the public types and verifier:

```python
@dataclass(frozen=True)
class UpstreamBinding:
    queue_root: Path
    manifest_path: Path
    manifest_sha256: str
    finalizer_config_path: Path
    finalizer_config_sha256: str
    expected_active_tasks: int = 14


@dataclass(frozen=True)
class UpstreamSnapshot:
    state: str
    authorized: bool
    preserve_only: bool
    exit_value: str | None
    completed_task_count: int
    manifest_sha256: str
    finalizer_config_sha256: str


class UpstreamEvidenceError(RuntimeError):
    pass


def verify_r7_upstream(binding: UpstreamBinding) -> UpstreamSnapshot:
    root = binding.queue_root.resolve(strict=True)
    manifest = binding.manifest_path.resolve(strict=True)
    config = binding.finalizer_config_path.resolve(strict=True)
    require_within(manifest, root)
    require_within(config, root)
    require_hash(manifest, binding.manifest_sha256, "manifest")
    require_hash(config, binding.finalizer_config_sha256, "finalizer config")
    passed = load_active_passed_records(root, manifest)
    terminal_path = root / "state" / "TERMINAL.json"
    marker_path = root / "markers" / "RISK-08_EXIT.json"
    if not terminal_path.exists() and not marker_path.exists():
        return UpstreamSnapshot(
            state="waiting",
            authorized=False,
            preserve_only=False,
            exit_value=None,
            completed_task_count=len(passed),
            manifest_sha256=binding.manifest_sha256,
            finalizer_config_sha256=binding.finalizer_config_sha256,
        )
    if terminal_path.exists() != marker_path.exists():
        raise UpstreamEvidenceError("r7 terminal and RISK-08 marker must appear together")
    terminal = load_json(terminal_path)
    marker = load_json(marker_path)
    validate_terminal_and_marker_identity(terminal, marker, binding.manifest_sha256)
    if len(passed) != binding.expected_active_tasks:
        raise UpstreamEvidenceError("r7 terminal exists without 14/14 passed tasks")
    exit_value = marker.get("exit")
    if exit_value not in {"risk_gated_method", "audit_only", "submission_stop"}:
        raise UpstreamEvidenceError(f"unknown RISK-08 exit: {exit_value!r}")
    return UpstreamSnapshot(
        state="terminal",
        authorized=exit_value == "risk_gated_method",
        preserve_only=exit_value in {"audit_only", "submission_stop"},
        exit_value=exit_value,
        completed_task_count=len(passed),
        manifest_sha256=binding.manifest_sha256,
        finalizer_config_sha256=binding.finalizer_config_sha256,
    )
```

The helper that loads records must reject inactive-branch records, unknown task IDs, `failed`, and `interrupted_unverified` statuses. It returns passed/running counts so the caller can distinguish a valid waiting state from a terminal state.

While both terminal and RISK-08 marker are absent, active `running` records are allowed and reported as `state="waiting"`; `failed` and `interrupted_unverified` records still raise. After either terminal artifact appears, every active record must be `passed` and the count must be exactly 14.

- [ ] **Step 4: Add malformed and contradictory evidence tests**

Add tests for missing terminal, missing marker, unknown exit, terminal/marker exit mismatch, `no_rescue != true`, one running record, one interrupted record, an inactive E1-fail record, and finalizer hash mismatch.

- [ ] **Step 5: Run GREEN and regression tests**

Run:

```powershell
python -m pytest tests/test_aaai27_continuation_upstream.py tests/test_aaai27_queue_storage.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add scripts/aaai27_continuation tests/test_aaai27_continuation_upstream.py
git commit -m "feat: verify immutable r7 continuation gate"
```

## Task 3: Implement maintenance and adapter eligibility policy

**Files:**

- Create: `scripts/aaai27_continuation/policy.py`
- Create: `tests/test_aaai27_continuation_policy.py`

- [ ] **Step 1: Write failing latest-safe-start tests**

```python
from datetime import datetime, timezone
from pathlib import Path

from scripts.aaai27_continuation.policy import EligibilityContext, classify_task


UTC = timezone.utc


def test_task_that_would_cross_shutdown_is_blocked_maintenance(tmp_path: Path) -> None:
    task = make_task(task_id="continuation.r13.ML1M.host", gpu_hours_high=26.0)
    context = EligibilityContext(
        now=datetime(2026, 7, 16, 0, 0, tzinfo=UTC),
        planned_shutdown=datetime(2026, 7, 16, 16, 0, tzinfo=UTC),
        maintenance_buffer_hours=3.0,
        queue_root=tmp_path,
        free_disk_gib=67.0,
        actual_gpu_hours=3.5,
        gpu_budget_hours=168.0,
        passed_task_ids=frozenset({"continuation.method_pass_gate"}),
    )
    decision = classify_task(task, context)
    assert decision.ready is False
    assert decision.status == "blocked_maintenance"


def test_missing_adapter_marker_is_blocked_adapter(tmp_path: Path) -> None:
    task = make_task(required_markers=("protocol/adapters/caser/PASS.json",))
    context = eligible_context(tmp_path)
    decision = classify_task(task, context)
    assert decision.ready is False
    assert decision.status == "blocked_adapter"


def test_short_task_before_latest_safe_start_is_ready(tmp_path: Path) -> None:
    marker = tmp_path / "protocol" / "adapters" / "prefergrow" / "PASS.json"
    marker.parent.mkdir(parents=True)
    marker.write_text('{"status":"pass"}', encoding="utf-8")
    task = make_task(gpu_hours_high=1.0, required_markers=("protocol/adapters/prefergrow/PASS.json",))
    decision = classify_task(task, eligible_context(tmp_path))
    assert decision.ready is True
    assert decision.status == "ready"
```

- [ ] **Step 2: Run RED**

```powershell
python -m pytest tests/test_aaai27_continuation_policy.py -q
```

Expected: import failure because `policy.py` is absent.

- [ ] **Step 3: Implement a pure classification function**

```python
@dataclass(frozen=True)
class EligibilityContext:
    now: datetime
    planned_shutdown: datetime
    maintenance_buffer_hours: float
    queue_root: Path
    free_disk_gib: float
    actual_gpu_hours: float
    gpu_budget_hours: float
    passed_task_ids: frozenset[str]


@dataclass(frozen=True)
class EligibilityDecision:
    ready: bool
    status: str
    reason: str | None


def classify_task(task: TaskSpec, context: EligibilityContext) -> EligibilityDecision:
    if not set(task.dependencies).issubset(context.passed_task_ids):
        return blocked("blocked_dependency", "dependencies are not terminal-pass")
    missing_markers = [
        marker for marker in task.required_markers
        if not safe_marker(context.queue_root, marker).is_file()
    ]
    if missing_markers:
        return blocked("blocked_adapter", f"missing required markers: {missing_markers}")
    if context.free_disk_gib < 40.0:
        return blocked("blocked_disk", "free /data space is below 40 GiB")
    if context.actual_gpu_hours + task.gpu_hours_high > context.gpu_budget_hours:
        return blocked("blocked_budget", "frozen high estimate exceeds queue budget")
    projected_end = context.now + timedelta(
        hours=task.gpu_hours_high + context.maintenance_buffer_hours
    )
    if projected_end > context.planned_shutdown:
        return blocked("blocked_maintenance", "task would cross planned shutdown")
    return EligibilityDecision(True, "ready", None)
```

`safe_marker` must reject absolute paths, `..`, and paths outside the continuation root. Marker content validation belongs to the adapter that produces the marker.

- [ ] **Step 4: Add disk, budget, dependency, path-escape, timezone, and exact-boundary tests**

Exact boundary behavior must be allowed when `projected_end == planned_shutdown` and blocked when it is one second later. Naive datetimes must raise `ValueError`.

- [ ] **Step 5: Run GREEN**

```powershell
python -m pytest tests/test_aaai27_continuation_policy.py -q
```

Expected: all policy tests pass.

- [ ] **Step 6: Commit**

```powershell
git add scripts/aaai27_continuation/policy.py tests/test_aaai27_continuation_policy.py
git commit -m "feat: gate continuation by adapters and maintenance"
```

## Task 4: Build the frozen Stage D manifest

**Files:**

- Create: `scripts/aaai27_continuation/adapters.py`
- Create: `scripts/aaai27_continuation/manifest.py`
- Create: `scripts/audit_e05_sasrec_reuse.py`
- Create: `tests/test_aaai27_continuation_adapters.py`
- Create: `tests/test_aaai27_continuation_manifest.py`
- Create: `tests/test_audit_e05_sasrec_reuse.py`

- [ ] **Step 1: Write failing tests for production argv**

```python
def test_prefergrow_argv_is_shell_free_and_binds_seed_workdir_and_gpu() -> None:
    task = build_prefergrow_task(
        dataset="ML1M",
        arm="host",
        run_dir="/data/Zijian/goal/aaai27_queue/continuation/runs/r13/ML1M/host",
        source_root="/data/Zijian/goal/RecDemo_continuation_source",
        seed=100,
    )
    assert task["argv"][0].endswith("python3")
    assert task["argv"][1].endswith("run_aaai27_pilot_task.py")
    separator = task["argv"].index("--")
    training_argv = task["argv"][separator + 1 :]
    assert training_argv[0].endswith("python3")
    assert training_argv[1].endswith("single_train.py")
    assert "random_seed=100" in training_argv
    assert f"work_dir={task['run_dir']}" in training_argv
    assert "cuda=0" in training_argv
    assert task["max_attempts"] == 1
    assert task["failure_policy"] == "fail_closed"


def test_caser_grurec_diffrec_tasks_require_adapter_markers() -> None:
    manifest = build_continuation_manifest(frozen_inputs())
    for task in manifest["tasks"]:
        if task["model"] in {"Caser", "GRURec", "DiffRec"}:
            assert task["required_markers"] == [
                f"protocol/adapters/{task['model'].casefold()}/PASS.json"
            ]


def test_e5_reuse_audit_requires_all_four_nonempty_artifact_sets(tmp_path: Path) -> None:
    e5_root = build_e5_fixture(tmp_path, datasets=("Steam", "ML1M", "Beauty", "ATG"))
    result = audit_e5_root(e5_root)
    assert result["status"] == "pass"
    assert result["datasets"] == ["ATG", "Beauty", "ML1M", "Steam"]
    assert all(item["stdout_bytes"] > 0 for item in result["artifacts"])


def test_e5_reuse_audit_rejects_a_missing_domain(tmp_path: Path) -> None:
    e5_root = build_e5_fixture(tmp_path, datasets=("Steam", "ML1M", "Beauty"))
    with pytest.raises(E5ReuseError, match="four-domain atomic group"):
        audit_e5_root(e5_root)
```

- [ ] **Step 2: Write failing tests for the exact matrix**

```python
def test_stage_d_manifest_contains_frozen_seed100_matrix() -> None:
    raw = build_continuation_manifest(frozen_inputs())
    manifest = QueueManifest.from_dict(raw)
    validate_manifest(manifest)
    tasks = manifest.tasks
    assert len([t for t in tasks if t.ledger_id == "RISK-13"]) == 8
    assert len([t for t in tasks if t.ledger_id == "RISK-14"]) == 12
    assert len([t for t in tasks if t.ledger_id == "RISK-10"]) == 12
    assert len([t for t in tasks if t.ledger_id == "RISK-11"]) == 4
    assert {t.seed for t in tasks if t.kind == "gpu"} == {100}
    assert all(t.branch == "method_pass" for t in tasks)
```

- [ ] **Step 3: Run RED**

```powershell
python -m pytest tests/test_aaai27_continuation_adapters.py tests/test_aaai27_continuation_manifest.py -q
```

Expected: imports fail because adapters and manifest modules are absent.

- [ ] **Step 4: Implement exact builders**

Implement these public functions:

```python
@dataclass(frozen=True)
class FrozenContinuationInputs:
    queue_root: str
    source_root: str
    python_executable: str
    code_revision: str
    ledger_path: str
    ledger_sha256: str
    source_manifest_sha256: str
    dataset_configs: dict[str, DatasetContract]
    high_risk_condition: RiskCondition
    low_risk_condition: RiskCondition
    e5_root: str
    planned_shutdown: str
    maintenance_buffer_hours: float


def build_prefergrow_task(
    inputs: FrozenContinuationInputs,
    *,
    ledger_id: str,
    task_id: str,
    dataset: str,
    arm: str,
    priority: int,
    gpu_hours_low: float,
    gpu_hours_high: float,
) -> dict[str, object]:
    contract = inputs.dataset_configs[dataset]
    run_rel = task_id.replace("continuation.", "runs/").replace(".", "/")
    run_dir = f"{inputs.queue_root}/{run_rel}"
    graph_type = "adaptive" if arm in {"host", "global_p"} else "proposal_adaptive"
    argv = build_prefergrow_argv(
        python_executable=inputs.python_executable,
        source_root=inputs.source_root,
        dataset=dataset,
        contract=contract,
        arm=arm,
        run_dir=run_dir,
        seed=100,
    )
    return make_task_payload(
        inputs=inputs,
        ledger_id=ledger_id,
        task_id=task_id,
        kind="gpu",
        argv=argv,
        run_dir=run_dir,
        dataset=dataset,
        arm=arm,
        model="PreferGrow",
        required_markers=("protocol/adapters/prefergrow/PASS.json",),
        gpu_hours_low=gpu_hours_low,
        gpu_hours_high=gpu_hours_high,
        priority=priority,
        graph_type=graph_type,
    )


def build_prefergrow_argv(
    *,
    python_executable: str,
    source_root: str,
    dataset: str,
    contract: DatasetContract,
    arm: str,
    run_dir: str,
    seed: int,
) -> list[str]:
    training_argv = build_training_argv_from_pilot_contract(
        python_executable=python_executable,
        single_train=f"{source_root}/single_train.py",
        dataset=dataset,
        contract=contract,
        arm=arm,
        run_dir=run_dir,
        seed=seed,
    )
    return [
        python_executable,
        f"{source_root}/scripts/run_aaai27_pilot_task.py",
        "--",
        *training_argv,
    ]


def build_sasrec_reuse_task(
    inputs: FrozenContinuationInputs,
    *,
    dataset: str,
    priority: int,
) -> dict[str, object]:
    task_id = f"continuation.r10.SASRec.{dataset}.reuse_audit"
    run_rel = task_id.replace("continuation.", "runs/").replace(".", "/")
    run_dir = f"{inputs.queue_root}/{run_rel}"
    argv = [
        inputs.python_executable,
        f"{inputs.source_root}/scripts/audit_e5_sasrec_reuse.py",
        "--e5-root",
        inputs.e5_root,
        "--dataset",
        dataset,
        "--output-dir",
        run_dir,
    ]
    return make_task_payload(
        inputs=inputs,
        ledger_id="RISK-10",
        task_id=task_id,
        kind="contract_gate",
        argv=argv,
        run_dir=run_dir,
        dataset=dataset,
        arm="reuse_audit",
        model="SASRec",
        required_markers=("protocol/adapters/sasrec/PASS.json",),
        gpu_hours_low=0.0,
        gpu_hours_high=0.0,
        priority=priority,
        graph_type=None,
    )


def build_guarded_baseline_task(
    inputs: FrozenContinuationInputs,
    *,
    model: str,
    ledger_id: str,
    dataset: str,
    priority: int,
    gpu_hours_low: float,
    gpu_hours_high: float,
) -> dict[str, object]:
    task_id = f"continuation.{ledger_id.casefold().replace('-', '')}.{model}.{dataset}"
    run_rel = task_id.replace("continuation.", "runs/").replace(".", "/")
    run_dir = f"{inputs.queue_root}/{run_rel}"
    entry = f"{inputs.source_root}/scripts/run_{model.casefold()}_common_protocol.py"
    argv = [
        inputs.python_executable,
        entry,
        "--dataset",
        dataset,
        "--seed",
        "100",
        "--run-dir",
        run_dir,
    ]
    return make_task_payload(
        inputs=inputs,
        ledger_id=ledger_id,
        task_id=task_id,
        kind="gpu",
        argv=argv,
        run_dir=run_dir,
        dataset=dataset,
        arm="baseline",
        model=model,
        required_markers=(f"protocol/adapters/{model.casefold()}/PASS.json",),
        gpu_hours_low=gpu_hours_low,
        gpu_hours_high=gpu_hours_high,
        priority=priority,
        graph_type=None,
    )


def build_continuation_manifest(inputs: FrozenContinuationInputs) -> dict[str, object]:
    tasks = [build_method_pass_gate(inputs)]
    for dataset in ("Steam", "ML1M", "Beauty", "ATG"):
        for arm in ("host", "risk_gated_full"):
            tasks.append(build_risk13_task(inputs, dataset=dataset, arm=arm))
    for rank, condition in (
        ("high_risk", inputs.high_risk_condition),
        ("low_risk", inputs.low_risk_condition),
    ):
        for arm in ("host", "text_anchor_only", "global_p", "dataset_gate_only", "full", "u_shuffle"):
            tasks.append(build_risk14_task(inputs, rank=rank, condition=condition, arm=arm))
    for dataset in ("Steam", "ML1M", "Beauty", "ATG"):
        tasks.append(build_sasrec_reuse_task(inputs, dataset=dataset, priority=30))
        tasks.append(build_guarded_baseline_task(inputs, model="Caser", ledger_id="RISK-10", dataset=dataset, priority=31, gpu_hours_low=1.0, gpu_hours_high=4.0))
        tasks.append(build_guarded_baseline_task(inputs, model="GRURec", ledger_id="RISK-10", dataset=dataset, priority=32, gpu_hours_low=1.0, gpu_hours_high=4.0))
        tasks.append(build_guarded_baseline_task(inputs, model="DiffRec", ledger_id="RISK-11", dataset=dataset, priority=40, gpu_hours_low=3.0, gpu_hours_high=9.0))
    payload = make_manifest_payload(inputs, tasks)
    validate_manifest(QueueManifest.from_dict(payload))
    return payload
```

The builders must emit one method-pass contract gate, eight RISK-13 tasks, twelve RISK-14 tasks, four SASRec reuse-audit contract tasks, four Caser tasks, four GRURec tasks, and four DiffRec tasks. PreferGrow tasks use real `single_train.py`; SASRec tasks validate E5 artifacts without GPU; guarded models use their named production entry path and remain blocked by missing adapter markers.

Implement `audit_e5_root` to require `manifest.json`, `queue_status.json`, and for every domain `artifact_manifest.json`, `best_summary_sasrec.json`, `metrics_sasrec.json`, `sasrec_best.pt`, and nonempty `stdout.log`. It must parse every JSON file, verify seed 100, common evaluator/selector/split mapping identities, and emit an audit JSON into the continuation task run directory. It never edits the E5 root.

- [ ] **Step 5: Strengthen validation for required markers and guarded entrypoints**

Add to `scripts/aaai27_queue/validation.py`:

```python
def _validate_required_markers(task: TaskSpec) -> None:
    for marker in task.required_markers:
        path = PurePosixPath(marker)
        if path.is_absolute() or ".." in path.parts or not marker.startswith("protocol/adapters/"):
            raise ManifestError(f"{task.task_id}: unsafe required marker")


def _validate_guarded_model_entry(task: TaskSpec, manifest: QueueManifest) -> None:
    if task.model not in {"Caser", "GRURec", "DiffRec"}:
        return
    expected = f"protocol/adapters/{task.model.casefold()}/PASS.json"
    if task.required_markers != (expected,):
        raise ManifestError(f"{task.task_id}: guarded model lacks adapter marker")
    if len(task.argv) < 2 or not _inside(task.argv[1], manifest.source_root):
        raise ManifestError(f"{task.task_id}: guarded model entry leaves source root")
```

Call both helpers from `_validate_task`.

- [ ] **Step 6: Add negative manifest tests**

Reject seed 101, DiffuRec, BERT4Rec, `max_attempts=2`, missing one domain from a baseline group, missing one RISK-14 arm, unsafe marker path, shell-string argv, output outside queue root, forecast over 168 GPU-hours, and an E5 reuse task that claims to be a GPU training run.

- [ ] **Step 7: Run GREEN**

```powershell
python -m pytest tests/test_aaai27_continuation_adapters.py tests/test_aaai27_continuation_manifest.py tests/test_audit_e05_sasrec_reuse.py tests/test_aaai27_queue_validation.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```powershell
git add scripts/aaai27_continuation/adapters.py scripts/aaai27_continuation/manifest.py scripts/audit_e05_sasrec_reuse.py scripts/aaai27_queue/validation.py tests/test_aaai27_continuation_adapters.py tests/test_aaai27_continuation_manifest.py tests/test_audit_e05_sasrec_reuse.py tests/test_aaai27_queue_validation.py
git commit -m "feat: build frozen Stage D continuation manifest"
```

## Task 5: Implement the continuation controller and status projection

**Files:**

- Create: `scripts/aaai27_continuation/controller.py`
- Create: `tests/test_aaai27_continuation_controller.py`

- [ ] **Step 1: Write failing controller tests**

```python
def test_controller_starts_zero_tasks_before_r7_terminal(tmp_path: Path) -> None:
    controller, runtime = build_controller_fixture(tmp_path, upstream_state="waiting")
    controller.tick(runtime)
    assert runtime.started == []
    assert controller.status()["gate"] == "waiting_r7"


def test_controller_starts_ready_tasks_only_after_method_pass(tmp_path: Path) -> None:
    controller, runtime = build_controller_fixture(
        tmp_path,
        upstream_state="risk_gated_method",
        adapter_markers=("prefergrow",),
    )
    controller.tick(runtime)
    assert {task.task_id for task in runtime.started} == {
        "continuation.method_pass_gate",
    }


def test_status_reports_adapter_and_maintenance_blocks(tmp_path: Path) -> None:
    controller, _ = build_controller_fixture(
        tmp_path,
        upstream_state="risk_gated_method",
        now="2026-07-16T12:00:00+08:00",
    )
    status = controller.status()
    assert status["counts"]["blocked_adapter"] > 0
    assert status["counts"]["blocked_maintenance"] > 0
```

- [ ] **Step 2: Run RED**

```powershell
python -m pytest tests/test_aaai27_continuation_controller.py -q
```

Expected: import failure because the controller module is absent.

- [ ] **Step 3: Implement the controller as a narrow wrapper**

```python
class ContinuationController:
    def __init__(
        self,
        queue_root: Path,
        manifest: QueueManifest,
        upstream_binding: UpstreamBinding,
        maintenance: MaintenanceWindow,
        *,
        now: Callable[[], datetime],
        free_disk_gib: Callable[[], float],
        live_process: Callable[[int, str], bool],
    ) -> None:
        self._base = QueueController(
            queue_root,
            manifest,
            live_process=live_process,
            free_disk_gib=free_disk_gib,
        )
        self._binding = upstream_binding
        self._maintenance = maintenance
        self._now = now

    def eligibility(self) -> dict[str, EligibilityDecision]:
        upstream = verify_r7_upstream(self._binding)
        if upstream.state == "waiting":
            return {
                task.task_id: EligibilityDecision(
                    ready=False,
                    status="blocked_upstream",
                    reason="r7 has not produced a terminal RISK-08 exit",
                )
                for task in self._base.manifest.tasks
            }
        if not upstream.authorized:
            return preserve_only_decisions(self._base.manifest.tasks, upstream.exit_value)
        records = self._base.load_records()
        passed = frozenset(
            task_id for task_id, record in records.items()
            if record.status == "passed"
        )
        context = EligibilityContext(
            now=self._now(),
            planned_shutdown=self._maintenance.planned_shutdown,
            maintenance_buffer_hours=self._maintenance.buffer_hours,
            queue_root=self._base.root,
            free_disk_gib=self._free_disk_gib(),
            actual_gpu_hours=sum(record.gpu_seconds for record in records.values()) / 3600.0,
            gpu_budget_hours=self._base.manifest.gpu_budget_hours,
            passed_task_ids=passed,
        )
        return {
            task.task_id: classify_task(task, context)
            for task in self._base.manifest.tasks
            if task.task_id not in records
        }

    def tick(self, runtime: RuntimeAdapter) -> None:
        self._base.observe(runtime)
        decisions = self.eligibility()
        ready_ids = {
            task_id for task_id, decision in decisions.items()
            if decision.ready
        }
        for task in self._base.ready_tasks():
            if task.task_id in ready_ids:
                self._base.start_one(runtime, task)

    def status(self) -> dict[str, object]:
        decisions = self.eligibility()
        counts = Counter(decision.status for decision in decisions.values())
        records = self._base.load_records()
        counts.update(record.status for record in records.values())
        upstream = verify_r7_upstream(self._binding)
        return {
            "schema_version": 1,
            "gate": (
                "waiting_r7"
                if upstream.state == "waiting"
                else "method_pass"
                if upstream.authorized
                else upstream.exit_value
            ),
            "risk08_exit": upstream.exit_value,
            "counts": dict(sorted(counts.items())),
            "queue_root": str(self._base.root),
            "manifest_sha256": self._manifest_sha256,
            "planned_shutdown": self._maintenance.planned_shutdown.isoformat(),
        }
```

Add `self._free_disk_gib` and `self._manifest_sha256` assignments in `__init__`. Refactor the imported `QueueController.tick` into public `observe(runtime)` and `start_one(runtime, task)` methods, then make its original `tick` call those two methods. This preserves process supervision and task-record persistence while allowing the continuation wrapper to filter ready tasks. Preserve all existing queue-core tests.

- [ ] **Step 4: Test preserve-only and corruption cases**

Add tests proving `audit_only`, `submission_stop`, task failure, unknown exit, upstream hash mismatch, controller restart with passed records, and orphaned running records behave fail closed.

- [ ] **Step 5: Run GREEN and all queue regressions**

```powershell
python -m pytest tests/test_aaai27_continuation_controller.py tests/test_aaai27_queue_controller.py tests/test_aaai27_queue_runtime.py tests/test_aaai27_queue_scheduler.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add scripts/aaai27_continuation/controller.py scripts/aaai27_queue/controller.py tests/test_aaai27_continuation_controller.py tests/test_aaai27_queue_controller.py
git commit -m "feat: add maintenance-aware continuation controller"
```

## Task 6: Add the prepare, validate, status, and resident-run CLI

**Files:**

- Create: `scripts/aaai27_method_pass_continuation.py`
- Create: `tests/test_aaai27_method_pass_continuation_cli.py`

- [ ] **Step 1: Write failing CLI tests**

```python
def test_prepare_writes_manifest_protocol_and_hashes(tmp_path: Path) -> None:
    result = run_cli("prepare", "--queue-root", str(tmp_path), fixture_arguments())
    assert result.returncode == 0
    assert (tmp_path / "queue" / "queue_seed100_continuation.json").is_file()
    assert (tmp_path / "protocol" / "upstream_binding.json").is_file()
    assert (tmp_path / "protocol" / "maintenance_window.json").is_file()
    assert (tmp_path / "queue" / "queue_manifest_meta.json").is_file()


def test_status_is_read_only_and_reports_waiting_r7(tmp_path: Path) -> None:
    prepare_fixture(tmp_path, upstream_terminal=False)
    before = tree_hashes(tmp_path)
    result = run_cli("status", "--queue-root", str(tmp_path))
    assert result.returncode == 0
    assert json.loads(result.stdout)["gate"] == "waiting_r7"
    assert tree_hashes(tmp_path) == before


def test_run_once_never_starts_gpu_for_submission_stop(tmp_path: Path) -> None:
    prepare_fixture(tmp_path, exit_value="submission_stop")
    result = run_cli("run", "--queue-root", str(tmp_path), "--once")
    assert result.returncode == 0
    assert load_events(tmp_path) == []
```

- [ ] **Step 2: Run RED**

```powershell
python -m pytest tests/test_aaai27_method_pass_continuation_cli.py -q
```

Expected: CLI file is absent.

- [ ] **Step 3: Implement subcommands**

The parser must expose:

```text
prepare
validate
status
run --once
run --poll-seconds 10
```

Core dispatch:

```python
def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = args.handler(args)
    except ContinuationError as exc:
        print(json.dumps({"status": "error", "reason": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0
```

`prepare` uses atomic create and refuses an existing nonempty queue root. `validate` recomputes every bound hash. `status` must not write. `run` acquires an OS controller lock, writes controller status, polls every 10 seconds, and executes `finally` to record `status=stopped` when interrupted without a scientific child.

- [ ] **Step 4: Add empty-log and artifact validation**

The success validator must require:

```python
log_path.stat().st_size > 0
all(success_artifact_path.is_file() and success_artifact_path.stat().st_size > 0)
valid_json(summary_path)
valid_json(artifact_manifest_path)
```

A zero-byte log or missing/invalid artifact returns `artifacts_valid=False`; no post-hoc reconstruction is performed.

- [ ] **Step 5: Run GREEN and CLI help smoke**

```powershell
python -m pytest tests/test_aaai27_method_pass_continuation_cli.py -q
python scripts/aaai27_method_pass_continuation.py --help
```

Expected: tests pass and help lists all five operations.

- [ ] **Step 6: Commit**

```powershell
git add scripts/aaai27_method_pass_continuation.py tests/test_aaai27_method_pass_continuation_cli.py
git commit -m "feat: add resident continuation CLI"
```

## Task 7: Run full local verification and write the operations runbook

**Files:**

- Create: `docs/reports/data/2026-07-13-method-pass-continuation/OPERATIONS_RUNBOOK.md`
- Create: `docs/reports/data/2026-07-13-method-pass-continuation/LOCAL_TEST_REPORT.md`

- [ ] **Step 1: Run the focused suite**

```powershell
python -m pytest tests/test_aaai27_continuation_upstream.py tests/test_aaai27_continuation_policy.py tests/test_aaai27_continuation_adapters.py tests/test_aaai27_continuation_manifest.py tests/test_audit_e05_sasrec_reuse.py tests/test_aaai27_continuation_controller.py tests/test_aaai27_method_pass_continuation_cli.py -q
```

Expected: all continuation tests pass with no warnings or skipped tests.

- [ ] **Step 2: Run the imported queue-core regression suite**

```powershell
python -m pytest tests/test_aaai27_queue_models.py tests/test_aaai27_queue_storage.py tests/test_aaai27_queue_scheduler.py tests/test_aaai27_queue_validation.py tests/test_aaai27_queue_runtime.py tests/test_aaai27_queue_controller.py -q
```

Expected: all imported tests remain green.

- [ ] **Step 3: Run static and syntax checks**

```powershell
python -m compileall -q scripts/aaai27_queue scripts/aaai27_continuation scripts/aaai27_method_pass_continuation.py
git diff --check
rg -n "fake_train|DiffuRec|seed.?10[12]|max_attempts.?[2-9]|STOP_AFTER_CURRENT" scripts/aaai27_continuation scripts/aaai27_method_pass_continuation.py
```

Expected: compile succeeds; diff check is clean; forbidden scan has no enabled scientific task and any textual occurrence is an explicit validator/test prohibition.

- [ ] **Step 4: Write the exact runbook**

Document:

- queue/source/upstream paths;
- prepare, validate, status, run, restart, and safe-stop commands;
- `risk_gated_method` versus preserve-only behavior;
- maintenance deadline and timezone;
- adapter marker schema and creation authority;
- GPU/disk/budget gates;
- empty-log behavior;
- upgrade recovery sequence;
- explicit statement that no backup was performed by this task.

- [ ] **Step 5: Record the local test report**

Include command, Python version, test counts, timestamps, Git revision, and SHA-256 of the planned server source manifest. Do not claim server validation yet.

- [ ] **Step 6: Commit**

```powershell
git add docs/reports/data/2026-07-13-method-pass-continuation
git commit -m "docs: add continuation operations contract"
```

## Task 8: Build and validate an immutable Linux bundle without launching training

**Files:** server-side immutable bundle and dated queue root generated by the CLI.

- [ ] **Step 1: Create a source manifest locally**

Run:

```powershell
$rev = git rev-parse --short=7 HEAD
git ls-files | Sort-Object | ForEach-Object { Get-FileHash -Algorithm SHA256 $_ } | Format-Table -AutoSize | Out-String -Width 4096 | Set-Content -Encoding utf8 source_manifest_$rev.txt
```

Expected: manifest covers only tracked source; it does not include dirty main-worktree files.

- [ ] **Step 2: Transfer to a new server bundle**

Run:

```powershell
$rev = git rev-parse --short=7 HEAD
$bundle = "/data/Zijian/goal/RecDemo_aaai27_continuation_$rev"
ssh zijian@172.18.0.40 "test ! -e $bundle && mkdir -p $bundle"
git archive --format=tar HEAD | ssh zijian@172.18.0.40 "tar -xf - -C $bundle"
scp source_manifest_$rev.txt "zijian@172.18.0.40:$bundle/source_manifest.txt"
```

Expected: a new isolated bundle; no existing source or artifact directory is overwritten.

- [ ] **Step 3: Run Linux tests in the immutable bundle**

Run:

```powershell
$rev = git rev-parse --short=7 HEAD
ssh zijian@172.18.0.40 "cd /data/Zijian/goal/RecDemo_aaai27_continuation_$rev && /data/Zijian/goal/PreferGrow/.venv/bin/python3 -m pytest tests/test_aaai27_continuation_upstream.py tests/test_aaai27_continuation_policy.py tests/test_aaai27_continuation_adapters.py tests/test_aaai27_continuation_manifest.py tests/test_audit_e05_sasrec_reuse.py tests/test_aaai27_continuation_controller.py tests/test_aaai27_method_pass_continuation_cli.py tests/test_aaai27_queue_runtime.py tests/test_aaai27_queue_controller.py -q"
```

Expected: all Linux tests pass.

- [ ] **Step 4: Verify r7 remains byte-identical before prepare**

Run:

```powershell
ssh zijian@172.18.0.40 "sha256sum /data/Zijian/goal/aaai27_queue/2026-07-12-risk0607-987eb19-r7/queue/queue_seed100.json"
```

Expected:

```text
387636c8c5dc5b09bb9c509db26b0f335ecac3ed1525e3c4bee3289612bb966e
```

- [ ] **Step 5: Prepare a new dated continuation root**

Run the CLI with the real r7 paths, E5 root, dataset contracts, maintenance time `2026-07-17T00:00:00+08:00`, maintenance buffer `3.0`, and conservative launch cutoff `2026-07-16T12:00:00+08:00`. The command must print the new queue root and manifest SHA-256. It must not start the resident controller.

- [ ] **Step 6: Run validate and read-only status**

Expected while r7 is incomplete:

```json
{
  "gate": "waiting_r7",
  "running": 0,
  "started": 0,
  "risk08_exit": null
}
```

- [ ] **Step 7: Run fake-worker dry-run in a separate smoke root**

The smoke root must use fake workers and synthetic markers. Prove:

- method pass schedules tasks;
- audit-only and submission-stop schedule none;
- two fake GPUs run at most one task each;
- maintenance-blocked tasks do not start;
- zero-byte logs fail;
- passed records survive controller restart.

No smoke output may be copied into the production continuation root.

## Task 9: Start the detached continuation controller

**Files:** server controller state, tmux session, and production logs.

- [ ] **Step 1: Re-run production validation immediately before launch**

Check:

- r7 manifest SHA-256 is still the frozen value;
- continuation manifest/source/finalizer hashes pass;
- current r7 status is either waiting or valid terminal;
- `/data` has at least 40 GiB free;
- no continuation controller lock is held;
- no production task record exists before first launch;
- current time and maintenance window are correct.

- [ ] **Step 2: Start exactly one detached controller**

Use a tmux session named from the continuation revision and execute:

```text
/data/Zijian/goal/PreferGrow/.venv/bin/python3
scripts/aaai27_method_pass_continuation.py
run
--queue-root "$queue_root_from_prepare_json"
--poll-seconds 10
```

The actual launch command is stored in `state/tmux_session.json` before tmux starts. The absolute production root is read from the prepare output; it is not handwritten.

- [ ] **Step 3: Verify resident behavior while r7 is incomplete**

Expected after at least two poll intervals:

```text
controller PID alive
status=running
gate=waiting_r7
scientific child PID count=0
GPU ownership unchanged
task records count=0
```

- [ ] **Step 4: Verify no backup and no r7 mutation**

Confirm no new backup path was created and r7 manifest SHA remains frozen. Compare r7 task-record count before/after continuation launch; the continuation controller must not write r7.

- [ ] **Step 5: Record the one-line operational status**

Use:

```text
CONT-R7 | resident_waiting_r7 | controller PID + manifest SHA + queue root | gap: RISK-08 not terminal | next: automatic gate consumption
```

## Task 10: Update the ledger and complete verification

**Files:**

- Modify: `issues/2026-07-10_21-18-20-aaai27-evidence-risk-rescue.csv`
- Modify: `docs/reports/data/2026-07-13-method-pass-continuation/LOCAL_TEST_REPORT.md`

- [ ] **Step 1: Update only factual execution state**

Record the continuation queue root, source revision, manifest SHA, controller PID/session, maintenance window, current gate, adapter-ready models, blocked-adapter models, and zero scientific launches while r7 is incomplete. Do not mark RISK-10/11/13/14 scientifically completed.

- [ ] **Step 2: Run final verification**

Run:

```powershell
python -m pytest tests/test_aaai27_continuation_upstream.py tests/test_aaai27_continuation_policy.py tests/test_aaai27_continuation_adapters.py tests/test_aaai27_continuation_manifest.py tests/test_audit_e05_sasrec_reuse.py tests/test_aaai27_continuation_controller.py tests/test_aaai27_method_pass_continuation_cli.py tests/test_aaai27_queue_models.py tests/test_aaai27_queue_storage.py tests/test_aaai27_queue_scheduler.py tests/test_aaai27_queue_validation.py tests/test_aaai27_queue_runtime.py tests/test_aaai27_queue_controller.py -q
git diff --check
```

Expected: all tests pass and diff check is clean.

- [ ] **Step 3: Verify server freshness**

Read back controller state, current r7 counts, RISK-08 exit, GPU PIDs, `/data` free space, continuation block counts, and latest event timestamp. Any mismatch between local expectation and server artifact must be reported with server artifact taking precedence.

- [ ] **Step 4: Commit the factual ledger update**

```powershell
git add issues/2026-07-10_21-18-20-aaai27-evidence-risk-rescue.csv docs/reports/data/2026-07-13-method-pass-continuation/LOCAL_TEST_REPORT.md
git commit -m "ops: deploy r7 method-pass continuation"
```

- [ ] **Step 5: Push the isolated branch**

```powershell
git push -u origin codex/r7-method-pass-continuation
```

Expected: the exact deployed revision is available remotely. If authentication fails, deployment remains valid but the push gap is reported explicitly.

## Completion criteria

The plan is complete only when:

- r7 manifest hash remains `387636c8c5dc5b09bb9c509db26b0f335ecac3ed1525e3c4bee3289612bb966e`;
- one continuation controller is alive in tmux;
- r7 incomplete means zero continuation scientific starts;
- only `risk_gated_method` can unlock Stage D;
- preserve-only and malformed evidence launch zero tasks;
- RISK-13/RISK-14 use real PreferGrow argv;
- E5 SASRec is reused only after identity audit;
- Caser/GRURec/DiffRec remain adapter-gated until real audits pass;
- maintenance, disk, budget, single-GPU, empty-log, and attempt-once tests pass;
- no backup operation occurred;
- server and ledger paths, hashes, PID, session, and block reasons are documented.
