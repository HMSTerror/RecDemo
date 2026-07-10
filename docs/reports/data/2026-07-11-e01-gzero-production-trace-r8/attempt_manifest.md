# E01 R8 attempt manifest

- attempt: `ADAPT-02-R8`
- code commit: `ea5cdca`
- bundle archive SHA-256: `3160572dddb84685f0fe67bbbfec512120fca3deb04b82edb0bd400772c76b92`
- remote bundle: `/data/Zijian/goal/RecDemo_aaai27_controller_20260711_r8_ea5cdca`
- remote interpreter: `/data/Zijian/goal/PreferGrow/.venv/bin/python3`
- dataset: `Beauty` (`seed=100`, `device=cuda:1`)
- tmux session: `aaai27_e01_r8`
- Python PID: `2625926`
- output root: `/data/Zijian/goal/RecDemoRuns/aaai27_e01_gzero_trace_20260711_r8_ea5cdca`
- report SHA-256: `9401f5db31f4b9f778ba315d83617807030a7db96064e39b0e3fe9fa0e8e3f74`
- execution-log SHA-256: `54d3e95cacefa96723d12d364bcde56de2a0cc15a73590a9e99686f12fe7ba47`
- terminal status: `fail`
- checkpoints: `step0=pass`, `step1=fail`, `step100=fail`, `step1000=fail`
- first divergence: `step=1 / optimizer / core_proposal_logits.state.exp_avg`
- first divergence magnitude: `0.011209116317331791`
- raw gradient max difference at step 1: `1.1175870895385742e-08`
- loss/proposal/RNG comparisons at step 1: passed under the frozen rule
- diagnosis: model-only gradient clipping/EMA omitted host graph-owned `p1`,
  while proposal arms included builder-owned `p1`; effective optimization sets
  were not matched.
- RISK-02 pass marker: `absent`
- downstream authorization: `false`
- continuation training: `not started`
- retry exercised: `false`

This is terminal repair evidence, not an E1 pass.
