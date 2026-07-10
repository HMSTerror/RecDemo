# ADAPT-02-R11 terminal attempt manifest

- Attempt: `ADAPT-02-R11` (E1 Beauty g=0 lockstep, seed 100)
- Source commit: `09c4a4a` (R10 implementation); launch bundle: `aaai27_controller_20260711_r11_c309ccf.tar`, SHA256 `57794228e9585b7f7e8bc7225c4ad296659a00b9a45eea2c63fa04c452dec23c`
- Remote bundle root: `/data/Zijian/goal/RecDemo_aaai27_controller_20260711_r11_c309ccf`
- Remote output root: `/data/Zijian/goal/RecDemoRuns/aaai27_e01_gzero_trace_20260711_r11_c309ccf`
- Report SHA256: `0fea794cb207089e08a717f1d804d4c9fd8c29c3382cfe1364ac25ad9f9b3f8a`
- Execution log SHA256: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` (empty raw log; tmux pane was read-only inspected before the session exited)
- Terminal status: `fail`; downstream launch authorization: `false`; RISK-02 pass marker: absent.
- Checkpoints: `step 0=pass`, `step 1=pass`, `step 100=fail`, `step 1000=fail`.
- First divergence: `step=100`, arm `final_v2_closed_gate_full`, category `loss_terms`, key `raw_score_entropy`, max absolute difference `3.814697265625e-06` under FP32 tolerance `1e-6`.
- Step-1000 continuation: gradient `core_proposal_logits`, max absolute difference `1.7670216038823128e-05`.
- R10's direct `p_core_full` closed-gate path reduced the step-100 drift but did not remove it. This is evidence that a remaining host/proposal graph or loss-kernel path differs after the proposal tensor is equal.
- No continuation training was launched. R11 is closed; R12 must be a new dated attempt.

## Audit commands

```text
ssh zijian@172.18.0.40 "sha256sum /data/Zijian/goal/RecDemoRuns/aaai27_e01_gzero_trace_20260711_r11_c309ccf/e01_gzero_trace.json /data/Zijian/goal/RecDemoRuns/aaai27_e01_gzero_trace_20260711_r11_c309ccf.execution.log"
scp zijian@172.18.0.40:/data/Zijian/goal/RecDemoRuns/aaai27_e01_gzero_trace_20260711_r11_c309ccf/e01_gzero_trace.json .
```
