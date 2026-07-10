# E01 R7 attempt manifest

- attempt: `ADAPT-02-R7`
- code commit: `3579421`
- bundle archive SHA-256: `2a1f93c100bf6c5d5d92c3ced9609beebe4d6e2f35fd1e3910ec148598497399`
- remote bundle: `/data/Zijian/goal/RecDemo_aaai27_controller_20260711_r7_3579421`
- remote interpreter: `/data/Zijian/goal/PreferGrow/.venv/bin/python3`
- dataset: `Beauty` (`seed=100`, `device=cuda:1`)
- tmux session: `aaai27_e01_r7`
- process PID: `2623525` (tmux launcher; Python child exited after terminal failure)
- output root: `/data/Zijian/goal/RecDemoRuns/aaai27_e01_gzero_trace_20260711_r7_3579421`
- report SHA-256: `7a0d8c0a8a89c96b17fd0831755640329d027955bb3446817d37a35c7e68796e`
- execution-log SHA-256: `223ca144e81e96425e0db3a3e72f809ffadc1a59ce6986bbedfb25e53eb4d2efa`
- terminal status: `fail`
- first divergence: `step=1 / training / host / NotImplementedError`
- exact cause: host `graph.p1` is on `cpu`, while model/noise and 24 other optimizer parameters are on `cuda:1`; AMP scaler is enabled and fails on the CPU gradient in `scaler.unscale_`.
- context evidence: `graph_parameter_devices={"cpu":1}`, `optimizer_parameter_devices={"cpu":1,"cuda:1":24}`, `scaler_enabled=true`
- RISK-02 pass marker: `absent`
- training authorization: `false`
- training result: `none`
- retry exercised: `false`

This attempt is terminal root-cause evidence. It identifies a device-placement
bug in the production graph factory; it does not establish an E1 scientific pass.
