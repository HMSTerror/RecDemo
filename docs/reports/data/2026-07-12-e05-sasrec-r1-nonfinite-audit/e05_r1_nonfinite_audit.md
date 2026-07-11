# E5 SASRec r1 prelaunch/early-run audit

Date: 2026-07-12 (Asia/Shanghai)

## Verdict

The dated queue `2026-07-11-e05-sasrec-seed100-gpu0-r1-29b8483` is **invalid and
not performance evidence**. Its first Steam task entered the real training
loop, but the first three logged epochs had `mean_train_loss: NaN`. The queue
was stopped before any ML1M, Beauty, or ATG task launched. The Steam checkpoint,
summary, and metric files were not produced. No number from this attempt may be
used in a paper table.

## Evidence

| Item | Evidence |
|---|---|
| Queue manifest | `/data/Zijian/goal/aaai27_queue/2026-07-11-e05-sasrec-seed100-gpu0-r1-29b8483/manifest.json`; SHA-256 `fbdfcc06620e16c7944881bdeb8a8498370fde168aa76968db6509aace924171` (self-hash before launch) |
| Queue status | `queue_status.json`; SHA-256 after the stopped run `5909dd4b8e310816d3ae64e23ec4fbdf91b5801b40bec985f0addbae3ef3b1e0`; status was `running` because the first runner did not persist an external stop marker |
| First task log | `runs/SASRec/Steam/stdout.log`; SHA-256 `e9e23cd5adc32310a6fa637f19c3e981cbb6bfc6b5e4eada36af5440552a1468` |
| Logged failure signature | `epoch=1/2/3`, `mean_train_loss=NaN`; validation NDCG@10 repeated `0.0007564760162495077`; the apparent PASS line is rejected because the loss was non-finite |
| Launch scope | GPU0 only; GPU1 r6a PID `2941546` remained running and was not modified |
| GPU stop | After stopping the E5 tmux session, GPU0 compute occupancy returned to empty; only the pre-existing GPU1 r6a process remained |

The first queue used the correct source revision and paper_raw_v1 split hashes,
but its runner did not yet reject non-finite loss and did not persist the task
PID in `queue_status.json`. Both are implementation defects fixed in the next
source revision. The successor must use a new source root and a never-used
dated queue root; r1 is not retried or resumed.

## Root-cause hypothesis and repair boundary

The frames are left-padded. Passing left-padded histories directly to a causal
Transformer can create all-masked causal rows in padding positions, producing
non-finite attention values. The repair canonicalizes each history to a
right-padded internal tensor using the frozen `len_seq` field, gathers the last
real item by length, checks startup logits, training logits, loss, and evaluation
logits for finiteness, and fails closed before writing any checkpoint when a
check fails. No dataset, seed, evaluator, selector, model width, or optimization
hyperparameter is changed.

## Claim boundary

This audit is an engineering failure record. It does not support SASRec
performance claims, does not upgrade E5 readiness, and does not alter the frozen
r6a pilot or any Gate-1/Table-2 artifact.
