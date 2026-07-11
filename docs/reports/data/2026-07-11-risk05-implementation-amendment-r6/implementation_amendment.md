# RISK-05 r6 implementation-only amendment

_PreferGrow AAAI-27 · 2026-07-11 · prepared after the r5 live-startup fail-closed audit_

---

## 📋 Scope and predecessor boundary

This dated amendment authorizes preparation of a new immutable r6 source and queue binding; it does not mutate, resume, or supersede the frozen RISK-05 scientific preregistration. r5 is closed as `failed_before_training`: seven tasks failed during Hydra logging initialization, fifteen were not launched, and the attempt produced zero training steps, checkpoints, best summaries, or performance evidence. r5 is permanently ineligible for retry, reuse, and RISK-08.

## 🔒 Immutable r6 identity

The source revision is `6f0fa3c2ca43a97b0da93a98f4fa88a0a7618dbd`, archived as `prefergrow_source_6f0fa3c.tar` with SHA-256 `acbf4aefeb3c9e580ce2e97e8ca94610abbe6de206fb92a0270f4750bed39aea` and size `41,308,160` bytes. The intended source root is `/data/Zijian/goal/RecDemo_aaai27_risk0607_6f0fa3c`; the intended queue root is `/data/Zijian/goal/aaai27_queue/2026-07-11-risk0607-6f0fa3c-r6`. Both are new dated roots. The machine-readable protocol is [risk0607_protocol_r6.json](risk0607_protocol_r6.json), SHA-256 `73b22ede2acec6a545324250b3fce87a7fda22a10b6ba811d5af7ef50d66cfb2`.

## 🧪 Frozen scientific fields

The amendment preserves seed `100`, Beauty/Steam, c0/c60/c100 pilot levels, EPE and the six preregistered `phi_R` values: Beauty `(1.0, 0.1366311174092942, 0.0)` and Steam `(1.0, 0.05808110271503808, 0.0)`. It preserves the 14-task E1-pass and 8-task E1-fail-audit matrix, `e0_full_tail_v2`, `validation-ndcg10-rowweighted-v1`, `max_attempts=1`, `failure_policy=fail_closed`, no rescue tuning, and no second seed. `phi_R` remains a controlled-corruption pilot gate and is not a replacement for the paper's `phi(U_ds)`.

## ⚙️ Implementation-only repair

The r6 change binds every GPU task to `cwd==run_dir` inside the queue root, exposes `gpu_ids=[1]`, requires absolute immutable source entries, propagates explicit controller Python/entry arguments, rejects ambiguous GPU probe rows, and adds a real Hydra startup probe that returns after optimizer/EMA/gate construction but before dataloaders, optimizer steps, validation/test, sampling, checkpoint, summary, or metric paths. A zero-slot CPU `contract_gate` may retain immutable source cwd as an orchestration exception; it is not a training task.

## 🚫 Prelaunch stop conditions

The amendment is not a performance result and does not yet authorize controller creation. Before launch, the archive must be uploaded and hash-matched, the extracted source must be read-only, the protocol/ledger/config hashes must match, r3/r4/r5 must remain quiescent and immutable, GPU1 must be free, `/data` must exceed 40 GiB, and the 22-task manifest must validate with exact assets, host/evidence identities, six `phi_R` values, seed 100, and GPU1-only binding. A real Hydra startup probe must exit zero with a scoped step-0 marker and zero checkpoint/summary side effects. Any mismatch preserves the r6 attempt and blocks the controller; no retry is allowed.
