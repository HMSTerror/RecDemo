# ADAPT-02-R10 terminal attempt manifest

- Attempt: `ADAPT-02-R10` (E1 Beauty g=0 lockstep, seed 100)
- Code commit: `09c4a4a`; bundle archive SHA256: `2f6585fc0330cfe268b18e51195e2ff9fd9f31f071202f1267e9fc7bdec4da8a`
- Remote bundle root: `/data/Zijian/goal/RecDemo_aaai27_controller_20260711_r10_09c4a4a`
- Remote output root: `/data/Zijian/goal/RecDemoRuns/aaai27_e01_gzero_trace_20260711_r10_09c4a4a` (not created)
- Execution log: `/data/Zijian/goal/RecDemoRuns/aaai27_e01_gzero_trace_20260711_r10_09c4a4a.execution.log`
- Execution log SHA256: `1527908631060b3c546d91d5c44a4159e0a613e1456c72612b0e6590bfe90262`
- Terminal status: `terminal_fail_before_trace`; downstream launch authorization: `false`; RISK-02 pass marker: absent.
- Failure evidence: the tmux nested command lost its requested working directory; Python attempted `/home/zijian/scripts/run_e01_gzero_trace.py` and exited before importing or executing the E1 runner.
- No E1 checkpoint was produced, no output directory was created, and no training/continuation was launched.
- Classification: launch-wrapper quoting failure, not a scientific comparison result. R10 is closed and will not be retried; R11 uses tmux `-c` plus absolute paths.

## Audit command

```text
ssh zijian@172.18.0.40 "sha256sum /data/Zijian/goal/RecDemoRuns/aaai27_e01_gzero_trace_20260711_r10_09c4a4a.execution.log; cat /data/Zijian/goal/RecDemoRuns/aaai27_e01_gzero_trace_20260711_r10_09c4a4a.execution.log"
```
