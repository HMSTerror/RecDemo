# E1 per-stage RNG diagnostic (2026-07-11, seed 100)

- Attempt identity: `ADAPT-02-R4`; behavior-preserving instrumentation after R3.
- Code revision: `c84b79e`.
- Bundle: `/data/Zijian/goal/RecDemo_aaai27_controller_20260711_r4_c84b79e` (archive SHA256 `04363fe5837dc77cc4034c30b1e297434060c7f9af1b21e05c544aaa00afec3a`).
- Remote session/PID: `aaai27_e01_r4` / `2603715`; physical GPU 1 through `CUDA_VISIBLE_DEVICES=1`.
- Protocol: Beauty production trio, seed `100`, trace steps `0,1,100,1000`, FP32 tolerance `1e-6`.
- Remote output: `/data/Zijian/goal/RecDemoRuns/aaai27_e01_gzero_trace_20260711_r4_c84b79e/e01_gzero_trace.json`.
- Local report SHA256: `da31b056077d487c75d80fc18cbb9fd527ad00337e99ccaa8935032fc82553aa`.
- Local log SHA256: `c9a25b40535e93f3c3d86d854b834fce132ba4be53f344d54db77cf26fe417df`.

## Localization result

The normalized trace-start and validation-loader iterator states are identical for all three arms. The first divergence occurs inside the first production p2 sampler call:

```text
stage: initial validation sampler call 0
batch_dims: [256, 1]
history_shape: [256, 10]
before hash (all arms): 5261a5a03242ae4d0d471d420ab7a749cbd83fb01d7eb9daddc2a4a8682ca949
host after: 6da31f2434a96be92c918b1ebff31fb92329c19f825ada01b57b609d5517aea7
final/global after: 33cdbb9a6c0c25b6f73bab00066117bc1c88a98a8bfbbc27e862d7c4a0ddf0ab
```

All subsequent sampler-call boundaries remain consistently offset. Therefore the remaining issue is inside the production sampler call itself, before training step 1; constructor RNG and DataLoader iterator creation are ruled out. R4 does not identify which internal operation (context encoding, initial graph draw, predictor draw, or denoiser draw) is responsible, so a finer sampler-stage probe is required.

`status=fail`, no pass marker, no training, no retry, and no frozen artifact mutation.
