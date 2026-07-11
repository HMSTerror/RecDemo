# E5 SASRec seed-100 GPU0 design

Date: 2026-07-11 (Asia/Shanghai)

## Purpose and evidence boundary

E5 supplies one external, non-diffusion reference for the PreferGrow four-domain
study. It is a single-seed (`100`) observation, not a significance or stability
claim. The comparison is valid only when Steam, ML1M, Beauty, and ATG all use the
frozen `paper_raw_v1` train/validation/test frames, item mappings, full real-item
catalog, `e0_full_tail_v2` metrics, and the validation-only selector
`validation-ndcg10-rowweighted-v1`.

## Implementation choice

Use a minimal standard SASRec implementation in the PreferGrow adapter rather
than importing an external project's preprocessed data or checkpoint. The model
has an item embedding with a padding row, learned absolute positions, a causal
Transformer encoder, and a full-catalog linear score head. It trains with
cross-entropy on the supplied `next` column. No native resplitting, sampled
candidate evaluation, history masking, or test-based checkpoint selection is
allowed.

The adapter writes one per-domain `artifact_manifest.json`, a validation-selected
best checkpoint, a summary, and a real log. Test metrics are evaluated once from
the validation-selected state and are explicitly labelled development-time test
readouts; they are not an untouched final holdout.

## Atomic execution contract

The four domain tasks are members of one E5 atomic group. The dated queue root is
new and isolated, `seed=100`, `gpu_ids=[0]`, `max_attempts=1`, and
`failure_policy=fail_closed`. A missing split, mapping, first training-loop
marker, validation summary, or artifact for any domain makes the group
`incomplete`; no favorable subset may be promoted. The task working directory is
its run directory and the source entry is immutable. The GPU0 launcher checks that
GPU1's r6a process set is unchanged before starting and that `/data` remains above
40 GiB.

## Validation and tests before launch

1. CPU unit tests cover padding, causal masking, full-catalog ranking, row counts,
   deterministic seed setup, validation-only selection, and artifact self-hashes.
2. A static manifest audit checks exactly four domains, one seed, one GPU, common
   evaluator/selector strings, absolute paper-raw paths, and no test selector.
3. A short GPU0 startup probe constructs the model and one batch, writes only a
   probe marker, and exits before training/checkpoint/metric code. The formal
   manifest does not contain the probe override.
4. Only after these checks pass is the detached GPU0 queue launched. A read-back
   records controller/launcher PID, tmux session, manifest SHA-256, task PID,
   argv/cwd, first loop marker, GPU occupancy, disk, and unchanged r6a state.

## Resource and stop policy

The estimate is 2--8 GPU-hours when run serially on GPU0 (Beauty/ATG are short;
ML1M/Steam dominate). Best-only checkpoints are retained; no periodic snapshots
are written. OOM, non-zero exit, missing artifact, hash mismatch, disk below the
hard gate, or any second process on GPU0 is terminal for this dated attempt. No
retry, seed change, hyperparameter sweep, or result-based rescue is authorized.
