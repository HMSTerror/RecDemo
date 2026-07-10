# E01 R6 attempt manifest

- attempt: `ADAPT-02-R6`
- code commit: `1aa33ec`
- bundle archive SHA-256: `5045bb04b503e4ffbbf9a7cff5a935a760b033bb1ba6748a4c7bcae9b5e23db2`
- remote bundle: `/data/Zijian/goal/RecDemo_aaai27_controller_20260711_r6_1aa33ec`
- remote interpreter: `/data/Zijian/goal/PreferGrow/.venv/bin/python3`
- dataset: `Beauty` (`seed=100`, `device=cuda:1`)
- tmux session: `aaai27_e01_r6`
- process PID: `2619054`
- output root: `/data/Zijian/goal/RecDemoRuns/aaai27_e01_gzero_trace_20260711_r6_1aa33ec`
- report SHA-256: `87dac60cd9a885a6442d9eef064d525bdbc889a33dfed7d9d98695da32431fad`
- execution-log SHA-256: `255f96cc17aec987e58fb55ef72d7d39e77c6ebc2c65dbc3af220621ec4a0b89`
- terminal status: `fail`
- first divergence: `preflight_or_execution_error / NotImplementedError`
- error: `aten::_amp_foreach_non_finite_check_and_unscale_` requested with CPU backend
- graph provenance emitted: `no` (exception occurred before report initialization payload)
- RISK-02 pass marker: `absent`
- training authorization: `false`
- training result: `none`
- retry exercised: `false`

This attempt is terminal diagnostic evidence only. It does not establish an E1
scientific pass or a graph-sampler cause.
