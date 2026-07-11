# Method-Pass Continuation Adapters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline execution is approved for this continuation task). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a queue-safe, seed-100-only continuation manifest for RISK-13, RISK-14, RISK-10, and conditionally audited RISK-11 without launching training or weakening the resident-queue gates.

**Architecture:** `continuation_adapters.py` will consume an already frozen pilot manifest plus immutable gate/audit bindings and append only `phase="continuation"`, `branch="method_pass"` tasks. It will emit a dated metadata manifest and a QueueManifest-compatible JSON; the existing controller remains the only component allowed to launch work. Validation will enforce exact RISK-13/RISK-14 matrices, four-domain atomic groups, DiffRec audit gating, and the 168 GPU-hour ceiling.

**Tech Stack:** Python 3.13, dataclasses/JSON, existing `QueueManifest`/`TaskSpec`, `pytest`/`unittest`, SHA-256 provenance, `apply_patch`.

---

### Task 1: Specify the continuation contract with failing tests

**Files:**
- Create: `tests/test_method_pass_continuation_adapters.py`
- Modify: `scripts/aaai27_queue/validation.py` only after RED is observed

- [ ] **Step 1: Write tests for exact matrices and common safety fields**

  The tests must construct a synthetic base pilot manifest and protocol with four domains (`Steam`, `ML1M`, `Beauty`, `ATG`). They assert that a method-pass build creates eight RISK-13 tasks (host/full per domain), the frozen RISK-14 control tasks, twelve RISK-10 tasks (SASRec/Caser/GRURec × four domains), all seed 100, `max_attempts=1`, `failure_policy="fail_closed"`, unique dated run roots, common evaluator/selector, and no destructive argv.

- [ ] **Step 2: Write tests for DiffRec audit fail-closed behavior**

  A missing, failed, or hash-mismatched identity/memory audit must produce zero RISK-11 GPU tasks and a manifest metadata status of `diffrec_blocked`; a passing audit with the exact four-domain identity and memory fields must produce exactly four RISK-11 tasks in one atomic group.

- [ ] **Step 3: Write tests for gate/dependency/budget behavior**

  The builder must reject absent or non-`risk_gated_method` RISK-08 markers, an E1 marker other than PASS, a changed RISK-05 preregistration hash, non-train-only RISK-14 condition selection, and a high forecast over 168 GPU-hours. Continuation tasks must depend on an in-manifest method-pass gate task whose required markers bind E1 and RISK-08.

- [ ] **Step 4: Run the focused tests and observe the expected RED**

  Run `python -m pytest tests/test_method_pass_continuation_adapters.py -q`.

  Expected: collection or assertion failures because the continuation adapter and continuation validation do not yet exist. Do not implement production code before this RED is recorded.

### Task 2: Implement the pure continuation adapter

**Files:**
- Create: `scripts/aaai27_adapters/continuation_adapters.py`
- Create: `scripts/build_method_pass_manifest.py`
- Modify: `scripts/aaai27_adapters/__init__.py` only if a public export is needed

- [ ] **Step 1: Implement immutable input and audit helpers**

  Add strict JSON/hash helpers that require dated, absent output roots; validate the E1 PASS marker (`random_seed=100`), RISK-08 exit exactly `risk_gated_method`, and RISK-05 preregistration hash. Add a read-only DiffRec audit function that accepts only `status="pass"`, `model_identity="DiffRec"`, an explicit source revision, config hash, split hash, and finite memory estimates under the protocol limit; any failure returns a blocked audit result and never raises a path toward GPU tasks.

- [ ] **Step 2: Implement RISK-13 matched host/full task generation**

  Generate one host and one full task for each of Steam, ML1M, Beauty, and ATG. Each pair shares a `matched_group`, differs only in the approved full-method toggle, uses `seed=100`, the common evaluator/validation selector, and an isolated run directory under the dated root. Mark the seed-100 wave as `partial_seed100` in metadata.

- [ ] **Step 3: Implement RISK-14 frozen train-only controls**

  Require a protocol-supplied train-only condition-choice hash and exactly the frozen `high_risk`/`low_risk` control arms. Generate only the approved controls, with no validation/test values in the selection payload and no adaptive/backoff/rescue fields.

- [ ] **Step 4: Implement RISK-10 and conditional RISK-11 four-domain groups**

  Generate SASRec, Caser, and GRURec groups over all four domains with one `atomic_group` per model. Generate DiffRec over all four domains only when the identity/memory audit passes; never generate DiffuRec, BERT4Rec, seed 101/102, retries, or partial baseline groups.

- [ ] **Step 5: Implement manifest assembly and CLI**

  Append continuation tasks to the immutable base pilot task list (without modifying the base artifact), prepend a CPU `contract_gate` task for method-pass markers, bind all source/code/config/split/bank/evaluator/selector hashes, compute the frozen high forecast, and write the dated queue JSON plus a self-hashed metadata JSON. The CLI must be print/build-only and must not call SSH, tmux, subprocess training, or deletion.

### Task 3: Extend queue validation for continuation-only contracts

**Files:**
- Modify: `scripts/aaai27_queue/validation.py`
- Test: `tests/test_method_pass_continuation_adapters.py`

- [ ] **Step 1: Add continuation matrix checks**

  Keep the existing exact 14/8 pilot checks when pilot tasks are present. For continuation tasks, require `branch="method_pass"`, `phase="continuation"`, RISK-13 exact eight-task host/full matrix, RISK-14 frozen control matrix, RISK-10 all-four groups, and RISK-11 all-four DiffRec only.

- [ ] **Step 2: Enforce continuation gate dependencies and budget**

  Require a method-pass contract gate task, require every GPU continuation task to depend on it (or on a transitive gate dependency), and reject any manifest whose sum of `gpu_hours_high` exceeds 168. Preserve the existing seed, retry, destructive-token, path, and DiffuRec/BERT4Rec rejection rules.

- [ ] **Step 3: Run the focused tests and the queue regression suite**

  Run `python -m pytest tests/test_method_pass_continuation_adapters.py tests/test_aaai27_queue_validation.py tests/test_aaai27_queue_scheduler.py -q` and confirm all continuation tests are green without changing the pilot behavior.

### Task 4: Document and reconcile evidence

**Files:**
- Modify: `docs/runbooks/2026-07-11-e1-pass-risk04-08-experiment-manual.md`
- Modify: `issues/2026-07-10_22-34-15-aaai27-seed100-resident-queue-execution.csv`
- Create: `docs/reports/data/2026-07-11-method-pass-continuation-adapter/adapter_manifest.json`
- Create: `docs/reports/data/2026-07-11-method-pass-continuation-adapter/adapter_manifest.md`

- [ ] **Step 1: Add the method-pass operating section**

  State that this adapter is local/build-only, requires a real artifact-backed RISK-08 marker, and that RISK-13 seed 100 remains a partial observation. Record the exact audit and launch hard stops.

- [ ] **Step 2: Write a dated self-hashed adapter manifest**

  Record source revision, test command/output, input hashes, task counts, audit outcome, forecast, and the explicit `training_started=false` boundary. Recompute and verify every listed hash.

- [ ] **Step 3: Update ADAPT-04 ledger evidence**

  Use `apply_patch` to change only the ADAPT-04 row to completed after all tests pass, with commit ID, manifest path/hash, and the statement that no remote training was started. Do not change historical tar/log files or the unrelated older ledger.

### Task 5: Fresh verification and commit

**Files:**
- All files above

- [ ] **Step 1: Run the complete relevant regression suite**

  Run `python -m pytest tests/test_method_pass_continuation_adapters.py tests/test_risk04_08_queue_safe_adapters.py tests/test_aaai27_queue_*.py -q`.

- [ ] **Step 2: Run static checks**

  Run `python -m compileall -q scripts/aaai27_adapters scripts/aaai27_queue scripts/build_method_pass_manifest.py` and `git diff --check`.

- [ ] **Step 3: Inspect scope and confirm no launch**

  Verify `git status --short` contains no edits to historical tar/log artifacts and that tests/CLI only create temporary synthetic roots. Confirm no SSH/tmux/GPU process was invoked.

- [ ] **Step 4: Commit and push**

  Commit with `feat: add method-pass continuation adapters`, then push the current branch. Report the commit and exact verification output; do not claim method-pass evidence or training completion.
