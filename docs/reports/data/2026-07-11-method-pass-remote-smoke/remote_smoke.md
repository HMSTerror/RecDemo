# l20 ADAPT-04 remote bundle smoke (2026-07-11)

Scope: remote bundle verification and controller no-op smoke only. No
scientific training, corruption-bank generation, evaluator run, checkpoint
write, or method-pass continuation was launched.

## Connection and resources

- SSH target: `l20`; hostname: `ubuntu`.
- Observation time: `2026-07-11 12:32:39 +0800`.
- GPU0: NVIDIA L20, 46,068 MiB total, 8,033 MiB used, 100% utilization. The
  known CLOSE-10 process is PID `2568867`; it was not touched.
- GPU1: NVIDIA L20, 46,068 MiB total, 12 MiB used, 0% utilization.
- `/data`: 79 GiB available; the 40 GiB queue gate is currently satisfied.
- Remote RAM: 62 GiB total, 56 GiB available, no swap.

## Bundle identity

Bundle root: `/data/Zijian/goal/aaai27_method_pass_bundle_20260711_c7be478`.

The following local/remote SHA-256 pairs matched:

| File | SHA-256 |
|---|---|
| `scripts/aaai27_adapters/continuation_adapters.py` | `fb9c5fc9f3b5d780fb64690356c8f6bf74ccc1359378f9f5475e2c114ff4689f` |
| `scripts/aaai27_adapters/common.py` | `90552562dcf47e2e93c908e5ce23ce14fd2faa460bbdbc29b048aa3c177c3bce` |
| `scripts/aaai27_queue/validation.py` | `ee95456a843ad710a2847a5ab6c1f97a977ef1a9ed3665521f307335e4d7448c` |
| `scripts/build_method_pass_manifest.py` | `e2fa8f15342337d5685e724a3059d3bb11cd618708089daf8d48b66416538de1` |
| `scripts/verify_method_pass_gate.py` | `c30dd3413fd1a360864b3248cbb959cfed592be9bcf8fd6c3260e357c6919ce0` |
| `scripts/aaai27_resident_queue.py` | `824a13c31f4ee9acb982c13b8f94270a6e6a79c3d1d9f1446242a21c5b3ba3ad` |

Remote focused adapter tests: `5 passed in 0.20s`.

Remote `compileall`: passed. Direct CLI `--help` probes: passed.

Remote no-op smoke root:
`/data/Zijian/goal/aaai27_method_pass_smoke_20260711_c7be478`.
The controller returned `status=smoke_pass`, `training_started=false`; only
`markers/SMOKE_PASS.json` exists and there is no `runs/` directory or training
PID.

## Launch decision

The remote hard stop remains active: only the E1 R12 `RISK-02_PASS.json` exists
on l20. No production RISK-04 bundle, RISK-05 freeze, or artifact-backed
RISK-08 `risk_gated_method` marker exists. Therefore no actual seed-100
training was started. The next authorized action is to build the real dated
RISK-04 assets and train-only RISK-05 preflight, then run the frozen pilot and
produce RISK-08; continuation cannot be scheduled from this smoke artifact.
