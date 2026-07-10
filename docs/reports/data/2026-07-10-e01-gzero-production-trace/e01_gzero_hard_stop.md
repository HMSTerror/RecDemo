# E01 Production-Path G-Zero Trace — HARD STOP

## Decision

`AAAI-E01` reached the preregistered **HARD STOP**. The Beauty production paths are not deterministically equivalent at `g=0`: the first tracked difference occurs at step 0 in optimizer membership for the canonical core proposal parameter. Therefore `downstream_launch_authorized=false`, and E2, E3, E4, E5, and E8 must not launch in this sprint.

This is a single-run production trace with `random_seed=100`. It is not a training-seed variance study and it does not support significance, stability, equivalence, or within-noise language.

## Scope and protocol

- Dataset: Beauty only. It is the only frozen domain with the matched production trio `AdaptiveWise host`, `final-v2 closed-gate full`, and `global_p`; ML1M uses a hybrid host and is outside this equivalence claim.
- Arms: `host`, `final_v2_closed_gate_full`, and `global_p`.
- Trace steps: 0, 1, 100, and 1000.
- Frozen FP32 tolerance: `1e-6`.
- The canonical initialized parameter values aligned before training: `canonical_parameter_sha256=9f34d3c821bc073668cbf8784a3e5ffa619415c715a2798867cbf5738ef85320`.
- E0 prerequisite, Beauty asset hashes, normalized configuration contract, and ordered batch checks passed.

## First divergence and root cause

The earliest failed comparison is:

```json
{
  "step": 0,
  "category": "optimizer",
  "key": "core_proposal_logits.in_optimizer",
  "reference_arm": "host",
  "arm": "final_v2_closed_gate_full",
  "max_abs_diff": 1.0,
  "status": "fail"
}
```

The production ownership is different even though the copied initial value is aligned:

| Arm | Core proposal owner | Optimizer consequence |
|---|---|---|
| `host` | `graph.p1` | canonical proposal parameter is not owned by the model optimizer |
| `final_v2_closed_gate_full` | `model.text_side_builder.p1` | canonical proposal parameter is owned by the model optimizer |
| `global_p` | `model.text_side_builder.p1` | canonical proposal parameter is owned by the model optimizer |

No optimizer ownership was normalized after observing the result. Doing so would change the production path and would not be a valid demonstration of the preregistered reduction.

## Divergence progression

| Step | Failed comparison counts | Selected maximum absolute differences |
|---:|---|---|
| 0 | optimizer 18; RNG 6 | optimizer membership `1.0` |
| 1 | gradients 46; loss terms 16; optimizer 72; RNG 6 | core proposal gradient `0.1586687267` |
| 100 | gradients 46; loss terms 16; optimizer 74; parameters 46; RNG 6; sampling 2 | core proposal parameter `0.0001971722`; p5 logits `3.4511e-05` |
| 1000 | gradients 46; loss terms 16; optimizer 74; parameters 48; RNG 6; sampling 10 | core proposal gradient `3.1849598885`; core proposal parameter `0.0113682747`; p5 logits `0.9984807372` |

The evidence therefore shows a step-0 production-topology mismatch followed by gradient, loss, parameter, and sampling-trajectory separation. It must not be described as seed noise.

## Launch and manuscript consequences

- E2 / E3 / E4 / E5 / E8: no launch authorization.
- No rescue tuning, second seed, or ownership patch is authorized in this 48-hour sprint.
- The paper must not claim that an end-to-end exact reduction has been demonstrated.
- The bounded-downside statement remains restricted to the proposal / one-step transition-row kernel-level TV bound; it is not a bound on training loss, ranking metrics, the full trajectory, or end-to-end performance.

## Provenance and audit limitation

- Remote run root: `/data/Zijian/goal/RecDemoRuns/aaai27_e01_gzero_trace_20260710_50e8e7b`
- Source trace SHA-256: `1ca4972357afb860f7e4b99b60711f28dc41ccd7e3192ae7aeff6351dc3cb70c`
- Trace generated at: `2026-07-10T18:08:17+08:00`
- The sibling execution log was archived exactly as found but is zero bytes. It is not used as positive execution evidence; the structured trace, pass-marker absence, source hashes, and remote filesystem metadata are the auditable evidence.
- `E01_PASS.json` was absent on the remote run, as required for a failed gate.

The filesystem interval from execution-log creation (`18:06:30 +08:00`) to trace generation (`18:08:17 +08:00`) is approximately 1 minute 47 seconds. This is a timestamp-derived runtime estimate, not an in-log timer.
