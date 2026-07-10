# AAAI-27 Seed-100 Resident Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify a fail-closed, resumable, server-resident seed-100 queue controller without deploying it or launching scientific experiments.

**Architecture:** A Python package under `scripts/aaai27_queue/` separates immutable manifest validation, atomic storage, pure scheduling, Linux process/GPU supervision, and persistent controller state. Thin entry points provide local SSH launch, remote tmux session management, controller CLI/status, and an isolated no-op smoke; scientific RISK adapters remain governed by the existing rescue ledger and must be supplied separately before deployment.

**Tech Stack:** Python 3 standard library, `unittest`, Linux `fcntl.flock`, `subprocess` argv execution, JSON/JSONL state, SSH, tmux, and NVIDIA `nvidia-smi`.

---

## 🛡️ Scope boundary

This plan implements only the orchestration subsystem defined by [the approved resident-queue design](../specs/2026-07-10-aaai27-seed100-resident-queue-design.md). It does not implement RISK-01 through RISK-14 scientific adapters, synchronize files to `l20`, create a remote queue root, start tmux, or launch an experiment.

A real queue manifest is accepted only when every enabled task has a complete argv, artifact contract, ledger mapping, and immutable provenance. Until those adapters exist, the controller is verified through unit tests, dry-run branch simulations, and a local no-op lifecycle.

## 📋 File map

| File | Responsibility |
| --- | --- |
| `scripts/aaai27_queue/__init__.py` | Stable package exports and schema version |
| `scripts/aaai27_queue/models.py` | Frozen task, queue, marker, and runtime record types |
| `scripts/aaai27_queue/validation.py` | Fail-closed manifest and branch-matrix validation |
| `scripts/aaai27_queue/storage.py` | SHA-256, safe paths, atomic JSON, and append-only JSONL |
| `scripts/aaai27_queue/scheduler.py` | Pure gate, dependency, resource, and priority decisions |
| `scripts/aaai27_queue/runtime.py` | Linux file locks, GPU probes, and argv process supervision |
| `scripts/aaai27_queue/controller.py` | Persistent state reconciliation, dispatch loop, and recovery |
| `scripts/aaai27_queue/cli.py` | Validate, dry-run, run, status, stop, and smoke commands |
| `scripts/aaai27_resident_queue.py` | Executable controller entry point |
| `scripts/aaai27_remote_tmux_entry.py` | Idempotent server-side tmux entry without session killing |
| `scripts/launch_aaai27_seed100_queue.py` | Shell-free local SSH builder and launcher |
| `tests/aaai27_queue_testdata.py` | Deterministic complete and invalid manifest builders |
| `tests/test_aaai27_queue_*.py` | Model, validation, storage, scheduler, runtime, controller, and CLI tests |
| `tests/test_launch_aaai27_seed100_queue.py` | Local SSH and remote tmux safety tests |
| `docs/runbooks/2026-07-10-aaai27-seed100-resident-queue.md` | Operator commands, recovery, and authorization gates |

### Task 1: Create immutable queue data models

**Files:**
- Create: `scripts/aaai27_queue/__init__.py`
- Create: `scripts/aaai27_queue/models.py`
- Create: `tests/aaai27_queue_testdata.py`
- Create: `tests/test_aaai27_queue_models.py`

- [ ] **Step 1: Write the model round-trip test**

```python
# tests/test_aaai27_queue_models.py
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from aaai27_queue.models import QueueManifest, TaskSpec


class QueueModelTests(unittest.TestCase):
    def test_task_round_trip_preserves_argv_and_hashes(self) -> None:
        raw = {
            "schema_version": 1,
            "task_id": "RISK-02.trace.seed100",
            "ledger_id": "RISK-02",
            "phase": "front_gate",
            "branch": "common",
            "kind": "gpu",
            "argv": ["/opt/venv/bin/python", "scripts/run_e1_trace.py", "--seed", "100"],
            "cwd": "/srv/bundle/source",
            "env": {"PYTHONHASHSEED": "100"},
            "dependencies": ["RISK-01.lock"],
            "required_markers": ["RISK-01_PASS.json"],
            "success_artifacts": ["runs/RISK-02/trace.json"],
            "failure_policy": "fail_closed",
            "max_attempts": 1,
            "gpu_slots": 1,
            "gpu_hours_low": 0.05,
            "gpu_hours_high": 0.1,
            "estimated_output_gib": 0.1,
            "seed": 100,
            "dataset": "Beauty",
            "arm": "trace",
            "model": "PreferGrow",
            "run_dir": "/srv/queue/runs/RISK-02/Beauty/trace/seed100",
            "code_revision": "a" * 40,
            "config_sha256": "b" * 64,
            "split_sha256": "c" * 64,
            "bank_sha256": None,
            "evaluator_version": "evaluator-tailfix-v1",
            "selector_version": "validation-ndcg10-p5-v1",
            "atomic_group": None,
            "priority": 0,
        }
        task = TaskSpec.from_dict(raw)
        self.assertEqual(("/opt/venv/bin/python", "scripts/run_e1_trace.py", "--seed", "100"), task.argv)
        self.assertEqual(raw, task.to_dict())

    def test_queue_rejects_unknown_top_level_keys_during_decode(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown queue fields"):
            QueueManifest.from_dict({"schema_version": 1, "queue_id": "q", "tasks": [], "extra": True})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify the package is absent**

Run:

```bash
python -m unittest tests.test_aaai27_queue_models -v
```

Expected: `ERROR` with `ModuleNotFoundError: No module named 'aaai27_queue'`.

- [ ] **Step 3: Add the package schema version**

```python
# scripts/aaai27_queue/__init__.py
SCHEMA_VERSION = 1

__all__ = ["SCHEMA_VERSION"]
```

- [ ] **Step 4: Implement frozen models with exact-field decoding**

```python
# scripts/aaai27_queue/models.py
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any


def _decode_exact(cls: type, raw: dict[str, Any], label: str):
    allowed = {field.name for field in fields(cls)}
    unknown = sorted(set(raw) - allowed)
    missing = sorted(name for name in allowed if name not in raw)
    if unknown:
        raise ValueError(f"unknown {label} fields: {unknown}")
    if missing:
        raise ValueError(f"missing {label} fields: {missing}")
    return cls(**raw)


@dataclass(frozen=True)
class TaskSpec:
    schema_version: int
    task_id: str
    ledger_id: str
    phase: str
    branch: str
    kind: str
    argv: tuple[str, ...]
    cwd: str
    env: dict[str, str]
    dependencies: tuple[str, ...]
    required_markers: tuple[str, ...]
    success_artifacts: tuple[str, ...]
    failure_policy: str
    max_attempts: int
    gpu_slots: int
    gpu_hours_low: float
    gpu_hours_high: float
    estimated_output_gib: float
    seed: int | None
    dataset: str | None
    arm: str | None
    model: str | None
    run_dir: str
    code_revision: str
    config_sha256: str
    split_sha256: str | None
    bank_sha256: str | None
    evaluator_version: str | None
    selector_version: str | None
    atomic_group: str | None
    priority: int

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "TaskSpec":
        converted = dict(raw)
        for name in ("argv", "dependencies", "required_markers", "success_artifacts"):
            converted[name] = tuple(converted[name])
        return _decode_exact(cls, converted, "task")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for name in ("argv", "dependencies", "required_markers", "success_artifacts"):
            payload[name] = list(payload[name])
        return payload


@dataclass(frozen=True)
class QueueManifest:
    schema_version: int
    queue_id: str
    created_at: str
    run_root: str
    source_root: str
    source_manifest_sha256: str
    ledger_path: str
    ledger_sha256: str
    gpu_ids: tuple[int, ...]
    gpu_budget_hours: float
    min_free_disk_gib: float
    tasks: tuple[TaskSpec, ...]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "QueueManifest":
        allowed = {field.name for field in fields(cls)}
        unknown = sorted(set(raw) - allowed)
        missing = sorted(name for name in allowed if name not in raw)
        if unknown:
            raise ValueError(f"unknown queue fields: {unknown}")
        if missing:
            raise ValueError(f"missing queue fields: {missing}")
        converted = dict(raw)
        converted["gpu_ids"] = tuple(converted["gpu_ids"])
        converted["tasks"] = tuple(TaskSpec.from_dict(item) for item in converted["tasks"])
        return cls(**converted)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["gpu_ids"] = list(self.gpu_ids)
        payload["tasks"] = [task.to_dict() for task in self.tasks]
        return payload


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    status: str
    attempt: int
    pid: int | None
    process_start_time: str | None
    gpu_id: int | None
    started_at: str | None
    ended_at: str | None
    exit_code: int | None
    gpu_seconds: float
    reason: str | None


@dataclass(frozen=True)
class GateSnapshot:
    e1_outcome: str | None
    risk08_exit: str | None
```

- [ ] **Step 5: Add deterministic test-data builders**

```python
# tests/aaai27_queue_testdata.py
from __future__ import annotations

from typing import Any

DEFAULT_RUN_ROOT = "/srv/queue"


def make_task(**overrides: Any) -> dict[str, Any]:
    task_id = str(overrides.get("task_id", "RISK-01.lock"))
    payload: dict[str, Any] = {
        "schema_version": 1,
        "task_id": task_id,
        "ledger_id": "RISK-01",
        "phase": "front_gate",
        "branch": "common",
        "kind": "gpu",
        "argv": ["/opt/venv/bin/python", "scripts/fake_adapter.py", "--seed", "100"],
        "cwd": "/srv/bundle/source",
        "env": {"PYTHONHASHSEED": "100"},
        "dependencies": [],
        "required_markers": [],
        "success_artifacts": [f"manifests/{task_id}.json"],
        "failure_policy": "fail_closed",
        "max_attempts": 1,
        "gpu_slots": 1,
        "gpu_hours_low": 0.1,
        "gpu_hours_high": 1.0,
        "estimated_output_gib": 0.1,
        "seed": 100,
        "dataset": "Beauty",
        "arm": "host",
        "model": "PreferGrow",
        "run_dir": f"{DEFAULT_RUN_ROOT}/runs/{task_id}",
        "code_revision": "a" * 40,
        "config_sha256": "b" * 64,
        "split_sha256": "c" * 64,
        "bank_sha256": None,
        "evaluator_version": "evaluator-tailfix-v1",
        "selector_version": "validation-ndcg10-p5-v1",
        "atomic_group": None,
        "priority": 0,
    }
    payload.update(overrides)
    return payload


def make_manifest(tasks: list[dict[str, Any]], **overrides: Any) -> dict[str, Any]:
    run_root = str(overrides.get("run_root", DEFAULT_RUN_ROOT))
    normalized: list[dict[str, Any]] = []
    for source in tasks:
        task = dict(source)
        if str(task["run_dir"]).startswith(f"{DEFAULT_RUN_ROOT}/runs/"):
            task["run_dir"] = f"{run_root}/runs/{task['task_id']}"
        normalized.append(task)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "queue_id": "aaai27-seed100-test",
        "created_at": "2026-07-10T22:00:00+08:00",
        "run_root": run_root,
        "source_root": "/srv/bundle/source",
        "source_manifest_sha256": "d" * 64,
        "ledger_path": "/srv/bundle/issues/2026-07-10_21-18-20-aaai27-evidence-risk-rescue.csv",
        "ledger_sha256": "e" * 64,
        "gpu_ids": [0, 1],
        "gpu_budget_hours": 168.0,
        "min_free_disk_gib": 40.0,
        "tasks": normalized,
    }
    payload.update(overrides)
    return payload
```

- [ ] **Step 6: Run the model tests**

Run:

```bash
python -m unittest tests.test_aaai27_queue_models -v
```

Expected: two tests pass and the command exits 0.

- [ ] **Step 7: Commit the model layer**

```bash
git add -- scripts/aaai27_queue/__init__.py scripts/aaai27_queue/models.py tests/aaai27_queue_testdata.py tests/test_aaai27_queue_models.py
git commit -m "feat: add resident queue data models"
```

### Task 2: Enforce the scientific and safety manifest contract

**Files:**
- Create: `scripts/aaai27_queue/validation.py`
- Create: `tests/test_aaai27_queue_validation.py`

- [ ] **Step 1: Write failing validation tests**

```python
# tests/test_aaai27_queue_validation.py
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for path in (REPO_ROOT / "scripts", REPO_ROOT / "tests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from aaai27_queue.models import QueueManifest
from aaai27_queue.validation import ManifestError, validate_manifest
from aaai27_queue_testdata import make_manifest, make_task


class QueueValidationTests(unittest.TestCase):
    def assert_invalid(self, task: dict, message: str) -> None:
        pilots = make_pilot_tasks("e1_pass", True) + make_pilot_tasks("e1_fail_audit", False)
        manifest = QueueManifest.from_dict(make_manifest([*pilots, task]))
        with self.assertRaisesRegex(ManifestError, message):
            validate_manifest(manifest)

    def test_rejects_non_seed100_training(self) -> None:
        self.assert_invalid(make_task(seed=101), "seed 100")

    def test_rejects_diffurec_and_risk12(self) -> None:
        self.assert_invalid(make_task(model="DiffuRec"), "DiffuRec")
        self.assert_invalid(make_task(ledger_id="RISK-12"), "RISK-12")

    def test_rejects_retry_and_destructive_argv(self) -> None:
        self.assert_invalid(make_task(max_attempts=2), "max_attempts")
        self.assert_invalid(make_task(argv=["python", "train.py", "--force"]), "destructive")

    def test_rejects_run_directory_outside_queue_root(self) -> None:
        self.assert_invalid(make_task(run_dir="/data/Zijian/goal/RecDemoRuns/frozen"), "run_dir")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and confirm import failure**

Run:

```bash
python -m unittest tests.test_aaai27_queue_validation -v
```

Expected: `ERROR` because `aaai27_queue.validation` does not exist.

- [ ] **Step 3: Implement exact fail-closed checks**

```python
# scripts/aaai27_queue/validation.py
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from . import SCHEMA_VERSION
from .models import QueueManifest, TaskSpec

ALLOWED_LEDGER_IDS = {f"RISK-{index:02d}" for index in range(1, 15)}
ALLOWED_PHASES = {"preflight", "front_gate", "pilot", "decision", "continuation"}
ALLOWED_BRANCHES = {"common", "e1_pass", "e1_fail_audit", "method_pass"}
ALLOWED_KINDS = {"cpu", "gpu", "contract_gate"}
FOUR_DOMAINS = {"Steam", "ML1M", "Beauty", "ATG"}
CLASSIC_MODELS = {"SASRec", "Caser", "GRURec"}
DESTRUCTIVE_TOKENS = {"--force", "--no-skip-existing", "rm", "rmdir", "remove-item", "del"}


class ManifestError(ValueError):
    pass


def _inside(path: str, root: str) -> bool:
    candidate = Path(path).resolve(strict=False)
    parent = Path(root).resolve(strict=False)
    return candidate == parent or parent in candidate.parents


def _validate_task(task: TaskSpec, manifest: QueueManifest) -> None:
    if task.schema_version != SCHEMA_VERSION:
        raise ManifestError(f"{task.task_id}: unsupported schema_version")
    if task.ledger_id not in ALLOWED_LEDGER_IDS or task.ledger_id == "RISK-12":
        raise ManifestError(f"{task.task_id}: RISK-12 and unknown ledger rows are disabled")
    if task.phase not in ALLOWED_PHASES or task.branch not in ALLOWED_BRANCHES or task.kind not in ALLOWED_KINDS:
        raise ManifestError(f"{task.task_id}: invalid phase, branch, or kind")
    if task.seed not in (None, 100):
        raise ManifestError(f"{task.task_id}: only seed 100 is permitted")
    if task.model == "DiffuRec":
        raise ManifestError(f"{task.task_id}: DiffuRec is excluded")
    if task.max_attempts != 1 or task.failure_policy != "fail_closed":
        raise ManifestError(f"{task.task_id}: max_attempts must be 1 and fail_closed")
    if task.gpu_slots not in (0, 1) or (task.kind == "gpu") != (task.gpu_slots == 1):
        raise ManifestError(f"{task.task_id}: invalid gpu_slots")
    if not task.argv or any(not isinstance(item, str) or not item for item in task.argv):
        raise ManifestError(f"{task.task_id}: argv must be a nonempty string array")
    if {item.lower() for item in task.argv} & DESTRUCTIVE_TOKENS:
        raise ManifestError(f"{task.task_id}: destructive argv token")
    if not _inside(task.run_dir, manifest.run_root):
        raise ManifestError(f"{task.task_id}: run_dir leaves queue root")
    if task.gpu_hours_low < 0 or task.gpu_hours_high < task.gpu_hours_low:
        raise ManifestError(f"{task.task_id}: invalid GPU-hour estimate")


def validate_manifest(manifest: QueueManifest) -> None:
    if manifest.schema_version != SCHEMA_VERSION:
        raise ManifestError("unsupported queue schema_version")
    if manifest.gpu_ids != (0, 1):
        raise ManifestError("queue must expose exactly GPU 0 and GPU 1")
    if manifest.gpu_budget_hours != 168.0 or manifest.min_free_disk_gib != 40.0:
        raise ManifestError("queue must freeze 168 GPU-hours and 40 GiB")
    task_ids = [task.task_id for task in manifest.tasks]
    if len(task_ids) != len(set(task_ids)):
        raise ManifestError("duplicate task_id")
    known = set(task_ids)
    for task in manifest.tasks:
        _validate_task(task, manifest)
        missing = sorted(set(task.dependencies) - known)
        if missing:
            raise ManifestError(f"{task.task_id}: unknown dependencies {missing}")

    grouped: dict[tuple[str, str], set[str]] = defaultdict(set)
    for task in manifest.tasks:
        if task.ledger_id == "RISK-10" and task.model in CLASSIC_MODELS:
            grouped[(task.ledger_id, task.model)].add(task.dataset or "")
    for (_, model), datasets in grouped.items():
        if datasets != FOUR_DOMAINS:
            raise ManifestError(f"{model}: baseline group must contain all four domains")
```

- [ ] **Step 4: Add exact pilot-matrix tests**

Add this validator and call `_validate_pilot_matrix(manifest.tasks)` at the end of `validate_manifest`:

```python
def _expected_pilot(branch: str, include_full: bool) -> set[tuple[str, str]]:
    expected: set[tuple[str, str]] = set()
    for dataset in ("Beauty", "Steam"):
        expected.add((dataset, "host"))
        for level in (0, 60, 100):
            expected.add((dataset, f"text_anchor_only_c{level}"))
            if include_full:
                expected.add((dataset, f"risk_gated_full_c{level}"))
    return expected


def _validate_pilot_matrix(tasks: tuple[TaskSpec, ...]) -> None:
    for branch, include_full in (("e1_pass", True), ("e1_fail_audit", False)):
        selected = [task for task in tasks if task.phase == "pilot" and task.branch == branch]
        actual = [(task.dataset or "", task.arm or "") for task in selected]
        expected = _expected_pilot(branch, include_full)
        if len(actual) != len(expected) or set(actual) != expected:
            raise ManifestError(f"{branch}: pilot matrix differs from frozen {len(expected)}-run design")
        for task in selected:
            expected_ledger = "RISK-06" if task.dataset == "Beauty" else "RISK-07"
            if task.ledger_id != expected_ledger:
                raise ManifestError(f"{task.task_id}: pilot ledger mismatch")
```

Add this deterministic builder to `tests/test_aaai27_queue_validation.py`:

```python
def make_pilot_tasks(branch: str, include_full: bool) -> list[dict]:
    tasks: list[dict] = []
    for dataset in ("Beauty", "Steam"):
        ledger_id = "RISK-06" if dataset == "Beauty" else "RISK-07"
        tasks.append(make_task(task_id=f"pilot.{branch}.{dataset}.host", ledger_id=ledger_id, phase="pilot", branch=branch, dataset=dataset, arm="host"))
        for level in (0, 60, 100):
            tasks.append(make_task(task_id=f"pilot.{branch}.{dataset}.anchor.c{level}", ledger_id=ledger_id, phase="pilot", branch=branch, dataset=dataset, arm=f"text_anchor_only_c{level}"))
            if include_full:
                tasks.append(make_task(task_id=f"pilot.{branch}.{dataset}.full.c{level}", ledger_id=ledger_id, phase="pilot", branch=branch, dataset=dataset, arm=f"risk_gated_full_c{level}"))
    return tasks
```

Build every valid test manifest with `make_pilot_tasks("e1_pass", True) + make_pilot_tasks("e1_fail_audit", False)`. Assert that it contains 14 pass tasks, eight audit tasks, six pass-branch full tasks, and zero audit-branch full tasks. Mutate one audit arm to `risk_gated_full_c60` and assert `ManifestError`.

- [ ] **Step 5: Run validation tests**

Run:

```bash
python -m unittest tests.test_aaai27_queue_validation -v
```

Expected: all validation tests pass.

- [ ] **Step 6: Commit validation**

```bash
git add -- scripts/aaai27_queue/validation.py tests/test_aaai27_queue_validation.py
git commit -m "feat: validate resident queue contracts"
```

### Task 3: Add safe paths, hashes, atomic markers, and event logs

**Files:**
- Create: `scripts/aaai27_queue/storage.py`
- Create: `tests/test_aaai27_queue_storage.py`

- [ ] **Step 1: Write storage failure tests**

```python
# tests/test_aaai27_queue_storage.py
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from aaai27_queue.storage import append_event, atomic_write_json, require_within, sha256_file


class QueueStorageTests(unittest.TestCase):
    def test_atomic_json_has_no_temporary_file_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "markers" / "pass.json"
            atomic_write_json(path, {"status": "pass", "task_id": "x"})
            self.assertEqual({"status": "pass", "task_id": "x"}, json.loads(path.read_text(encoding="utf-8")))
            self.assertEqual([path], list(path.parent.iterdir()))

    def test_require_within_rejects_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "queue"
            root.mkdir()
            with self.assertRaisesRegex(ValueError, "outside allowed root"):
                require_within(root.parent / "frozen", root)

    def test_hash_and_jsonl_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "a.txt"
            source.write_bytes(b"abc")
            self.assertEqual("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", sha256_file(source))
            events = root / "events.jsonl"
            append_event(events, {"event": "one"})
            append_event(events, {"event": "two"})
            self.assertEqual([{"event": "one"}, {"event": "two"}], [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()])
```

- [ ] **Step 2: Verify failure before implementation**

Run:

```bash
python -m unittest tests.test_aaai27_queue_storage -v
```

Expected: import error for `aaai27_queue.storage`.

- [ ] **Step 3: Implement atomic storage primitives**

```python
# scripts/aaai27_queue/storage.py
from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any


def require_within(path: Path, root: Path) -> Path:
    resolved = path.resolve(strict=False)
    allowed = root.resolve(strict=False)
    if resolved != allowed and allowed not in resolved.parents:
        raise ValueError(f"path outside allowed root: {resolved}")
    return resolved


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        with temporary.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def append_event(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())
```

- [ ] **Step 4: Add marker identity validation**

Add the following function to `storage.py`:

```python
def validate_marker(marker: dict[str, Any], expected_task, queue_sha256: str, queue_root: Path) -> None:
    required = {
        "schema_version", "task_id", "ledger_id", "status", "created_at",
        "queue_manifest_sha256", "code_revision", "config_sha256",
        "split_sha256", "bank_sha256", "exit_code", "artifacts", "validation",
    }
    if set(marker) != required:
        raise ValueError("marker fields differ from schema")
    if marker["schema_version"] != 1:
        raise ValueError("marker schema mismatch")
    if marker["task_id"] != expected_task.task_id or marker["ledger_id"] != expected_task.ledger_id:
        raise ValueError("marker task identity mismatch")
    if marker["queue_manifest_sha256"] != queue_sha256:
        raise ValueError("marker queue hash mismatch")
    if marker["code_revision"] != expected_task.code_revision or marker["config_sha256"] != expected_task.config_sha256:
        raise ValueError("marker source or config mismatch")
    if marker["split_sha256"] != expected_task.split_sha256 or marker["bank_sha256"] != expected_task.bank_sha256:
        raise ValueError("marker data identity mismatch")
    if marker["status"] not in {"pass", "fail"} or not isinstance(marker["exit_code"], int):
        raise ValueError("marker terminal status invalid")
    validation = marker["validation"]
    validation_ok = isinstance(validation, dict) and validation.get("result") == "pass" and isinstance(validation.get("checks"), list)
    if marker["status"] == "pass" and (marker["exit_code"] != 0 or not validation_ok):
        raise ValueError("pass marker lacks successful exit and validation")
    if not isinstance(marker["artifacts"], list):
        raise ValueError("marker artifacts must be an array")
    for relative in marker["artifacts"]:
        artifact = require_within(queue_root / relative, queue_root)
        if not artifact.is_file():
            raise ValueError(f"marker artifact missing: {relative}")
```

Test a valid pass marker, then independently change the queue hash, task ID, config hash, split hash, exit code, validation result, and artifact path and assert rejection. Controller tests, not this function, create simultaneous `RISK-02_PASS.json` and `RISK-02_FAIL.json` and assert an integrity failure.

- [ ] **Step 5: Run storage tests**

Run:

```bash
python -m unittest tests.test_aaai27_queue_storage -v
```

Expected: all storage tests pass.

- [ ] **Step 6: Commit storage**

```bash
git add -- scripts/aaai27_queue/storage.py tests/test_aaai27_queue_storage.py
git commit -m "feat: add atomic queue evidence storage"
```

### Task 4: Implement pure branch, dependency, budget, and disk scheduling

**Files:**
- Create: `scripts/aaai27_queue/scheduler.py`
- Create: `tests/test_aaai27_queue_scheduler.py`

- [ ] **Step 1: Write branch and resource tests**

```python
# tests/test_aaai27_queue_scheduler.py
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for path in (REPO_ROOT / "scripts", REPO_ROOT / "tests"):
    sys.path.insert(0, str(path))

from aaai27_queue.models import GateSnapshot, QueueManifest
from aaai27_queue.scheduler import IntegrityError, choose_ready_tasks, select_active_branch
from aaai27_queue_testdata import make_manifest, make_task


class QueueSchedulerTests(unittest.TestCase):
    def test_e1_fail_selects_audit_and_cannot_enter_method_pass(self) -> None:
        self.assertEqual("e1_fail_audit", select_active_branch(GateSnapshot("fail", None)))
        with self.assertRaisesRegex(IntegrityError, "E1 pass"):
            select_active_branch(GateSnapshot("fail", "risk_gated_method"))

    def test_risk08_method_exit_unlocks_continuation_after_e1_pass(self) -> None:
        self.assertEqual("method_pass", select_active_branch(GateSnapshot("pass", "risk_gated_method")))

    def test_budget_and_disk_block_new_work(self) -> None:
        task = make_task(task_id="RISK-13.Steam.host.seed100", ledger_id="RISK-13", branch="method_pass", gpu_hours_high=10.0)
        manifest = QueueManifest.from_dict(make_manifest([task]))
        gates = GateSnapshot("pass", "risk_gated_method")
        self.assertEqual([], choose_ready_tasks(manifest, {}, gates, 160.0, 80.0, set()))
        self.assertEqual([], choose_ready_tasks(manifest, {}, gates, 0.0, 39.9, set()))
```

- [ ] **Step 2: Run tests and verify scheduler import failure**

Run:

```bash
python -m unittest tests.test_aaai27_queue_scheduler -v
```

Expected: import error for `aaai27_queue.scheduler`.

- [ ] **Step 3: Implement deterministic branch selection and readiness**

```python
# scripts/aaai27_queue/scheduler.py
from __future__ import annotations

from .models import GateSnapshot, QueueManifest, TaskRecord, TaskSpec


class IntegrityError(RuntimeError):
    pass


def select_active_branch(gates: GateSnapshot) -> str:
    if gates.e1_outcome is None:
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
    ready: list[TaskSpec] = []
    for task in manifest.tasks:
        if task.task_id in started or task.branch not in {"common", branch}:
            continue
        if not set(task.dependencies).issubset(passed):
            continue
        if actual_gpu_hours + task.gpu_hours_high > manifest.gpu_budget_hours:
            continue
        if task.gpu_slots == 1 and len(busy_gpu_ids) >= len(manifest.gpu_ids):
            continue
        ready.append(task)
    return sorted(ready, key=lambda task: (task.priority, task.task_id))
```

- [ ] **Step 4: Add dependency, no-retry, baseline-group, and priority tests**

Prove that dependencies require `passed`; any attempt-1 record is never selected again; a validated all-four baseline group may occupy available GPU slots sequentially but a failed member marks the whole group incomplete; RISK-13 sorts ahead of RISK-14, RISK-10, and RISK-11; and `terminal_stop` returns no tasks. Add `group_status(records, tasks, atomic_group)` returning `pending`, `running`, `passed`, or `incomplete`; it returns `passed` only when all four domain members passed and `incomplete` when any member failed or became interrupted.

- [ ] **Step 5: Run scheduler tests**

Run:

```bash
python -m unittest tests.test_aaai27_queue_scheduler -v
```

Expected: all scheduler tests pass.

- [ ] **Step 6: Commit scheduler**

```bash
git add -- scripts/aaai27_queue/scheduler.py tests/test_aaai27_queue_scheduler.py
git commit -m "feat: add fail-closed queue scheduler"
```

### Task 5: Add Linux GPU locking and argv process supervision

**Files:**
- Create: `scripts/aaai27_queue/runtime.py`
- Create: `tests/test_aaai27_queue_runtime.py`

- [ ] **Step 1: Write injectable runtime tests**

```python
# tests/test_aaai27_queue_runtime.py
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from aaai27_queue.runtime import GpuBusyError, ProcessSupervisor, probe_gpu_pids


class QueueRuntimeTests(unittest.TestCase):
    def test_gpu_probe_parses_integer_pids(self) -> None:
        runner = mock.Mock(return_value=subprocess.CompletedProcess([], 0, "123\n456\n", ""))
        self.assertEqual({123, 456}, probe_gpu_pids(1, runner=runner))
        self.assertIn("--id=1", runner.call_args.args[0])

    def test_supervisor_uses_argv_no_shell_and_new_session(self) -> None:
        popen = mock.Mock()
        popen.return_value.pid = 77
        supervisor = ProcessSupervisor(popen=popen)
        with tempfile.TemporaryDirectory() as tmpdir:
            supervisor.start(
                argv=["python", "train.py", "--seed", "100"],
                cwd=Path(tmpdir),
                env={"CUDA_VISIBLE_DEVICES": "0"},
                stdout_path=Path(tmpdir) / "task.log",
            )
        kwargs = popen.call_args.kwargs
        self.assertFalse(kwargs["shell"])
        self.assertTrue(kwargs["start_new_session"])

    def test_unknown_gpu_process_blocks_without_spawn(self) -> None:
        supervisor = ProcessSupervisor(popen=mock.Mock())
        with self.assertRaises(GpuBusyError):
            supervisor.require_gpu_free(0, probe=lambda _: {999})
        supervisor._popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify runtime import failure**

Run:

```bash
python -m unittest tests.test_aaai27_queue_runtime -v
```

Expected: import error for `aaai27_queue.runtime`.

- [ ] **Step 3: Implement NVIDIA probing and shell-free spawn**

```python
# scripts/aaai27_queue/runtime.py
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable, IO


class GpuBusyError(RuntimeError):
    pass


def probe_gpu_pids(
    gpu_id: int,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> set[int]:
    command = [
        "nvidia-smi",
        f"--id={gpu_id}",
        "--query-compute-apps=pid",
        "--format=csv,noheader,nounits",
    ]
    result = runner(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise GpuBusyError(f"GPU probe failed for {gpu_id}: {result.stderr.strip()}")
    return {int(line.strip()) for line in result.stdout.splitlines() if line.strip().isdigit()}


class ProcessSupervisor:
    def __init__(self, popen: Callable[..., subprocess.Popen] = subprocess.Popen) -> None:
        self._popen = popen
        self._log_handles: dict[int, IO[bytes]] = {}

    def require_gpu_free(self, gpu_id: int, probe: Callable[[int], set[int]] = probe_gpu_pids) -> None:
        pids = probe(gpu_id)
        if pids:
            raise GpuBusyError(f"GPU {gpu_id} already has compute PIDs {sorted(pids)}")

    def start(self, *, argv: list[str], cwd: Path, env: dict[str, str], stdout_path: Path) -> subprocess.Popen:
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        handle = stdout_path.open("ab", buffering=0)
        merged_env = os.environ.copy()
        merged_env.update(env)
        process = self._popen(
            argv,
            cwd=str(cwd),
            env=merged_env,
            stdin=subprocess.DEVNULL,
            stdout=handle,
            stderr=subprocess.STDOUT,
            shell=False,
            start_new_session=True,
        )
        self._log_handles[process.pid] = handle
        return process

    def close_log(self, pid: int) -> None:
        handle = self._log_handles.pop(pid, None)
        if handle is not None:
            handle.close()
```

- [ ] **Step 4: Implement Linux flock behind an injectable interface**

```python
class LinuxFlockHandle:
    def __init__(self, handle) -> None:
        self._handle = handle

    def close(self) -> None:
        import fcntl

        fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        self._handle.close()


class LinuxFlockBackend:
    def try_acquire(self, path: Path) -> LinuxFlockHandle | None:
        import fcntl

        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            return None
        handle.seek(0)
        handle.truncate()
        handle.write(f"pid={os.getpid()}\n")
        handle.flush()
        os.fsync(handle.fileno())
        return LinuxFlockHandle(handle)
```

Tests inject a fake backend, so Windows never imports `fcntl`. A Linux-only test guarded by `@unittest.skipUnless(sys.platform.startswith("linux"), "Linux flock")` acquires the same path twice and proves the second acquisition returns `None` until the first handle closes.

- [ ] **Step 5: Add exit-accounting and no-kill tests**

Test that the supervisor reports real exit codes and elapsed GPU seconds, maps nonzero exit to failure, closes log handles, and has no call path to `terminate`, `kill`, `taskkill`, or `pkill`.

- [ ] **Step 6: Run runtime tests**

Run:

```bash
python -m unittest tests.test_aaai27_queue_runtime -v
```

Expected: all tests pass on Windows with fakes; Linux locking remains covered by the later isolated smoke.

- [ ] **Step 7: Commit runtime supervision**

```bash
git add -- scripts/aaai27_queue/runtime.py tests/test_aaai27_queue_runtime.py
git commit -m "feat: supervise resident queue GPU tasks"
```

### Task 6: Persist controller state and recover without reruns

**Files:**
- Create: `scripts/aaai27_queue/controller.py`
- Create: `tests/test_aaai27_queue_controller.py`

- [ ] **Step 1: Write recovery and no-retry tests**

```python
# tests/test_aaai27_queue_controller.py
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for path in (REPO_ROOT / "scripts", REPO_ROOT / "tests"):
    sys.path.insert(0, str(path))

from aaai27_queue.controller import QueueController
from aaai27_queue.models import QueueManifest, TaskRecord
from aaai27_queue_testdata import make_manifest, make_task


class QueueControllerTests(unittest.TestCase):
    def test_orphaned_record_becomes_interrupted_without_retry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest = QueueManifest.from_dict(make_manifest([make_task(task_id="front.one")], run_root=str(root)))
            controller = QueueController.for_test(root, manifest, live_process=lambda pid, started: False)
            controller.save_record(TaskRecord("front.one", "running", 1, 123, "stamp", 0, "start", None, None, 0.0, None))
            controller.reconcile()
            self.assertEqual("interrupted_unverified", controller.load_records()["front.one"].status)
            self.assertEqual([], controller.ready_tasks())

    def test_stop_file_prevents_new_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest = QueueManifest.from_dict(make_manifest([make_task(task_id="front.one")], run_root=str(root)))
            controller = QueueController.for_test(root, manifest)
            (root / "state").mkdir(parents=True)
            (root / "state" / "STOP_AFTER_CURRENT").write_text("requested\n", encoding="utf-8")
            self.assertEqual([], controller.ready_tasks())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify controller import failure**

Run:

```bash
python -m unittest tests.test_aaai27_queue_controller -v
```

Expected: import error for `aaai27_queue.controller`.

- [ ] **Step 3: Implement record persistence and orphan reconciliation**

```python
# scripts/aaai27_queue/controller.py
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

from .models import GateSnapshot, QueueManifest, TaskRecord
from .scheduler import choose_ready_tasks
from .storage import append_event, atomic_write_json, load_json


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class QueueController:
    def __init__(self, root: Path, manifest: QueueManifest, *, live_process: Callable[[int, str], bool], free_disk_gib: Callable[[], float]) -> None:
        self.root = root
        self.manifest = manifest
        self._live_process = live_process
        self._free_disk_gib = free_disk_gib

    @classmethod
    def for_test(
        cls,
        root: Path,
        manifest: QueueManifest,
        live_process: Callable[[int, str], bool] = lambda pid, started: False,
        free_disk_gib: Callable[[], float] = lambda: 80.0,
    ) -> "QueueController":
        return cls(root, manifest, live_process=live_process, free_disk_gib=free_disk_gib)

    @property
    def records_dir(self) -> Path:
        return self.root / "state" / "tasks"

    def save_record(self, record: TaskRecord) -> None:
        atomic_write_json(self.records_dir / f"{record.task_id}.json", asdict(record))

    def load_records(self) -> dict[str, TaskRecord]:
        records: dict[str, TaskRecord] = {}
        if not self.records_dir.exists():
            return records
        for path in sorted(self.records_dir.glob("*.json")):
            record = TaskRecord(**load_json(path))
            records[record.task_id] = record
        return records

    def reconcile(self) -> None:
        for record in self.load_records().values():
            if record.status != "running" or record.pid is None or record.process_start_time is None:
                continue
            if self._live_process(record.pid, record.process_start_time):
                continue
            revised = replace(record, status="interrupted_unverified", ended_at=utc_now(), reason="orphaned running record")
            self.save_record(revised)
            append_event(self.root / "logs" / "events.jsonl", {"at": utc_now(), "task_id": record.task_id, "to": "interrupted_unverified"})

    def ready_tasks(self):
        if (self.root / "state" / "STOP_AFTER_CURRENT").exists():
            return []
        records = self.load_records()
        gpu_hours = sum(record.gpu_seconds for record in records.values()) / 3600.0
        busy = {record.gpu_id for record in records.values() if record.status == "running" and record.gpu_id is not None}
        return choose_ready_tasks(self.manifest, records, self.load_gates(), gpu_hours, self._free_disk_gib(), busy)

    def load_gates(self) -> GateSnapshot:
        e1_pass = self.root / "markers" / "RISK-02_PASS.json"
        e1_fail = self.root / "markers" / "RISK-02_FAIL.json"
        if e1_pass.exists() and e1_fail.exists():
            raise RuntimeError("ambiguous RISK-02 markers")
        e1 = "pass" if e1_pass.exists() else "fail" if e1_fail.exists() else None
        risk08_path = self.root / "markers" / "RISK-08_EXIT.json"
        risk08 = str(load_json(risk08_path)["exit"]) if risk08_path.exists() else None
        return GateSnapshot(e1, risk08)
```

- [ ] **Step 4: Implement one-tick dispatch with injected runtime**

Define the runtime boundary and implement `tick()` as follows:

```python
@dataclass(frozen=True)
class StartedChild:
    task_id: str
    pid: int
    process_start_time: str
    gpu_id: int | None


@dataclass(frozen=True)
class FinishedChild:
    task_id: str
    exit_code: int
    gpu_seconds: float
    artifacts_valid: bool
    reason: str | None


class RuntimeAdapter(Protocol):
    def observe_finished(self) -> list[FinishedChild]:
        raise NotImplementedError

    def start_task(self, task, allowed_gpu_ids: tuple[int, ...]) -> StartedChild | None:
        raise NotImplementedError


def tick(self, runtime: RuntimeAdapter) -> None:
    self.reconcile()
    records = self.load_records()
    for finished in runtime.observe_finished():
        previous = records[finished.task_id]
        passed = finished.exit_code == 0 and finished.artifacts_valid
        terminal = replace(
            previous,
            status="passed" if passed else "failed",
            ended_at=utc_now(),
            exit_code=finished.exit_code,
            gpu_seconds=finished.gpu_seconds,
            reason=None if passed else finished.reason or "artifact or process failure",
        )
        self.save_record(terminal)
        append_event(self.root / "logs" / "events.jsonl", {"at": utc_now(), "task_id": terminal.task_id, "to": terminal.status})

    if (self.root / "state" / "STOP_AFTER_CURRENT").exists():
        return
    for task in self.ready_tasks():
        child = runtime.start_task(task, self.manifest.gpu_ids)
        if child is None:
            continue
        running = TaskRecord(
            task_id=task.task_id,
            status="running",
            attempt=1,
            pid=child.pid,
            process_start_time=child.process_start_time,
            gpu_id=child.gpu_id,
            started_at=utc_now(),
            ended_at=None,
            exit_code=None,
            gpu_seconds=0.0,
            reason=None,
        )
        self.save_record(running)
        append_event(self.root / "logs" / "events.jsonl", {"at": utc_now(), "task_id": task.task_id, "to": "running", "gpu_id": child.gpu_id})
```

`runtime.start_task` must acquire flock and verify `nvidia-smi` before spawning. It returns `None` when no slot is safely available and never alters an existing process. Inject runtime, clock, and disk probes in tests.

- [ ] **Step 5: Add terminal-state tests**

Prove that nonzero exit blocks dependents; exit 0 with missing artifacts still fails; valid artifacts pass with GPU seconds; audit/stop exits dispatch no continuation; method pass requires E1 pass; attempt 1 is never recreated; and every state path stays below the queue root.

- [ ] **Step 6: Run controller tests**

Run:

```bash
python -m unittest tests.test_aaai27_queue_controller -v
```

Expected: all controller tests pass.

- [ ] **Step 7: Commit controller persistence**

```bash
git add -- scripts/aaai27_queue/controller.py tests/test_aaai27_queue_controller.py
git commit -m "feat: persist and recover resident queue state"
```

### Task 7: Add controller CLI, dry-run, status, stop, and no-op smoke

**Files:**
- Create: `scripts/aaai27_queue/cli.py`
- Create: `scripts/aaai27_resident_queue.py`
- Create: `tests/test_aaai27_queue_cli.py`

- [ ] **Step 1: Write CLI contract tests**

```python
# tests/test_aaai27_queue_cli.py
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENTRY = REPO_ROOT / "scripts" / "aaai27_resident_queue.py"


class QueueCliTests(unittest.TestCase):
    def test_status_is_read_only_when_state_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "queue"
            result = subprocess.run([sys.executable, str(ENTRY), "status", "--queue-root", str(root), "--json"], capture_output=True, text=True)
            self.assertEqual(2, result.returncode)
            self.assertFalse(root.exists())
            self.assertEqual("absent", json.loads(result.stdout)["status"])

    def test_request_stop_creates_only_stop_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "queue"
            root.mkdir()
            result = subprocess.run([sys.executable, str(ENTRY), "request-stop", "--queue-root", str(root)], capture_output=True, text=True)
            self.assertEqual(0, result.returncode)
            self.assertTrue((root / "state" / "STOP_AFTER_CURRENT").is_file())

    def test_smoke_writes_marker_without_training(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "smoke"
            result = subprocess.run([sys.executable, str(ENTRY), "smoke", "--queue-root", str(root)], capture_output=True, text=True)
            self.assertEqual(0, result.returncode)
            marker = json.loads((root / "markers" / "SMOKE_PASS.json").read_text(encoding="utf-8"))
            self.assertEqual("pass", marker["status"])
            self.assertFalse((root / "runs").exists())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify entry-point absence**

Run:

```bash
python -m unittest tests.test_aaai27_queue_cli -v
```

Expected: failures because `scripts/aaai27_resident_queue.py` does not exist.

- [ ] **Step 3: Implement the entry point**

```python
# scripts/aaai27_resident_queue.py
#!/usr/bin/env python3

from aaai27_queue.cli import main


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Implement exact CLI subcommands**

```python
# scripts/aaai27_queue/cli.py (parser contract)
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the AAAI-27 seed-100 resident queue.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "dry-run", "run", "status", "request-stop", "smoke"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--queue-root", type=Path, required=True)
        if name in {"validate", "dry-run", "run"}:
            sub.add_argument("--manifest", type=Path, required=True)
        if name == "dry-run":
            sub.add_argument("--e1-outcome", choices=("pending", "pass", "fail"), required=True)
            sub.add_argument("--risk08-exit", choices=("pending", "risk_gated_method", "audit_only", "submission_stop"), required=True)
        if name == "status":
            sub.add_argument("--json", action="store_true")
    return parser
```

`status` creates nothing. `request-stop` may create only `state/STOP_AFTER_CURRENT`. `smoke` rejects a nonempty root and writes only state, log, and `SMOKE_PASS.json`. `validate` and `dry-run` are read-only. `run` requires a validated manifest and controller lock.

- [ ] **Step 5: Add dry-run branch-count tests**

Use complete fake manifests to prove 14 pilot tasks for E1 pass, eight for E1 fail, no full task on audit, no continuation for audit/stop exits, and only approved seed-100 continuation for method pass.

- [ ] **Step 6: Run CLI tests**

Run:

```bash
python -m unittest tests.test_aaai27_queue_cli -v
```

Expected: all CLI tests pass.

- [ ] **Step 7: Commit CLI**

```bash
git add -- scripts/aaai27_queue/cli.py scripts/aaai27_resident_queue.py tests/test_aaai27_queue_cli.py
git commit -m "feat: add resident queue CLI"
```

### Task 8: Add idempotent remote tmux entry and shell-free local SSH launcher

**Files:**
- Create: `scripts/aaai27_remote_tmux_entry.py`
- Create: `scripts/launch_aaai27_seed100_queue.py`
- Create: `tests/test_launch_aaai27_seed100_queue.py`

- [ ] **Step 1: Write launcher safety tests**

```python
# tests/test_launch_aaai27_seed100_queue.py
import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    path = REPO_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class QueueLaunchTests(unittest.TestCase):
    def test_local_launcher_uses_ssh_argv_and_batch_mode(self) -> None:
        module = load("launch_aaai27_seed100_queue")
        argv = module.build_ssh_argv(
            host="zijian@172.18.0.40",
            remote_python="/data/Zijian/goal/PreferGrow/.venv/bin/python",
            remote_entry="/data/Zijian/goal/aaai27_bundle/scripts/aaai27_remote_tmux_entry.py",
            queue_root="/data/Zijian/goal/RecDemoRuns/aaai27_seed100_resident_20260710-220000",
            manifest="/data/Zijian/goal/RecDemoRuns/aaai27_seed100_resident_20260710-220000/queue/queue_seed100.json",
            session="aaai27_seed100_queue",
        )
        self.assertEqual(["ssh", "-n", "-T", "-o", "BatchMode=yes"], argv[:5])
        self.assertEqual("zijian@172.18.0.40", argv[5])
        self.assertIn("aaai27_remote_tmux_entry.py", argv[6])
        self.assertNotIn("kill-session", argv[6])

    def test_remote_entry_returns_matching_live_session(self) -> None:
        module = load("aaai27_remote_tmux_entry")
        runner = mock.Mock(return_value=subprocess.CompletedProcess([], 0, "", ""))
        result = module.ensure_session(
            session="aaai27_seed100_queue",
            queue_root=Path("/srv/queue"),
            manifest=Path("/srv/queue/queue/queue_seed100.json"),
            python_bin=Path("/opt/venv/bin/python"),
            controller_entry=Path("/srv/bundle/scripts/aaai27_resident_queue.py"),
            runner=runner,
            metadata={"session": "aaai27_seed100_queue", "queue_root": "/srv/queue", "manifest_sha256": "a" * 64},
            manifest_sha256="a" * 64,
        )
        self.assertEqual("already_running", result)
        self.assertFalse(any("kill-session" in item for call in runner.call_args_list for item in call.args[0]))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify both scripts are absent**

Run:

```bash
python -m unittest tests.test_launch_aaai27_seed100_queue -v
```

Expected: file-not-found failures for the two launcher scripts.

- [ ] **Step 3: Implement the local launcher**

```python
# scripts/launch_aaai27_seed100_queue.py (core command builder)
SSH_BASE = ["ssh", "-n", "-T", "-o", "BatchMode=yes"]


def build_ssh_argv(*, host: str, remote_python: str, remote_entry: str, queue_root: str, manifest: str, session: str) -> list[str]:
    remote_argv = [
        remote_python,
        remote_entry,
        "--queue-root", queue_root,
        "--manifest", manifest,
        "--session", session,
    ]
    return [*SSH_BASE, host, shlex.join(remote_argv)]
```

The CLI defaults to `zijian@172.18.0.40`, requires absolute queue/manifest/bundle paths, exposes `--connect-timeout`, calls `subprocess.run(argv, check=True)` only without `--print-only`, and contains no upload, delete, kill, or push action.

- [ ] **Step 4: Implement server-side tmux idempotency**

`scripts/aaai27_remote_tmux_entry.py` must verify `socket.gethostname() == "ubuntu"`, validate the manifest, compare `state/tmux_session.json` to the requested session/root/hash, return `already_running` for an exact live match, reject a mismatched live session, and return `terminal` without restart for terminal queues.

For a missing nonterminal session, execute this argv with `shell=False`:

```python
[
    "tmux", "new-session", "-d", "-s", session,
    str(python_bin), str(controller_entry),
    "run", "--queue-root", str(queue_root), "--manifest", str(manifest),
]
```

No function may invoke `tmux kill-session`.

- [ ] **Step 5: Add mismatch, terminal, path-space, and print-only tests**

Prove that a mismatched manifest fails, a terminal queue is not restarted, print-only makes no subprocess call, and the remote command remains one SSH argument when paths contain spaces.

- [ ] **Step 6: Run launcher tests**

Run:

```bash
python -m unittest tests.test_launch_aaai27_seed100_queue -v
```

Expected: all launcher tests pass.

- [ ] **Step 7: Commit launchers**

```bash
git add -- scripts/aaai27_remote_tmux_entry.py scripts/launch_aaai27_seed100_queue.py tests/test_launch_aaai27_seed100_queue.py
git commit -m "feat: launch seed100 queue idempotently"
```

### Task 9: Write the runbook and verify a local no-op lifecycle

**Files:**
- Create: `docs/runbooks/2026-07-10-aaai27-seed100-resident-queue.md`
- Modify: `tests/test_aaai27_queue_cli.py`

- [ ] **Step 1: Add a no-op lifecycle test**

Add `test_smoke_status_and_stop_lifecycle` that invokes `smoke`, reads `status --json`, invokes `request-stop`, reads status again, and asserts:

```python
self.assertEqual("smoke_pass", first_status["status"])
self.assertTrue(second_status["stop_requested"])
self.assertFalse((root / "runs").exists())
self.assertEqual([], list(root.rglob("*.pth")))
```

- [ ] **Step 2: Run the lifecycle test**

Run:

```bash
python -m unittest tests.test_aaai27_queue_cli.QueueCliTests.test_smoke_status_and_stop_lifecycle -v
```

Expected: pass without SSH, tmux, GPU, checkpoint, or training activity.

- [ ] **Step 3: Write the operator runbook**

Create `docs/runbooks/2026-07-10-aaai27-seed100-resident-queue.md` with exactly one H1 and these H2 sections: authorization gate, prerequisites, read-only validation, branch dry runs, print-only launch, authorized start, read-only status, safe stop, recovery, and evidence handoff.

Use this executable variable block before commands so readers never copy unresolved operands:

```bash
QUEUE_ROOT=/data/Zijian/goal/RecDemoRuns/aaai27_seed100_resident_20260710-220000
MANIFEST="$QUEUE_ROOT/queue/queue_seed100.json"
BUNDLE=/data/Zijian/goal/aaai27_seed100_bundle_20260710
REMOTE_PYTHON=/data/Zijian/goal/PreferGrow/.venv/bin/python
SESSION=aaai27_seed100_queue
```

Document all three RISK-08 dry-run outcomes, same-root recovery, `interrupted_unverified`, no automatic retry, status paths, and the distinction between read-only commands and launch mutations.

- [ ] **Step 4: Verify every referenced local file exists**

Run:

```powershell
$paths = @(
  'scripts\aaai27_resident_queue.py',
  'scripts\aaai27_remote_tmux_entry.py',
  'scripts\launch_aaai27_seed100_queue.py',
  'docs\superpowers\specs\2026-07-10-aaai27-seed100-resident-queue-design.md'
)
$paths | ForEach-Object { if (-not (Test-Path -LiteralPath $_)) { throw "missing $_" } }
```

Expected: exit 0 with no missing-path error.

- [ ] **Step 5: Commit the runbook**

```bash
git add -- docs/runbooks/2026-07-10-aaai27-seed100-resident-queue.md tests/test_aaai27_queue_cli.py
git commit -m "docs: add seed100 resident queue runbook"
```

### Task 10: Run full verification and record deployment blockers

**Files:**
- Modify only if verification reveals a defect in files created by this plan

- [ ] **Step 1: Run the focused orchestration suite**

Run:

```powershell
python -m unittest tests.test_aaai27_queue_models tests.test_aaai27_queue_validation tests.test_aaai27_queue_storage tests.test_aaai27_queue_scheduler tests.test_aaai27_queue_runtime tests.test_aaai27_queue_controller tests.test_aaai27_queue_cli tests.test_launch_aaai27_seed100_queue -v
```

Expected: all focused tests pass with zero failures and zero errors.

- [ ] **Step 2: Run existing launcher regressions**

Run:

```powershell
python -m unittest tests.test_launch_beauty_text_side_tmux tests.test_launch_sprint07_control_tmux tests.test_retry_sprint07_when_l20_ready -v
```

Expected: all existing launcher tests pass; new files do not alter old launchers.

- [ ] **Step 3: Run syntax and whitespace checks**

Run:

```powershell
python -m compileall -q scripts\aaai27_queue scripts\aaai27_resident_queue.py scripts\aaai27_remote_tmux_entry.py scripts\launch_aaai27_seed100_queue.py
git diff --check
```

Expected: both commands exit 0.

- [ ] **Step 4: Inspect the scoped change set**

Run:

```powershell
git status --short -- scripts/aaai27_queue scripts/aaai27_resident_queue.py scripts/aaai27_remote_tmux_entry.py scripts/launch_aaai27_seed100_queue.py tests/test_aaai27_queue_*.py tests/test_launch_aaai27_seed100_queue.py docs/runbooks/2026-07-10-aaai27-seed100-resident-queue.md
git diff --stat -- scripts/aaai27_queue scripts/aaai27_resident_queue.py scripts/aaai27_remote_tmux_entry.py scripts/launch_aaai27_seed100_queue.py tests docs/runbooks/2026-07-10-aaai27-seed100-resident-queue.md
```

Expected: only plan-named files appear in the scoped status and diff.

- [ ] **Step 5: Record mandatory blockers before remote launch**

The implementation handoff must report the state of every item below:

- RISK scientific adapters and their tests;
- clean pinned execution bundle;
- complete real queue manifest with immutable hashes;
- DiffRec identity and memory audit if RISK-11 is enabled;
- remote no-op tmux smoke authorization;
- remote bundle synchronization authorization;
- experiment-launch authorization.

No controller unit test, local smoke, or printed SSH command satisfies these deployment gates.

- [ ] **Step 6: Commit verification corrections only when needed**

If Steps 1–4 required corrections, run:

```powershell
git add -- scripts/aaai27_queue scripts/aaai27_resident_queue.py scripts/aaai27_remote_tmux_entry.py scripts/launch_aaai27_seed100_queue.py tests/test_aaai27_queue_*.py tests/test_launch_aaai27_seed100_queue.py docs/runbooks/2026-07-10-aaai27-seed100-resident-queue.md
git commit -m "test: verify seed100 resident queue"
```

If no correction was required, do not create an empty commit.

## ✅ Self-review checklist

- [ ] Every approved E1 and RISK-08 branch has a scheduler test.
- [ ] E1 fail schedules eight audit tasks and zero `risk_gated_full` tasks.
- [ ] Method pass is impossible without E1 pass.
- [ ] Seeds 101/102, RISK-12, DiffuRec, retries, and partial classic baselines fail validation.
- [ ] The 168 GPU-hour and 40 GiB limits are exact assertions.
- [ ] Stop and recovery never kill or automatically retry a task.
- [ ] Status is read-only; smoke creates no `runs/` directory.
- [ ] The remote entry never uses `tmux kill-session`.
- [ ] The local launcher has SSH argv and print-only paths.
- [ ] No step deploys, synchronizes, starts remote tmux, or launches science.
- [ ] Final handoff distinguishes orchestration readiness from experiment readiness.
