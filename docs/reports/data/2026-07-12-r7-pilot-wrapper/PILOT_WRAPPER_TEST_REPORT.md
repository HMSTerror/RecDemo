# r7 fail-closed pilot wrapper and artifact-contract test report

Date: 2026-07-12 (Asia/Shanghai)

Scope: local P0-2 implementation and regression verification only. No r7 source snapshot or queue was deployed to the server, and no training was started by this work item.

## Acceptance contract

Every pilot task must execute `single_train.py` through a source-bound wrapper. A task may become `pass` only when all of the following are true:

1. the real child process exits with code 0;
2. the selected validation-chosen summary exists, is JSON, contains finite validation/test HR@10 and NDCG@10, and has an integer `best_step`;
3. the run-local `single_train.log` exists and is nonempty;
4. the queue manifest is unchanged across child execution;
5. the selected summary, log, queue, source revision, config, split, bank, evaluator, selector, gate scale, and frozen clean-null reference are all bound by hash/provenance;
6. the immutable `artifact_manifest.json` is the task's second declared success artifact.

Child failure, malformed/nonfinite summary, path escape, queue mutation, empty/tampered log, missing null provenance, or identity mismatch must return nonzero and must not create a passing artifact manifest.

## RED evidence

The implementation was driven by failing contract tests. Before the wrapper existed, the new tests observed the following intended failures:

- pilot argv still invoked `single_train.py` directly;
- queue validation still accepted only one success artifact;
- the source wrapper entry point did not exist;
- task environments did not carry queue/run/summary/artifact/source/null-reference bindings;
- three rehashed artifact-tampering cases were accepted by the previous RISK-08 validator.

During regression synchronization, the pre-existing suite reproduced seven failures: four fixtures lacked the new null/double-artifact contract and three assertions still expected the direct-entry/single-artifact design. After those fixtures were corrected, two tests exposed a real production data-flow defect: `build_risk0607_manifest()` accepted `null_curve_sha256` in the outer protocol but dropped it while rebuilding the internal pilot protocol. The minimal production fix validates and propagates that hash.

## Minimal implementation

The change adds:

- `scripts/run_aaai27_pilot_task.py`, a source-root CLI entry point;
- `scripts/aaai27_adapters/pilot_task_wrapper.py`, which runs the real child process, tees stdout/stderr into the resident queue log and run-local log, validates the selected summary, and writes one immutable manifest only after all checks pass;
- wrapper argv and provenance environment bindings in `pilot_adapters.py`;
- the two-artifact pilot contract in queue validation;
- source/config/split/bank/evaluator/selector/summary/log/null/gate validation in the production RISK-08 artifact validator;
- validated propagation of `null_curve_sha256` through `build_risk0607_manifest()`.

The wrapper does not modify model mathematics, training hyperparameters, selector rules, evaluator rules, seeds, corruption banks, or frozen thresholds.

## GREEN evidence

Real-child wrapper tests:

```text
python -m unittest tests.test_aaai27_pilot_task_wrapper
```

Observed result during implementation: `Ran 8 tests in 6.184s`, `OK`. These tests execute a real temporary child process and cover success streaming, a silent child, child exit failure, missing/nonfinite summary, queue-relative path escape, missing frozen-null provenance, empty/tampered logs, and rehashed null/source identity tampering.

Fresh combined regression command:

```text
python -m unittest \
  tests.test_aaai27_pilot_task_wrapper \
  tests.test_r6_launch_contract \
  tests.test_risk04_08_queue_safe_adapters \
  tests.test_text_side_proposal \
  tests.test_aaai27_front_gate_adapters \
  tests.test_aaai27_queue_validation \
  tests.test_aaai27_queue_runtime
```

Observed result: `Ran 87 tests in 16.919s`, `OK (skipped=1)`. The one skip is an existing conditional test and is not a newly hidden failure.

Additional checks:

```text
python -m py_compile <all changed Python modules and tests>
git diff --check
git diff --exit-code -- model/text_side.py
```

All three commands exited 0. The production model file remains unchanged.

## Evidence boundary

This report proves the local wrapper, manifest construction, production validator, and queue-contract behavior in the tested scope. Temporary-child and fixture tests do not prove server deployment or completion of any GPU training. Server deployment remains P0-4, and training launch remains P0-5 after P0-3 is also closed.
