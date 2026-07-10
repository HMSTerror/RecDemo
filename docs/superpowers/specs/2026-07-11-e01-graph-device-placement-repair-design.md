# E1 R8 graph-device placement repair

## Root cause

R7 captured the production boundary failure at trace step 1 on the host arm:
`AdaptiveWise.p1` remained on CPU because `graph_lib.get_graph(config, device)`
ignored its `device` argument. The optimizer therefore contained one CPU
parameter and 24 CUDA parameters, and the enabled CUDA AMP scaler failed while
unscaling the CPU gradient.

## Minimal repair

Make the graph factory move the newly constructed `nn.Module` to the requested
device before returning it. The repair applies to every graph type through the
same factory return path; it changes placement only, not initialization values,
random seed, graph formulas, proposal rows, optimizer membership, evaluator,
sampling layout, tolerance, or corruption.

## Frozen constraints

- Keep seed `100`, `cuda:1`, trace steps `0, 1, 100, 1000`, FP32 tolerance
  `1e-6`, all three arms, and the production evaluator unchanged.
- Do not drop the graph parameter from the optimizer or disable AMP.
- Preserve all R1--R7 artifacts; create one new isolated R8 bundle/output root.
- The first attempt is single-run and fail-closed. A failure creates no pass
  marker and unlocks no training continuation.

## Acceptance

1. A focused factory test proves an `adaptive` graph's `p1` is on the requested
   device (using the CPU-independent `meta` device in the local test) and that
   parameter-free proposal graphs remain constructible.
2. Existing graph/E1/controller tests and compile checks pass.
3. The remote R8 trace reaches the structured checkpoints. It is an E1 pass only
   if steps 0, 1, 100, and 1000 have no failed comparisons and all hard gates
   validate; otherwise it remains terminal fail with no continuation launch.
