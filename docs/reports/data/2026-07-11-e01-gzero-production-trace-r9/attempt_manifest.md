# ADAPT-02-R9 terminal attempt manifest

- Attempt: `ADAPT-02-R9` (E1 Beauty g=0 lockstep, seed 100)
- Code commit: `ff82753`; bundle archive: `aaai27_controller_20260711_r9_ff82753.tar`
- Bundle archive SHA256: `08719c55c4d84fb8220abc2b4aabe9e0492fa80f75294496619476875844380d`
- Remote bundle root: `/data/Zijian/goal/RecDemo_aaai27_controller_20260711_r9_ff82753`
- Remote output root: `/data/Zijian/goal/RecDemoRuns/aaai27_e01_gzero_trace_20260711_r9_ff82753`
- Remote report: `e01_gzero_trace.json`; SHA256: `251a77a30bac58723aaae91c8f984a2da34fdb5d4ad21b8c1f829b3b5ccb3d69`
- Remote execution log SHA256: `41428caba5bdc277a023427eae20701d67f730bdf730e86e63c58a18802ce8ff`
- Terminal status: `fail`; downstream launch authorization: `false`; RISK-02 pass marker: absent
- Checkpoints: `step 0=pass`, `step 1=pass`, `step 100=fail`, `step 1000=fail`
- First divergence: `step=100`, arm `final_v2_closed_gate_full`, category `loss_terms`, key `raw_score_entropy`, max absolute difference `7.62939453125e-06` under FP32 tolerance `1e-6`.
- Step-1000 continuation: gradient `core_proposal_logits`, max absolute difference `2.2855587303638458e-05`.
- Interpretation: R9 removed the step-1 optimizer/EMA parameter-contract divergence; the remaining drift was isolated to the closed-gate proposal autograd path. R10 targets that path only.
- No continuation training was launched from this failed attempt. R1--R8 artifacts remain unchanged.

## Audit commands

```text
ssh zijian@172.18.0.40 "sha256sum /data/Zijian/goal/RecDemoRuns/aaai27_e01_gzero_trace_20260711_r9_ff82753/e01_gzero_trace.json /data/Zijian/goal/RecDemoRuns/aaai27_e01_gzero_trace_20260711_r9_ff82753.execution.log"
scp zijian@172.18.0.40:/data/Zijian/goal/RecDemoRuns/aaai27_e01_gzero_trace_20260711_r9_ff82753/e01_gzero_trace.json .
scp zijian@172.18.0.40:/data/Zijian/goal/RecDemoRuns/aaai27_e01_gzero_trace_20260711_r9_ff82753.execution.log .
```
