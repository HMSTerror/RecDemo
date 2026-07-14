# Continuation GPU Sharing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow the authorized r7 continuation queue to run at most two GPU training processes per L20 when at least 8192 MiB remains free, without changing frozen scientific contracts.

**Architecture:** Keep the manifest and queue policy immutable. Extend the reusable runtime with opt-in per-GPU slot capacity, memory probing, external-process accounting, descendant-aware local reservations, and exclusive-task handling; configure only the continuation CLI to opt in. Extend candidate selection with an explicit slot budget while preserving its old default behavior.

**Tech Stack:** Python 3, pytest/unittest, `nvidia-smi`, Linux `/proc`, flock, tmux, SSH.

---

### Task 1: Specify candidate-slot behavior

**Files:**
- Modify: `tests/test_aaai27_queue_scheduler.py`
- Modify: `scripts/aaai27_queue/scheduler.py`

- [ ] Add a failing test showing an explicit four-slot budget can select four GPU candidates while the legacy call still selects one task per free GPU.
- [ ] Run `python -m pytest tests/test_aaai27_queue_scheduler.py -q` and verify the new test fails because the argument is absent.
- [ ] Add an optional keyword-only `available_gpu_slots` argument and use it only when supplied.
- [ ] Re-run the scheduler tests and verify all pass.

### Task 2: Add memory and process-slot runtime gates

**Files:**
- Modify: `tests/test_aaai27_queue_runtime.py`
- Modify: `scripts/aaai27_queue/runtime.py`

- [ ] Add failing tests for one external plus one local task, the third-task block, insufficient memory, probe failure, two independent GPUs, local descendant de-duplication, and exclusive tasks.
- [ ] Run the focused tests and confirm each failure is caused by missing sharing support.
- [ ] Add `probe_gpu_free_memory_mib`, Linux descendant discovery, opt-in slot locks, and fail-closed capacity checks. Keep constructor defaults equivalent to the old exclusive behavior.
- [ ] Re-run the focused runtime tests and the old runtime suite.

### Task 3: Opt continuation into two-slot scheduling

**Files:**
- Modify: `tests/test_aaai27_continuation_controller.py`
- Modify: `tests/test_aaai27_method_pass_continuation_cli.py`
- Modify: `scripts/aaai27_continuation/controller.py`
- Modify: `scripts/aaai27_method_pass_continuation.py`

- [ ] Add failing tests proving the continuation controller offers four candidates and the production CLI constructs `QueueRuntime` with two slots and 8192 MiB reserve.
- [ ] Run the focused tests and verify RED.
- [ ] Add the controller slot-budget option and configure the CLI constants. Do not change prepare output or manifest schema.
- [ ] Run the focused continuation and CLI suites and verify GREEN.

### Task 4: Verify safety invariants and document deployment

**Files:**
- Create: `docs/reports/data/2026-07-14-continuation-gpu-sharing/LOCAL_TEST_REPORT.md`
- Create: `docs/reports/data/2026-07-14-continuation-gpu-sharing/SERVER_SWITCH_REPORT.md`

- [ ] Run the complete queue and continuation test suites, `compileall`, `git diff --check`, and forbidden-string scan.
- [ ] Record exact commands, counts, revision and hashes in the local report.
- [ ] Verify r7 and continuation queue manifest hashes before deployment.
- [ ] Build and transfer a new immutable source bundle, run Linux focused and full tests there, and record its source manifest SHA.
- [ ] At a safe point, stop only the old continuation controller, start one new detached continuation controller, and verify r7/root processes remain unchanged.
- [ ] Confirm the new controller remains waiting while RISK-08 is absent and creates zero continuation scientific records.
- [ ] Record PID, tmux session, paths, hashes, GPU state, disk state and rollback command in the server report.

### Task 5: Interpret current r7 evidence

**Files:**
- Update after 14/14 only: dated r7 paper evidence artifacts produced by the existing frozen builder.

- [ ] Read all completed best summaries and artifact manifests without modifying r7.
- [ ] Produce a partial table for completed arms; label running arms pending.
- [ ] Compare only against the frozen RISK-08 phenomenon criteria.
- [ ] After 14/14, allow the existing finalizer to emit the sole RISK-08 terminal marker and report its exact exit.

