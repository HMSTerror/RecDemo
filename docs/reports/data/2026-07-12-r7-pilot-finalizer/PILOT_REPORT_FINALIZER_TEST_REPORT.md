# r7 artifact-derived pilot report and RISK-08 finalizer test report

Date: 2026-07-12 (Asia/Shanghai)

Scope: P0-3 local implementation and contract tests. No server source was deployed, no queue was armed, and no GPU training result is claimed by this report.

## Frozen inputs replayed

The implementation reads the dated RISK-05 preregistration and its SHA-bound train-only preflight instead of accepting metric or threshold arguments. It replays:

- primary statistic: EPE;
- pilot levels: c0/c60/c100 on Beauty and Steam;
- full-arm predictions for `phi_R>=0.5`, `0<phi_R<0.5`, and `phi_R=0`;
- adjacent opposite-reversal tolerance: NDCG@10 `0.002`;
- six-point descriptive Spearman threshold: `rho <= -0.5`;
- worst-anchor absolute-improvement threshold: NDCG@10 `0.002`, with the frozen alternative of halving the worst negative magnitude;
- evaluator `e0_full_tail_v2` and selector `validation-ndcg10-rowweighted-v1`;
- E1-pass cardinality of fourteen tasks, seed 100, no rescue, and no second seed.

The six EPE values are loaded only after the preflight file SHA-256 matches the hash frozen in RISK-05. Bank hashes at each pilot point must also agree between preflight, preregistration, queue task, and artifact provenance.

## Artifact-only report construction

`scripts/aaai27_adapters/pilot_report.py` discovers the fourteen E1-pass tasks from the validated queue manifest. For each task it derives the artifact path from the task's second declared success artifact, executes the production RISK-08 artifact validator, reads the bound selected summary, and cross-checks the summary metrics against the artifact's selected-metric copy.

The report contains, for every host/anchor/full arm:

- validation and test HR@10 and NDCG@10;
- validation/test host-relative deltas for every evidence arm;
- selected step, selected-summary path/hash, artifact path/hash, bank hash, and kernel identity;
- frozen EPE and `phi_R` for all six anchor/full conditions.

There is no top-level `metrics` input field. Missing artifacts, nonfinite summaries, summary/artifact disagreement, path escape, queue/prereg/preflight/hash mismatch, selector/evaluator mismatch, wrong kernel version, or gate-scale mismatch raises `PilotReportError` before RISK-08 is called.

## Frozen phenomenon decision

The deterministic `phenomenon_pass` is the conjunction of four visible checks:

1. all six frozen full-arm predictions pass;
2. at least one dataset's anchor deltas follow descending-EPE ordering without an opposite adjacent reversal greater than `0.002`;
3. Spearman correlation uses all six EPE/anchor-delta points and is at most `-0.5`;
4. the full arm improves the single worst anchor delta by at least `0.002` or halves the magnitude of that worst negative delta.

Every failed condition remains in `phenomenon_checks`, with its input values, threshold, and boolean result. The Spearman value is explicitly descriptive; the code performs no significance test and supplies no p-value.

## Immutable finalizer

`scripts/finalize_r7_pilot.py` builds one report inside the dated queue root and then calls the existing `run_risk08_decision()`. The original function remains the only writer of `markers/RISK-08_EXIT.json`. A second finalization attempt fails because the report and/or exit is immutable. An output path outside the dated queue is rejected before any report is written.

If the frozen phenomenon is false, the original RISK-08 logic emits `submission_stop`; the finalizer contains no threshold, corruption, seed, or rescue branch.

## TDD evidence

Initial RED evidence:

- importing `scripts.aaai27_adapters.pilot_report` failed because the module did not exist;
- invoking the finalizer CLI failed because `scripts/finalize_r7_pilot.py` did not exist;
- the first boundary test showed that a caller could place a report outside the queue root;
- fixture synchronization exposed E1 byte-format and source-hash fixture defects before the production logic was accepted.

Fresh dedicated command:

```text
python -m unittest tests.test_r7_pilot_report
```

Observed result: `Ran 10 tests in 19.978s`, `OK`.

The ten tests cover: complete 14-artifact PASS, full-prediction failure, anchor-ordering failure, six-point Spearman failure, worst-anchor failure, missing/nonfinite summary, preflight hash tampering, direct CLI invocation, one immutable original RISK-08 exit, and report-path containment.

Fresh combined regression command:

```text
python -m unittest \
  tests.test_r7_pilot_report \
  tests.test_aaai27_pilot_task_wrapper \
  tests.test_r6_launch_contract \
  tests.test_risk04_08_queue_safe_adapters \
  tests.test_text_side_proposal \
  tests.test_aaai27_front_gate_adapters \
  tests.test_aaai27_queue_validation \
  tests.test_aaai27_queue_runtime
```

Observed result: `Ran 97 tests in 31.225s`, `OK (skipped=1)`. The skip is pre-existing and conditional.

Additional verification:

- `python -m py_compile` on the new module, CLI, and test: exit 0;
- `git diff --check`: exit 0;
- `git diff --exit-code -- model/text_side.py`: exit 0;
- line-length audit at 119 characters: zero violations in the three new files.

`ruff` was not available in the current Python environment, so no linter-pass claim is made.

## Evidence boundary

The PASS fixture uses fourteen same-root, hash-bound synthetic artifacts and calls the production validator plus original RISK-08 writer. This proves the local decision pipeline in the tested scope; it is not evidence that r7 server training has completed or that the real frozen phenomenon will pass. Real `phenomenon_pass` remains unknown until P0-5 completes all fourteen seed-100 tasks.
