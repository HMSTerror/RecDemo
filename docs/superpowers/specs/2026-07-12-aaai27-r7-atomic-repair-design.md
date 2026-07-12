# AAAI-27 r7 atomic pilot repair and evidence-integration design

Date: 2026-07-12 (Asia/Shanghai)

Status: user-approved execution input. The approval covers P0-0 through P0-6, a new dated r7 attempt, and automatic continuation to the seed-100 fourteen-run E1-pass pilot after every prelaunch gate below passes. This document does not authorize E7 record regeneration, rescue tuning, interference with root-owned GPU jobs, or writes into any r6a/frozen artifact root.

## 1. Goal

Produce one complete, internally consistent, seed-100 r7 pilot under the already frozen RISK-05 numerical contract while repairing only the two proven execution defects in r6a:

1. anchor-only tasks lacked an explicit dataset-scale source and could either fail the bank-hash check or be silently overwritten by the post-mixture closed-gate branch;
2. successful tasks did not emit the per-run artifact manifests required by `run_risk08_decision()`, and their run-local `single_train.log` files were empty.

The r7 attempt must execute the full E1-pass matrix in one dated queue root: Beauty and Steam, one shared host per dataset, and `text_anchor_only` plus frozen full at corruption levels 0, 60, and 100. This is fourteen executed training tasks. The queue builder may retain the inactive eight-task E1-fail branch for schema compatibility, but no task outside the E1-pass branch may execute when the bound E1 marker is PASS.

## 2. Frozen inputs and non-goals

The following are immutable inputs:

- seed and corruption seed: 100;
- evaluator: `e0_full_tail_v2`;
- selector: validation `p5` NDCG@10, row-weighted;
- datasets and splits: frozen Beauty and Steam `paper_raw_v1` inputs;
- corruption banks and hashes from the dated RISK-04 bundle;
- RISK-05 EPE values, `phi_R` numeric values, pilot levels, predictions, thresholds, and no-rescue rule;
- E1/R12 PASS marker and its source/trace hashes;
- production `model/text_side.py` used by r6a;
- one training process per physical GPU and no sharing with any root-owned process;
- no replacement or deletion of r6a, Gate-1, SPRINT-07, DiffuRec, or other frozen artifacts.

This attempt does not:

- regenerate E7 transition records or user IDs;
- add a new FPM statistic; RISK-03 EPE/PNE@10 is the mechanism audit;
- tune a threshold, gate, corruption level, seed, selector, or evaluator after observing r6a/r7 results;
- reinterpret c100 as spontaneous user-gate collapse;
- claim a checkpoint-byte identity when only selected best summaries are identical;
- promote a single-seed result to significance, stability, equivalence, or a noise-floor claim;
- restore DiffuRec as a confirmatory baseline.

## 3. Scientific arbitration that must precede manuscript use

### 3.1 c100 scope

The r6a full c100 argv explicitly supplies `text_side.gate_dataset_scale_override=0.0`. Therefore c100 is a production-path exact-fallback sanity check under a preregistered dataset scale of zero. It is not evidence that history-level `u_tilde` spontaneously collapsed under corruption. The permitted statement is:

> Under preregistered `phi_R=0`, the production training path selected a best-summary artifact byte-identical to the matched host; checkpoints differ because the full arm serializes additional text-side state.

### 3.2 EPE and `phi_R` are not the legacy `U_ds` hinge

The legacy method used `g = g_max * phi(U_ds) * clip(u_tilde, 0, 1)`. The r6a/r7 pilot instead injects the dated RISK-05 override values derived from RISK-03 EPE. These are distinct method generations and must be separated in the paper:

1. `U_ds`: legacy discovery evidence;
2. EPE/PNE@10: train-only observed next-positive exposure measurements;
3. frozen `phi_R`: the dated corruption-response scale used by r6a/r7;
4. r7/RISK-08: a controlled reliability/fallback intervention, not a silent replacement of the legacy main table.

### 3.3 frozen sign inconsistency

RISK-03 defines positive EPE as stronger text-proposal exposure of the observed next positive. The parent rescue spec says `phi_R` must be non-increasing in that risk. The frozen implementation and JSON instead use

`clip((R_100 - R_D) / (R_100 - R_clean), 0, 1)`.

For both pilot datasets `R_clean > R_100`, so this mapping is monotone increasing in EPE: clean/high-EPE maps to one and c100/low-EPE maps to zero. No frozen value or prediction may be altered after r6a results were observed. The dated evidence memo must therefore record all three facts:

- EPE remains an observed next-positive exposure proxy;
- the implemented `phi_R` behaves as an evidence-retention/corruption-reliability scale, not as a demonstrated high-EPE suppression function;
- a mechanical RISK-08 PASS cannot by itself validate the broader claim that high positive-exposure risk closes the gate.

The RISK-05 machine contract and its legacy exit label remain byte-preserved for auditability. Manuscript wording must use the narrower scientific scope above.

### 3.4 Beauty disclosure

Every table or figure that shows Beauty c0/c60 test gains must also show validation deltas. The caption must state that selection used validation only and that test metrics were logged during development. Beauty c0/c60 validation deltas are approximately zero; test-only gains may be described only as single-run observations.

## 4. P0 execution tasks

### P0-0 — freeze source and write the dated evidence amendment

Create an immutable source/evidence manifest before patching. It must bind the r6a source root, the four relevant source-file SHA-256 values, the E1/R12 marker, RISK-03 report/provenance artifacts, RISK-05 bundle/preregistration, RISK-04 banks, r6a queue manifest, all six full-arm override tokens, `phi_R` values, and the r6a best summaries. Write a dated memo covering Sections 3.1–3.4 and the exact sign inconsistency. The memo is evidence arbitration, not a retroactive preregistration.

Acceptance:

- no r6a/frozen byte is modified;
- every cited input has a path and SHA-256;
- Beauty and Steam `phi_R` values are recorded as `1.0/0.1366311174092942/0.0` and `1.0/0.05808110271503808/0.0`;
- c100 best-summary identity is distinguished from checkpoint identity;
- the memo states that E7 remains `not_estimable` because user IDs are absent.

### P0-1 — repair anchor gate-source selection using TDD

The sole production-argv repair is to add exactly one `text_side.gate_dataset_scale_override=1.0` token to every anchor-only task. Do not modify `model/text_side.py`. The override skips default utility-report discovery, prevents bank-hash mismatch, sets the anchor dataset scale to one, and avoids the post-mixture `self.gate_dataset_scale == 0` overwrite.

The dated test report must cover seven checks:

1. all six E1-pass anchor argv contain exactly one override of 1.0;
2. anchor argv do not carry a utility-report path and have one unambiguous gate source;
3. a clean `phi=0` fixture still yields `g=g_max` for anchor-only;
4. final anchor proposal differs from `p_core` on a non-degenerate fixture;
5. final anchor proposal equals the fixed `g_max` anchor mixture;
6. full c100 still returns `p_core` exactly;
7. E1/global-p and existing queue-contract regressions remain green.

The new regression test must be observed failing for the final-proposal condition before the adapter patch is applied.

### P0-2 — add a fail-closed task wrapper and artifact provenance

Every r7 pilot task must execute through a real wrapper inside the dated source root. The wrapper streams child stdout/stderr to both the queue task log and a run-local nonempty `single_train.log`, preserves the child exit code, and emits `artifact_manifest.json` only after a successful child exit and validation of the selected best summary.

The artifact manifest must bind:

- task ID, status, queue-manifest SHA-256, source revision, config/split/bank identity;
- summary path and SHA-256 as metric provenance;
- run-log path, nonzero size, and SHA-256;
- evaluator and selector versions;
- `null_curve_reference_policy=frozen_clean_calibration`;
- null-curve path/SHA-256, clean source-bank SHA-256, and current embedding SHA-256 for evidence arms;
- explicit `phi_R`/gate scale where applicable;
- a self hash computed with the existing canonical payload-hash rule.

If the child fails, the summary is missing/non-JSON/nonfinite, the log is empty, a provenance path leaves the dated queue root, or a required hash differs, the wrapper exits nonzero and does not emit a passing artifact manifest. No manifest may be reconstructed manually after the task.

### P0-3 — freeze artifact-derived pilot decision logic

Before any repaired anchor result is observed, implement and test a pilot-report builder that reads only the fourteen r7 artifact manifests and their bound selected summaries. It must never accept hand-entered metrics. It must report validation and test HR@10/NDCG@10 for every arm, host-relative deltas, all six anchor points, all six full points, and the frozen EPE/`phi_R` values.

`phenomenon_pass` must replay the already frozen RISK-05/parent-spec contract without discretionary rescue:

- all six frozen per-`phi_R` full-arm predictions are reported and evaluated;
- at least one dataset satisfies the preregistered anchor response ordering with no opposite adjacent NDCG@10 reversal greater than 0.002;
- descriptive Spearman association between the six frozen EPE points and six anchor host-relative test NDCG@10 deltas is at most -0.5;
- the full arm improves the worst anchor host-relative delta by at least 0.002 or halves the magnitude of the worst negative delta;
- all hashes, branches, selectors, evaluators, kernel versions, task IDs, and artifact paths match.

Any missing/nonfinite value or failed condition makes `phenomenon_pass=false`. The builder must retain the failed values and reasons. It must not change the RISK-05 threshold, add another seed, choose a favorable subset, or call `run_risk08_decision()` until all fourteen artifacts are present.

### P0-4 — build and validate one dated r7 atomic queue

Create a new dated source root and queue root. Copy the frozen r6a source snapshot, apply only the reviewed adapter/wrapper/report-builder patch, and generate a source manifest. Bind the existing RISK-04/RISK-05/E1 artifacts by SHA-256. Configure the explicit physical GPU allowlist `[0,1]`; the runtime must probe each card and launch at most one training process on a card only when no compute PID is present. Root-owned jobs are never stopped, signalled, reniced, or colocated.

Prelaunch validation must establish:

- exactly fourteen active E1-pass tasks and eight inactive E1-fail schema tasks;
- seed 100 and isolated run directories for every task;
- six corrected anchor argv and six unchanged numeric full overrides;
- two host tasks use the learned v2 host path;
- each task requires both its selected summary and artifact manifest;
- queue/source/ledger/protocol hashes are internally consistent;
- dry-run/smoke validation starts no training;
- no task can pass with an empty log or missing artifact manifest.

### P0-5 — arm the resident controller and automatically close RISK-08

After P0-0 through P0-4 pass, start a detached resident controller. It may wait while GPUs are occupied. As soon as either L20 is truly free, it may launch the next seed-100 task; if both are free it may use both, one process per card. After all fourteen active tasks pass, an automatic finalizer builds the artifact-derived pilot report and invokes the original `run_risk08_decision()` against the same dated queue root.

If a task fails, produces an empty log, or fails provenance validation, the queue remains fail-closed. If RISK-08 emits `submission_stop`, no new threshold, corruption level, second seed, or rescue run is authorized. The controller must survive client disconnection and expose status, PIDs, elapsed time, GPU assignment, last log timestamp, and artifact paths.

### P0-6 — integrate the scientific scope and enforce deadline gates

Before the 2026-07-18 internal abstract freeze, update the method/experiment/reproducibility wording so that:

- legacy `U_ds`, RISK-03 EPE/PNE@10, and the dated `phi_R` reliability-scale pilot are separated;
- the sign inconsistency and scope limitation are disclosed in a dated amendment/supplement note;
- c100 is presented as explicit scale-zero fallback, not adaptive user-level backoff;
- Beauty validation and test values appear together;
- SASRec is the external common-contract baseline and its Beauty anomaly is annotated;
- DiffuRec remains excluded from the confirmatory table;
- model selection is described as validation-only while test logging during development is disclosed;
- every seed-100 result is labeled a single-run observation.

Go/No-Go checkpoints:

- 2026-07-16 evening: if r7 has started or completed and the original RISK-08 contract is executable, continue the full submission path; if GPU remains unavailable but CPU/paper work is complete, hold a downgraded draft;
- 2026-07-18: if no repaired anchor evidence exists, remove gate-efficacy language and retain only the audit, EPE/PNE@10 measurement, and exact-fallback story;
- `RISK-08=submission_stop`: remove the predictive-risk claim and do not rescue-tune;
- AAAI-27 deadlines remain 2026-07-21 abstract, 2026-07-28 paper, and 2026-07-31 supplement (AoE).

## 5. Resource estimate

The r6a eight successful tasks consumed 7.0637 GPU-hours. The r7 fourteen-run active branch is budgeted at 12–16 GPU-hours, with an expected wall clock of approximately 6–10 hours on two available L20 cards or 12–18 hours on one. These are planning estimates, not completion promises. Actual feasibility is governed by the first GPU release time. E4 remains a separate 44–55 GPU-hour matched pair and is not part of the r7 blocking path.

## 6. Audit/reporting format

Each task update uses:

`task | status | key number and dated artifact path | gap to acceptance | next action`

No completion or PASS statement is permitted without a fresh command output, full test count, and artifact hash. If server state conflicts with a document, the server artifact is authoritative and the discrepancy is recorded rather than silently reconciled.
