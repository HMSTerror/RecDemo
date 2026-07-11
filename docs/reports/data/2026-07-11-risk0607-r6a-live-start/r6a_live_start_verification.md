# r6a live-start verification

**Observed:** 2026-07-11 22:51+08:00  
**Queue:** `/data/Zijian/goal/aaai27_queue/2026-07-11-risk0607-946a167-r6a`  
**Session:** `aaai27_r6a_seed100_controller_20260711`  
**Manifest SHA-256:** `34b20ec58e2619d1326a45f1dd3d08cf717a10f8073532e7fd7f585f17c62227`

The r6a controller is resident in tmux (PID `2914346`).  Its first task is
`pilot.e1_pass.Beauty.host`, seed `100`, on GPU1 (PID `2914349`), with
`cwd=run_dir` under the r6a queue root.  The task state is `running` and the log has
entered the real training loop:

```text
step: 1000, evaluation_loss: 7.94071e+00, eval_time: 0.00s
EARLY_STOP_MONITOR step=1000 metric=ndcg10 strength=p5 value=0.010434
NEW_BEST step=1000 metric=ndcg10 value=0.010434
```

These are development-time single-run observations, not final paper results.  The
training code logs test metrics during development; they must not be described as an
untouched final holdout.  No second seed was started.

The prelaunch gates are also closed: the real Hydra startup probe produced
`STARTUP_PROBE_PASS` with step 0, no dataloader construction, optimizer steps,
checkpoints, summaries, or metrics, and the production GPU probe observed diagnostic
PIDs only on physical GPU1 before they naturally exited.  At live start GPU0 was 0%
and 9 MiB, GPU1 was 46% and about 1.5 GiB, and `/data` had 47 GiB free.

This artifact proves a live seed-100 training start only.  It does not prove completion,
cross-domain performance, RISK-08 exit, or statistical significance.

