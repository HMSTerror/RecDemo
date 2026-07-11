# R6 runtime launch-contract verification

_PreferGrow AAAI-27 · 2026-07-11 · engineering evidence before immutable r6 deployment_

---

## 📋 Scope

This report records the local contract checks and the l20 GPU occupancy probe required before creating the new immutable r6 attempt. It is an orchestration artifact only; it contains no training metric and cannot be cited as RISK-08 or performance evidence.

## ✅ Local verification

The complete extension suite ran with `156` tests, `0` failures, `0` errors, and one platform-expected Windows skip for Linux `flock`. The startup-probe test emitted `STARTUP_PROBE_PASS` and returned before dataloader construction. `compileall` and `git diff --check` both returned exit code `0`.

The generated builder/validator audit was synthetic fixture evidence, explicitly bounded to invariants: `22` tasks (`14` `e1_pass`, `8` `e1_fail_audit`), `gpu_ids=[1]`, seed set `{100}`, `22` unique run directories, GPU-task `cwd==run_dir`, four host tasks, eighteen evidence tasks, and absolute POSIX `single_train.py` source entry. It does not establish that any task trained or that any metric is valid.

## 🔍 l20 dynamic occupancy probe

At `2026-07-11T21:19:50+08:00`, l20 reported two NVIDIA L20 devices with `46068 MiB` each and `9 MiB` used. A 20-second CUDA-only diagnostic was launched with `CUDA_VISIBLE_DEVICES=1`; PID `2891985` appeared in the global compute listing and in `nvidia-smi --id=1`, while `nvidia-smi --id=0` was empty. The process exited naturally and the post-probe global listing was empty.

The pre-deployment source tree on l20 did not contain the new queue package, so the production `probe_gpu_pids(0/1)` import was not claimed here. After the r6 immutable source is deployed, the same read-only probe must call the production function for both physical IDs and archive its raw output before any controller is created.

## 🚫 Boundary

No r6 controller, tmux session, scientific task, checkpoint, summary, validation/test metric, or RISK-08 marker was created by this verification. The next irreversible boundary is the creation of a new immutable source/protocol/manifest root; a failed remote startup probe must preserve that attempt and prevent controller launch.
