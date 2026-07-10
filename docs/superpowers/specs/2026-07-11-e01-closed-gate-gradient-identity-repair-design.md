# E1 R10 closed-gate gradient identity repair

## Root cause

R9 made clipping, optimizer membership, and EMA ownership identical. Step 0 and
step 1 then passed, but step 100 first diverged in `raw_score_entropy` by
`7.62939453125e-06`. The closed-gate proposal had the same forward value as
`p_core = softmax(p1)` yet was produced through real-core renormalization and a
zero-weight mixture. That introduces a different autograd path and accumulates
small gradient/parameter differences over many steps.

## Minimal repair

For the registered kernel-level closed gate only (`injection_mode="kernel"` and
dataset scale exactly `0.0`, or the registered `global_p` ablation), return the
already-computed `p_core_full` tensor as `context["proposal"]`. Keep the existing
adaptive/anchor calculations and all non-closed-gate paths unchanged. This is a
gradient-path repair, not a value/tolerance/seed change: the forward proposal is
the core proposal required by the g=0 contract.

## Frozen constraints

- Keep seed `100`, CUDA device, evaluator, optimizer/EMA contract, trace steps,
  FP32 tolerance `1e-6`, and all dataset assets unchanged.
- Do not alter `g_max`, content bank, proposal values at nonzero g, text utility,
  corruption, selector, or paper claims.
- Preserve R1--R9 and run one isolated R10 attempt only. Failure creates no pass
  marker and unlocks no continuation.

## Acceptance

1. A RED/GREEN test proves the closed-gate proposal gradient is exactly the
   gradient of `softmax(p1)` under a fixed weighted readout; non-closed encoder or
   loss injection paths retain their anchor behavior.
2. Existing text-side, E1, graph, controller, and compile regressions pass.
3. Remote R10 must have no failed comparisons at 0, 1, 100, or 1000 before E1
   can be marked pass.
