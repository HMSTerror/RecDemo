# E1 R11 launch-wrapper repair

## Root cause

ADAPT-02-R10 never entered the E1 runner. The remote `tmux new-session` command
was nested inside an SSH string whose quoting was stripped by the local
PowerShell/remote shell boundary. The requested `cd` was therefore lost and
Python looked for `scripts/run_e01_gzero_trace.py` under `/home/zijian`.

## Minimal repair

Create a new dated attempt (R11) and launch the same frozen R10 source with
`tmux new-session -c <bundle-root>` and absolute interpreter/script/config
paths. The launcher must be preflighted for a free GPU1, an absent output path,
and an absent tmux session before starting exactly one process. No model,
optimizer, evaluator, seed, tolerance, proposal, corruption, or trace logic is
changed.

## Acceptance

1. Remote preflight confirms the R11 bundle and output paths are unique, GPU1 is
   free, and GPU0 PID `2568867` is untouched.
2. Remote unit tests for the E1/controller surface pass before launch.
3. The runner creates one dated `e01_gzero_trace.json` and compares steps
   `0,1,100,1000` with seed `100` and FP32 tolerance `1e-6`.
4. Only a report with `status=pass`, all four checkpoint statuses `pass`, and a
   valid unique RISK-02 marker may unlock continuation. Any launcher or
   scientific failure closes R11 and starts no continuation.
