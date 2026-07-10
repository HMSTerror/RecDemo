# E1 R6 graph-initial provenance diagnostic

## Purpose

R5 identified the first production divergence at the `graph.sample_nonpreference`
boundary. The three arms enter that boundary with identical normalized RNG state,
and their `encode_history_context` calls do not consume RNG. R6 must therefore
distinguish an unequal probability input from a CUDA sampling-layout/kernel
difference without changing scientific behavior.

## Frozen constraints

- Keep seed `100`, CUDA production arithmetic, trace steps `0, 1, 100, 1000`, and
  FP32 tolerance `1e-6` unchanged.
- Do not modify evaluator semantics, model parameters, optimizer membership,
  proposal values, corruption, frozen artifacts, or pass/fail thresholds.
- Wrap only the first p2 validation sampler call for each arm.
- The shared `_sample_probability_rows` operation is called exactly once by the
  wrapper and is restored immediately after the call; no RNG state is captured,
  restored, or reseeded by the probe.
- Preserve all prior dated attempts and create one new isolated output directory.
- A diagnostic failure is terminal for R6 and cannot unlock training or another
  experiment. A later repair requires a new ledger row and a new dated attempt.

## Evidence recorded

At the graph-initial boundary, record for each arm:

1. the RNG metadata immediately before and after `graph.sample_nonpreference`;
2. the probability tensor passed to `_sample_probability_rows`, including dtype,
   device, shape, stride, contiguity, finite-value range, row-sum summary, and a
   content hash;
3. the `batch_shape` passed to the sampler helper;
4. the sampled output tensor with the same layout and content metadata; and
5. a comparison summary identifying the first arm/input/layout/output difference.

This stage boundary is sufficient to decide whether the next change belongs in
proposal construction or in the shared CUDA sampling representation. R6 does not
attempt either repair.

## Acceptance

The attempt is valid only if the isolated report and manifest hash the complete
bundle, identify the first graph-initial difference (or prove all inputs and
layouts equal), preserve `status=fail` for the existing E1 divergence, and record
that no pass marker or training process was created.
