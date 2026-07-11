# RISK-06/RISK-07 seed=100 pilot execution (2026-07-11)

## Scope and design

This dated record covers the server-side launch boundary for the E1-pass pilot. The queue contains the frozen 14-task E1-pass branch (Beauty/Steam host, text-anchor-only c0/c60/c100, and risk-gated-full c0/c60/c100), plus the eight E1-fail audit tasks that remain inactive while the E1 marker is `pass`. Every task is PreferGrow, `random_seed=100`, `max_attempts=1`, and `failure_policy=fail_closed`. No DiffuRec, BERT4Rec, second seed, test-driven reselection, or rescue tuning is part of this attempt.

The controller is resident on l20 under tmux. GPU0 is reserved for the pre-existing CLOSE-10 process; at most one new task may occupy GPU1. The `/data` launch gate is 40 GiB free space.

## Attempt r2: fail-closed before valid training

The first dated retry root was:

```text
/data/Zijian/goal/aaai27_queue/2026-07-11-risk0607-332efb8-r2
```

The controller command was rejected before dispatch because the old manifest bound `run_root` to `.../r2/runs` while the controller was invoked with the dated queue root `.../r2`. The exact error was:

```text
ValueError: queue root does not match manifest run_root:
/data/.../2026-07-11-risk0607-332efb8-r2 !=
/data/.../2026-07-11-risk0607-332efb8-r2/runs
```

After correcting that root identity in a new manifest, the first child exposed a second safety issue: `single_train.py` overwrites `CUDA_VISIBLE_DEVICES` from its Hydra `cuda=` argument. The r2 child was therefore terminated and recorded as `exit_code=-15`; its partial checkpoint is not a result and must not be used. The CLOSE-10 PID `2568867` was left running.

## Attempt r3: binding fix and live execution

The immutable r3 root is:

```text
/data/Zijian/goal/aaai27_queue/2026-07-11-risk0607-332efb8-r3
```

Manifest and controller evidence:

| Item | Evidence |
|---|---|
| queue manifest SHA-256 | `559808f19da0bc066d9a658bd022757b9573a00ea38583736e4c76d247891653` |
| queue manifest | 22 tasks total; 14 selected on `e1_pass`; seed set `{100}` |
| controller | PID `2798369`, tmux `aaai27_r3_seed100_controller_20260711` |
| initial task | `pilot.e1_pass.Beauty.host`, PID `2798374`, GPU1 |
| completed task observed | Beauty/host, `passed=1`; validation-selected `best_step=8000`, `NDCG@10=0.022093` (single-run observation) |
| current task observed | `pilot.e1_pass.Steam.host`, PID `2799407`, GPU1 |
| runtime patch SHA-256 | `a453dc6ae7e4f734e0837d2d20bb2a89b293c9fd8f74be010e290057ce267cea` |
| free `/data` at latest check | about 51.8 GiB; above the 40 GiB hard gate |

The post-launch binding checks for both Beauty/host and Steam/host found:

```text
CUDA_VISIBLE_DEVICES=1
AAAI_PHYSICAL_GPU_ID=1
AAAI_LOGICAL_GPU_ID=0
random_seed=100
command token: cuda=1
nvidia-smi: PID listed on GPU1 and absent from GPU0
```

GPU0 continued to contain only CLOSE-10 PID `2568867`. The corresponding JSON binding checks are written below the r3 queue root under `state/`.

## Interpretation and next steps

The experiment is genuinely running, but the full 14-task branch is not complete. The current evidence supports only the statements “controller live”, “GPU binding passed for the checked tasks”, and “Beauty/host single-run observation passed”. It does not support claims of significance, stability, statistical equivalence, or final paper conclusions. The resident queue should be monitored using the read-only status command; it must stop dispatching if `/data` falls below 40 GiB, if a task exits nonzero, if a success artifact is missing, or if any new task appears on GPU0.

