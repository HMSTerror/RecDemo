# E1 RNG-boundary repair attempt (2026-07-11, seed 100)

- Attempt identity: `ADAPT-02-R2`; a new dated attempt after the R1 step-0 RNG failure.
- Code revision: `e0459b5`.
- Bundle: `/data/Zijian/goal/RecDemo_aaai27_controller_20260711_r2_e0459b5` (archive SHA256 `f8f8b45fdca3d34b4bf6db353ff26602d3ac2b03f388def98838f7824cf5857d`).
- Remote session/PID: `aaai27_e01_r2` / `2589921`; physical GPU 1 through `CUDA_VISIBLE_DEVICES=1`.
- Protocol: Beauty production trio (`host`, `final_v2_closed_gate_full`, `global_p`), trace steps `0,1,100,1000`, FP32 tolerance `1e-6`, fixed random seed `100`.
- Remote output: `/data/Zijian/goal/RecDemoRuns/aaai27_e01_gzero_trace_20260711_r2_e0459b5/e01_gzero_trace.json`.
- Remote execution log: `/data/Zijian/goal/RecDemoRuns/aaai27_e01_gzero_trace_20260711_r2_e0459b5.execution.log`.
- Local artifact hashes:
  - `e01_gzero_trace.json`: `6a2058a13b1131d88bdf9ef9ed2af0d505e8e7e9731cccb02068728310987bc0`
  - `e01_gzero_trace.execution.log`: `663c11d34d7699f1e8aca4caf2bac77cbd38fbf0eb1015ad2d4eebe999f80850`

## Result

`status=fail`. The repair worked at the intended boundary: the report's `initialization.rng_boundary` records one identical `trace_start` hash for all three arms and preserves distinct construction hashes. However, the first comparable checkpoint still diverges after the production validation sampler:

```text
step: 0
category: rng
key: combined_sha256
reference_arm: host
observed_arm: final_v2_closed_gate_full
reference_sha256: 081a935abc0c8aaa8515886b0429071afc7590b15ebad504506544881ca28e11
observed_sha256: 8de0a135bfe3bde1ea50ec8295b01ace5332e0bdaf2e815d358e18cf86f80ceb
```

The report also shows later non-RNG divergences: at step 1 there are gradient, loss-term, optimizer, and RNG failures; at steps 100 and 1000 there are additional parameter and sampling-probe failures. A controlled CPU probe confirms the host `AdaptiveWise` and proposal `ProposalAdaptiveWise` sampling methods consume different RNG amounts and produce different draws even when the proposal vector is exactly the host `p1` vector: host uses `torch.multinomial`, while proposal uses elementwise Gumbel sampling. This is a production graph-kernel mismatch, not a remaining constructor-RNG problem.

No retry, rescue tuning, threshold change, seed change, or downstream training was performed. No pass marker was written; the R2 process and tmux session terminated after the terminal report.
