# E1 dated production-trace attempt (2026-07-11, seed 100)

- Attempt identity: `ADAPT-02-R1`; this is a new dated attempt and does not replace the earlier preflight failure.
- Bundle: `/data/Zijian/goal/RecDemo_aaai27_controller_20260711_r1_5268a8c` (source archive SHA256 `3ef279c265f5378f49ebdb41b248f8f706bc347644f76da08a351036bcf20af3`).
- Remote session/PID: `aaai27_e01_r1` / `2578104`; physical GPU 1 through `CUDA_VISIBLE_DEVICES=1`.
- Protocol: Beauty production trio (`host`, `final_v2_closed_gate_full`, `global_p`), trace steps `0,1,100,1000`, FP32 tolerance `1e-6`, fixed random seed `100`.
- Remote output: `/data/Zijian/goal/RecDemoRuns/aaai27_e01_gzero_trace_20260711_r1_5268a8c/e01_gzero_trace.json`.
- Remote execution log: `/data/Zijian/goal/RecDemoRuns/aaai27_e01_gzero_trace_20260711_r1_5268a8c.execution.log`.
- Local artifact hashes:
  - `e01_gzero_trace.json`: `5af6d9405d2d7bfbc0c18bfb4534d0e4a804e459384fc7a7f96c52a5f333b4fb`
  - `e01_gzero_trace.execution.log`: `9b36d532b8168d6f55c142b767406d448e2da5950b927c67596d5fff13e4708d`

## Terminal result

`status=fail` at the registered first checkpoint (`step=0`). The structured report identifies:

```text
category: rng
key: combined_sha256
reference_arm: host
observed_arm: final_v2_closed_gate_full
reference_sha256: 081a935abc0c8aaa8515886b0429071afc7590b15ebad504506544881ca28e11
observed_sha256: 8de0a135bfe3bde1ea50ec8295b01ace5332e0bdaf2e815d358e18cf86f80ceb
max_abs_diff: null (hash-level exact comparison)
```

This is a scientific/protocol divergence at step 0, not an import or preflight error. The report records `downstream_launch_authorized=false`. No `RISK-02_PASS.json`, no seed-100 training, and no retry/rescue/tolerance/corruption change was performed. The GPU1 process and tmux session terminated naturally after writing the terminal report; the existing GPU0 task was not touched.
