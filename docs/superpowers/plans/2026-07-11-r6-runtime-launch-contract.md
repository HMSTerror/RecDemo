# R6 runtime launch-contract implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Subagent execution is disabled for this run; all RED/GREEN evidence is collected inline.

**Goal:** Build a new revision whose seed-100 pilot tasks run from isolated directories, can only use GPU1, launch through a complete SSH/tmux argument chain, and pass a real Hydra pre-step probe before controller creation.

**Architecture:** Keep immutable code identity in absolute argv paths and move all relative GPU runtime state into `task.run_dir`. Treat `QueueManifest.gpu_ids` as the mechanical allowlist, retain the verified physical-GPU probe while making ambiguous output fail closed, and add a narrowly scoped `training.startup_probe_only` exit after state construction but before dataloaders or training. The method-pass continuation adapter follows the same GPU1-only contract; the CPU contract gate is the explicit source-cwd exception because it has no GPU slot.

**Tech Stack:** Python 3.10, `unittest`, Hydra/OmegaConf, PyTorch, Linux `nvidia-smi`, SSH/tmux, JSON artifacts.

---

### Task 1: Bind pilot cwd and GPU allowlist

**Files:**

- Modify: `tests/test_r6_launch_contract.py`
- Modify: `scripts/aaai27_adapters/pilot_adapters.py:91-123,220-233`
- Modify: `scripts/aaai27_adapters/risk04_08.py:515-576`
- Modify: `scripts/aaai27_adapters/continuation_adapters.py:154-272,390`
- Modify: `scripts/aaai27_queue/validation.py:61-123,284-313`
- Modify: `tests/aaai27_queue_testdata.py:6-65`
- Modify: `tests/test_method_pass_continuation_adapters.py:35-220`

- [x] **Step 1: Write failing adapter and validator tests**

```python
def test_pilot_manifest_copies_explicit_gpu1_allowlist(self):
    manifest = build_pilot_manifest(make_protocol(gpu_ids=[1]))
    self.assertEqual([1], manifest["gpu_ids"])

def test_pilot_gpu_tasks_run_from_their_isolated_run_dirs(self):
    manifest = build_pilot_manifest(make_protocol(gpu_ids=[1]))
    self.assertTrue(all(task["cwd"] == task["run_dir"] for task in manifest["tasks"]))

def test_validator_rejects_gpu_task_cwd_that_differs_from_run_dir(self):
    task = make_task(cwd="/srv/bundle/source")
    with self.assertRaisesRegex(ManifestError, "cwd must equal run_dir"):
        validate_manifest(decoded([task], gpu_ids=[1]))
```

- [x] **Step 2: Run tests and confirm RED**

Run: `python -m unittest tests.test_r6_launch_contract -v`

Expected: failures showing hard-coded `[0,1]`, source-root `cwd`, and missing cwd equality rejection.

- [x] **Step 3: Implement the minimum manifest contract**

```python
"cwd": run_dir,
...
"gpu_ids": list(protocol["gpu_ids"]),
```

Validate `gpu_ids` as a nonempty unique list of nonnegative integers, require r6 protocol `[1]`, and reject GPU `cwd != run_dir`.

- [x] **Step 4: Run focused tests and confirm GREEN**

Run: `python -m unittest tests.test_r6_launch_contract tests.test_aaai27_queue_validation tests.test_risk04_08_queue_safe_adapters tests.test_aaai27_front_gate_adapters -v`

Expected: all tests pass; Windows-only `flock` skip remains permitted.

### Task 2: Contain runtime cwd and fail-close ambiguous GPU rows

**Files:**

- Modify: `tests/test_aaai27_queue_runtime.py:57-226`
- Modify: `scripts/aaai27_queue/runtime.py:76-90,206-230`

- [x] **Step 1: Write failing runtime tests**

```python
def test_gpu_probe_unknown_row_is_fail_closed(self):
    runner = mock.Mock(return_value=subprocess.CompletedProcess([], 0, "N/A\n", ""))
    with self.assertRaisesRegex(GpuBusyError, "unrecognized"):
        probe_gpu_pids(1, runner=runner)

def test_runtime_creates_contained_task_cwd_before_spawn(self):
    task = TaskSpec.from_dict(make_task(cwd=str(run_dir), run_dir=str(run_dir)))
    runtime.start_task(task, (1,))
    self.assertTrue(run_dir.is_dir())
```

- [x] **Step 2: Run tests and confirm RED**

Run: `python -m unittest tests.test_aaai27_queue_runtime.QueueRuntimeTests.test_gpu_probe_unknown_row_is_fail_closed tests.test_aaai27_queue_runtime.QueueRuntimeTests.test_runtime_creates_contained_task_cwd_before_spawn -v`

Expected: no exception for `N/A` and absent cwd after spawn mock.

- [x] **Step 3: Implement containment and strict parsing**

```python
rows = [line.strip() for line in result.stdout.splitlines() if line.strip()]
if any(not row.isdigit() or int(row) <= 0 for row in rows):
    raise GpuBusyError(f"GPU probe returned unrecognized rows for {gpu_id}: {rows!r}")

cwd = require_within(Path(task.cwd), self.queue_root)
cwd.mkdir(parents=True, exist_ok=True)
```

- [x] **Step 4: Run runtime suite and confirm GREEN**

Run: `python -m unittest tests.test_aaai27_queue_runtime -v`

Expected: all runtime tests pass with one expected Windows `flock` skip.

### Task 3: Complete the SSH/tmux launcher argument chain

**Files:**

- Modify: `tests/test_launch_aaai27_seed100_queue.py:22-53`
- Modify: `scripts/launch_aaai27_seed100_queue.py:12-103`

- [x] **Step 1: Write failing launcher integration test**

```python
argv = module.build_ssh_argv(
    ...,
    python_bin="/opt/venv/bin/python3",
    controller_entry="/srv/r6/scripts/aaai27_resident_queue.py",
)
self.assertIn("--python-bin /opt/venv/bin/python3", argv[-1])
self.assertIn("--controller-entry /srv/r6/scripts/aaai27_resident_queue.py", argv[-1])
```

- [x] **Step 2: Run test and confirm RED**

Run: `python -m unittest tests.test_launch_aaai27_seed100_queue.QueueLaunchTests.test_local_launcher_forwards_controller_python_and_entry -v`

Expected: `build_ssh_argv` rejects the new keywords or omits the flags.

- [x] **Step 3: Add required parameters through parser, launcher, and remote argv**

```python
remote_argv.extend([
    "--python-bin", python_bin,
    "--controller-entry", controller_entry,
])
```

- [x] **Step 4: Run launcher suite and confirm GREEN**

Run: `python -m unittest tests.test_launch_aaai27_seed100_queue -v`

Expected: all launcher and remote-entry tests pass.

### Task 4: Add the real Hydra pre-step probe

**Files:**

- Modify: `configs/config.yaml:11-30`
- Modify: `single_train.py:159-215`
- Modify: `scripts/aaai27_queue/validation.py:85-110`
- Create: `tests/test_single_train_startup_probe.py`

- [x] **Step 1: Write failing main-boundary tests**

```python
def test_startup_probe_returns_before_dataloader_and_writes_scoped_artifact(self):
    with mock.patch.object(single_train.data, "get_seqdataloader") as loaders:
        single_train.main.__wrapped__(cfg)
    loaders.assert_not_called()
    payload = json.loads((run_dir / "startup_probe.json").read_text())
    self.assertEqual(0, payload["step"])
    self.assertEqual(0, payload["optimizer_state_entries"])

def test_queue_manifest_rejects_startup_probe_override(self):
    task = make_task(argv=["python", "/srv/source/single_train.py", "training.startup_probe_only=True"])
    with self.assertRaisesRegex(ManifestError, "startup probe"):
        validate_manifest(decoded([task], gpu_ids=[1]))
```

- [x] **Step 2: Run tests and confirm RED**

Run: `python -m unittest tests.test_single_train_startup_probe -v`

Expected: missing config/behavior and validator acceptance.

- [x] **Step 3: Implement the exclusive pre-step artifact and early return**

```python
if bool(cfg.training.get("startup_probe_only", False)):
    payload = build_startup_probe_payload(cfg, state, work_dir, checkpoint_meta_dir)
    with open(os.path.join(work_dir, "startup_probe.json"), "x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
    print("STARTUP_PROBE_PASS")
    return
```

The helper raises unless step is zero, optimizer state is empty, and no checkpoint or summary files exist. Place the branch before `data.get_seqdataloader(cfg)`.

- [x] **Step 4: Run startup-probe and core training-helper suites**

Run: `python -m unittest tests.test_single_train_startup_probe tests.test_graph_checkpoint_contract tests.test_single_train_checkpoint_retention -v`

Expected: all tests pass and no existing checkpoint behavior changes.

### Task 5: Full local and dynamic verification

**Files:**

- Modify: `issues/2026-07-11_host-core-v2-preflight.csv`
- Create: `docs/reports/data/2026-07-11-r6-runtime-launch-contract/verification.json`
- Create: `docs/reports/data/2026-07-11-r6-runtime-launch-contract/verification.md`

- [x] **Step 1: Run focused and aggregate regression suites**

Run: `python -m unittest tests.test_r6_launch_contract tests.test_aaai27_queue_runtime tests.test_aaai27_queue_validation tests.test_aaai27_queue_cli tests.test_launch_aaai27_seed100_queue tests.test_risk04_08_queue_safe_adapters tests.test_aaai27_front_gate_adapters tests.test_single_train_startup_probe -v`

Expected: zero failures; only the platform-expected Windows `flock` skip is allowed. The continuation adapter must report `gpu_ids=[1]`, every continuation GPU task must report `cwd==run_dir`, and the CPU contract gate must retain the immutable source cwd.

- [x] **Step 2: Run static verification**

Run: `python -m compileall -q single_train.py scripts tests/test_r6_launch_contract.py tests/test_single_train_startup_probe.py`

Run: `git diff --check`

Expected: exit code `0` for both commands.

- [ ] **Step 3: Re-run production `probe_gpu_pids(0/1)` after deploying the r6 immutable source**

Create a short no-training CUDA context on GPU1, capture global and `--id` queries, call `probe_gpu_pids(0/1)`, and wait for natural exit.

Expected: the diagnostic PID appears only for GPU1; no process remains afterward.

- [x] **Step 4: Audit a generated manifest**

Expected invariants: 22 tasks, 14/8 branches, seed set `{100}`, `gpu_ids=[1]`, 22 unique run dirs, every GPU task `cwd==run_dir`, absolute source entry, unchanged assets/`phi_R`/identities.

- [ ] **Step 5: Commit the implementation and ledger**

```bash
git add single_train.py configs/config.yaml scripts/aaai27_adapters scripts/aaai27_queue scripts/launch_aaai27_seed100_queue.py tests docs/reports/data/2026-07-11-r6-runtime-launch-contract issues/2026-07-11_host-core-v2-preflight.csv
git commit -m "fix(queue): enforce r6 runtime launch contract"
```

Do not stage user tar archives or the two untracked E1 execution logs.

### Task 6: Freeze the dated r6 handoff contract

- [x] Update the r6 spec, this plan, and the E1/RISK-04–08 manual with the r5 closed-before-training fact, GPU1-only binding, GPU-task `cwd==run_dir`, absolute source entry, real Hydra startup-probe boundary, and CPU contract-gate exception.
- [x] Mark the 2026-07-10 resident-queue runbook as superseded; retain it as historical evidence and do not reuse its `[0,1]` allowlist.
- [x] Record fresh test, compile, diff, dynamic GPU probe, and generated-manifest evidence in the dated verification artifact; production probe evidence remains a pre-controller gate after deployment.
