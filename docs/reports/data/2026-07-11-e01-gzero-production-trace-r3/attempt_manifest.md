# E1 shared stochastic-kernel repair attempt (2026-07-11, seed 100)

- Attempt identity: `ADAPT-02-R3`; a new dated attempt after R2 isolated the production sampling mismatch.
- Code revision: `410da7c`.
- Bundle: `/data/Zijian/goal/RecDemo_aaai27_controller_20260711_r3_410da7c` (archive SHA256 `bf7b73f716584ee2fbe36aa7f83ada13b7515221d59fe2562a6f28a5ca27501a`).
- Remote session/PID: `aaai27_e01_r3` / `2597266`; physical GPU 1 through `CUDA_VISIBLE_DEVICES=1`.
- Protocol: Beauty production trio (`host`, `final_v2_closed_gate_full`, `global_p`), trace steps `0,1,100,1000`, FP32 tolerance `1e-6`, fixed random seed `100`.
- Remote output: `/data/Zijian/goal/RecDemoRuns/aaai27_e01_gzero_trace_20260711_r3_410da7c/e01_gzero_trace.json`.
- Remote execution log: `/data/Zijian/goal/RecDemoRuns/aaai27_e01_gzero_trace_20260711_r3_410da7c.execution.log`.
- Local artifact hashes:
  - `e01_gzero_trace.json`: `31fc126198d713938a248c8aa77205641253186f51066f03c87c77c780358400`
  - `e01_gzero_trace.execution.log`: `dd7efa53b42945cbc61b0210d5179db943a57aa5241bb3bd4a1ad041801a1e93`

## Result

`status=fail`. The shared helper passes the dedicated CPU tests and preserves row-wise proposal sampling, but the production trace still reports a step-0 RNG divergence after initial validation sampling:

```text
step: 0
category: rng
key: combined_sha256
reference_arm: host
observed_arm: final_v2_closed_gate_full
reference_sha256: 1c3b14ca8af2434cfa1abade23f81c5968cdc41507d59a34ae8ac47dab5b988a
observed_sha256: 8de0a135bfe3bde1ea50ec8295b01ace5332e0bdaf2e815d358e18cf86f80ceb
```

The normalized trace-start hash remains identical for all arms (`045004e1aa5085b9bc2c5a99fc9e751ec65625318efc8ca68496198b551c9777`), so R2's constructor-RNG issue is not the remaining cause. The production path still has later gradient/loss/optimizer/parameter/sampling failures. The next diagnostic must record RNG metadata at each initial-validation sampling call to identify which production operation consumes the unmatched stream.

No retry, rescue tuning, threshold change, seed change, or downstream training was performed. No pass marker was written; the R3 process and tmux session terminated after the terminal report.
