# RISK-04--RISK-08 Queue-Safe Adapters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze and validate dated, fail-closed queue inputs for the RISK-04 corruption sweep, RISK-05 prospective protocol, RISK-06/RISK-07 Beauty/Steam pilot, and RISK-08 decision without launching training.

**Architecture:** Keep the existing train-only risk, corruption, preregistration, and queue model primitives. Add a thin queue-safe orchestration layer that binds every artifact to one absent dated root, verifies hashes and E1 provenance, emits a controller-valid 14-task E1-pass/eight-task audit manifest, and writes an atomic RISK-08 exit marker only from artifact-backed pilot reports. Each public adapter refuses existing output roots, validation/test inputs, retries, seed changes, destructive arguments, and ambiguous markers.

**Tech Stack:** Python 3.11, pathlib, JSON/JSONL, SHA-256, NumPy/PyTorch, unittest/pytest, existing `aaai27_queue` models and validation.

---

### Task 1: Specify the queue-safe contracts with failing tests

**Files:**
- Create: `tests/test_risk04_08_queue_safe_adapters.py`
- Read-only reference: `docs/superpowers/specs/2026-07-10-aaai27-evidence-risk-rescue-design.md`, `docs/superpowers/specs/2026-07-10-aaai27-seed100-resident-queue-design.md`

- [ ] **Step 1: Write the failing tests**

  Cover: dated-root rejection when the root exists; RISK-04 bank manifest binding (seed 100, exact 0/20/40/60/80/100 levels, train-only source, no test/validation path); RISK-05 binding to preflight and E1 marker hashes with no test metrics; RISK-06/RISK-07 complete 14-task pass branch and eight-task audit branch; queue validation of generated manifests; RISK-08 rejection of missing/duplicate/mismatched artifact provenance and atomic immutable output; and the experiment-manual presence of the explicit E1-pass/no-training boundary.

- [ ] **Step 2: Run the focused test file to verify RED**

  Run `python -m pytest tests/test_risk04_08_queue_safe_adapters.py -q`. It must fail because the new queue-safe module and dated builders do not yet exist.

### Task 2: Implement immutable RISK-04 bank and preflight adapter

**Files:**
- Create: `scripts/aaai27_adapters/risk04_08.py`
- Create: `scripts/build_risk04_corruption_banks.py`
- Create: `scripts/validate_risk04_banks.py`
- Modify: `scripts/aaai27_adapters/bank_builder.py` only if a narrowly tested metadata/provenance hook is required

- [ ] **Step 1: Add `build_risk04_bundle`**

  Require an absent dated output root, exactly Beauty and Steam, train-only transition paths, clean embedding paths, corruption seed 100, six frozen levels, popularity-stratified permutation, and explicit source hashes. Build each level under `<root>/banks/<dataset>/level-XXX`, reuse `build_corruption_bank`, write a manifest with algorithm/strata/row-norm/selected-count/hash provenance, and write a fail-closed preflight report. Never read validation/test files and never delete an old root.

- [ ] **Step 2: Add `validate_risk04_bundle`**

  Recompute every bank and manifest hash, assert all six levels/datasets, seed 100, train-only paths, exact item mapping and row norms, and return a machine-readable pass report. Reject a missing or modified bank, a level mismatch, a path containing validation/test, or any existing output collision.

- [ ] **Step 3: Add the CLI wrappers**

  `build_risk04_corruption_banks.py` accepts one dated config and emits the bundle manifest; `validate_risk04_banks.py` accepts the dated bundle and emits JSON. Both use argv-only parsing and never launch a trainer.

- [ ] **Step 4: Run the focused tests to verify GREEN**

  Run `python -m pytest tests/test_risk04_08_queue_safe_adapters.py -q` and the existing front-gate tests. Confirm that only adapter tests execute and no GPU process is started.

### Task 3: Implement RISK-05 freeze and RISK-06/RISK-07 dated queue manifest

**Files:**
- Modify: `scripts/aaai27_adapters/risk04_08.py`
- Create: `scripts/build_risk05_preregistration.py`
- Create: `scripts/build_risk0607_pilot_manifest.py`

- [ ] **Step 1: Add `build_risk05_bundle`**

  Bind the validated RISK-04 bundle hash, preflight hash, E1 marker hash/source revision, fixed seed/levels/metrics/thresholds, evaluator and selector versions, and the no-test-metric rule. Emit `protocol/risk05_preregistration.json`, `markers/RISK-05_PASS.json` or `RISK-05_STOP.json`, and a hash manifest under a new dated root; fail if the root exists or the E1 marker is not a terminal pass/fail marker.

- [ ] **Step 2: Add `build_risk0607_manifest`**

  Create a new queue root with protocol copies and source/hash manifest, call the existing pilot task builder, bind all twelve bank hashes and the frozen RISK-05 hash, add `markers/RISK-02_PASS.json` (and the mutually exclusive fail marker schema), and validate the resulting `QueueManifest`. The pass branch must contain exactly 14 tasks; the audit branch exactly eight; every task has seed 100, `max_attempts=1`, `failure_policy=fail_closed`, safe argv, unique run directory below the root, evaluator/selector references, and no DiffuRec/BERT4Rec/destructive flag. Manifest creation never starts a queue.

- [ ] **Step 3: Run queue validation tests**

  Run the focused adapter tests plus `python -m pytest tests/test_aaai27_queue_validation.py tests/test_aaai27_queue_scheduler.py -q`. Confirm that generated manifests pass the existing controller validator and malicious mutations fail closed.

### Task 4: Implement artifact-backed RISK-08 decision adapter

**Files:**
- Modify: `scripts/aaai27_adapters/risk04_08.py`
- Create: `scripts/run_risk08_decision.py`

- [ ] **Step 1: Add `run_risk08_decision`**

  Load exactly one E1 marker, exactly one RISK-05 marker, the queue manifest, a pilot report, and one artifact manifest per completed task. Verify marker hashes/source revision, branch/task-ID completeness, artifact paths remain below the dated root, artifact hashes match, and metrics are not manually supplied without provenance. Evaluate the frozen phenomenon criteria from RISK-05 without changing thresholds. Write exactly one atomic `markers/RISK-08_EXIT.json`; on any hard stop write a terminal `submission_stop` marker with the reason, and never launch continuation.

- [ ] **Step 2: Test all exits and failures**

  Verify E1-pass + phenomenon pass yields `risk_gated_method`, E1-fail + phenomenon pass yields `audit_only`, otherwise `submission_stop`; verify missing/duplicate/stale/hash-mismatched inputs and a second write are rejected.

### Task 5: Land the dated experiment manual and ledger rows

**Files:**
- Create: `docs/runbooks/2026-07-11-e1-pass-risk04-08-experiment-manual.md`
- Modify: `issues/2026-07-10_22-34-15-aaai27-seed100-resident-queue-execution.csv`

- [ ] **Step 1: Write the manual**

  Document the existing E1 R12 evidence, server/GPU read-only preflight, RISK-04 generation and severe-corruption gate, RISK-05 freeze, dated RISK-06/RISK-07 manifest creation, controller `validate`/`dry-run`, the authorization boundary before training, pilot monitoring, artifact validation, RISK-08 exits, method-pass unlock criteria, recovery/no-go procedures, audit commands, and the required reproducibility sentence about validation-only selection and development-time test logging.

- [ ] **Step 2: Append dated ledger rows**

  Add rows for RISK-04, RISK-05, RISK-06, RISK-07, and RISK-08 using the existing 19-column schema, recording the dated bundle/manifest paths, hashes after generation, `no_training_started=true`, acceptance criteria, and the next issue. Do not create or launch an experiment outside this ledger.

### Task 6: Full verification and handoff

**Files:**
- No production files beyond the above.

- [ ] **Step 1: Run static and focused verification**

  Run `python -m compileall -q scripts model graph_lib.py losses.py`, `git diff --check`, the focused adapter tests, and the complete existing 139-test regression suite. Record any pre-existing environment-only skips/failures separately.

- [ ] **Step 2: Inspect the diff and confirm no remote launch**

  Verify only dated local artifacts/manual/ledger/code/tests changed; no SSH, tmux, GPU launch, dataset mutation, frozen-artifact overwrite, or training command was executed.

- [ ] **Step 3: Commit and push only after fresh verification**

  Commit the implementation and documentation with a dated message, push the current branch, and report exact paths and test output. Do not claim RISK-08 method-pass until a future pilot artifact report exists.

---

## Self-review checklist

- RISK-04 through RISK-08 requirements and hard stops map to Tasks 2--4.
- The queue contract, 14/8 branch sizes, seed 100, no retry, one GPU process, and no-training boundary are explicit.
- All output roots are dated and immutable; no old artifact is deleted or relabeled.
- The manual and ledger are part of the same auditable change.
- No step authorizes GPU training; authorization remains a later explicit boundary.
