# ADAPT-02-R12 terminal attempt manifest

- Attempt: `ADAPT-02-R12` (E1 Beauty g=0 lockstep, seed 100)
- Source commit: `0338cc219f9ee983b8e9464b4df85f34471c7d6f`
- Bundle archive: `aaai27_controller_20260711_r12_0338cc2.tar`; SHA256 `a932457291187ea9b054605752e08b04105434a2374d428e7d0d3a58f427f0ba`
- Remote bundle root: `/data/Zijian/goal/RecDemo_aaai27_controller_20260711_r12_0338cc2`
- Remote output root: `/data/Zijian/goal/RecDemoRuns/aaai27_e01_gzero_trace_20260711_r12_0338cc2`
- Trace report SHA256: `b912d5b6807320e9466048bc6e98ec470e85e510433b3471c65c94a569e387ce`
- `E01_PASS.json` SHA256: `1da54cf25f936a7b09397cf78f14162f3ab02e0caa1c46dfa2d3aba4b37c017f`
- `RISK-02_PASS.json` SHA256: `040afa9328e05ba6fcfb36b26ae561657236a0d0a033e97e9ceb7c9a40a2924c`
- Raw execution log SHA256: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` (empty; structured report and pass marker are the authoritative terminal artifacts)
- Terminal status: `pass`; downstream launch authorization: `true`.
- Protocol: seed `100`, FP32 tolerance `1e-6`, trace steps `0,1,100,1000`, arms `host`, `final_v2_closed_gate_full`, `global_p`.
- Checkpoints: all four `pass`; `2986` comparisons, `0` failed; `first_divergence=null`.
- Pass-marker checks: `E01_PASS.json.trace_report_sha256` equals the report hash; exactly one `E01_PASS.json` and one `RISK-02_PASS.json` exist in the isolated output; no fail marker exists.
- No method-pass continuation was launched by the E1 runner. Any continuation must go through the separately validated controller/RISK-08 method decision.

## Audit commands

```text
ssh zijian@172.18.0.40 "sha256sum /data/Zijian/goal/RecDemoRuns/aaai27_e01_gzero_trace_20260711_r12_0338cc2/e01_gzero_trace.json /data/Zijian/goal/RecDemoRuns/aaai27_e01_gzero_trace_20260711_r12_0338cc2/E01_PASS.json /data/Zijian/goal/RecDemoRuns/aaai27_e01_gzero_trace_20260711_r12_0338cc2/RISK-02_PASS.json"
ssh zijian@172.18.0.40 "nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv,noheader; ps -p 2568867 -o pid,lstart,etime,pcpu,pmem,args=; df -Pk /data"
```
