# E1 kernel-reduction repair design

## Evidence and root cause

The R1 trace failed at `step=0` because arm-specific construction consumed different RNG states. R2 normalized the post-construction trace-start state and preserved the construction hashes, but the failure remained after the production validation sampler. R2 then showed later gradient, loss-term, optimizer, parameter, and sampling failures.

A controlled CPU reproduction with identical host `p1` and proposal rows shows the remaining production mismatch:

- `AdaptiveWise.sample_nonpreference` uses `torch.multinomial` on a one-dimensional probability vector.
- `ProposalAdaptiveWise.sample_nonpreference` uses elementwise Gumbel `sample_categorical`, consuming a different number of random values and producing different draws.
- The same mismatch exists in `sample_prob`.

The deterministic rate, probability, and reverse-kernel methods already agree when the proposal rows equal the host `p1`; the stochastic sampling boundary is the next root cause.

## Options considered

1. Change only the E1 comparator to ignore post-sampler RNG. Rejected: it would weaken the registered production-path claim and leave the host/proposal stochastic kernels inconsistent.
2. Bypass the proposal graph in the trace and feed host samples. Rejected: it would not exercise the production path.
3. Use a shared distribution-preserving sampler in both production graph classes. Selected: it preserves per-row proposal probabilities, makes the `g=0` reduction exact when rows are constant, and leaves non-constant proposal rows on a batched multinomial path.

## Implementation boundary

Add one helper in `graph_lib.py` that accepts either a one-dimensional probability vector or a row-wise probability tensor:

- one-dimensional/row-constant input: one `torch.multinomial` call with `B*L` draws, matching `AdaptiveWise`;
- non-constant row-wise input: flatten rows and draw one sample per row, then reshape;
- reject invalid probability ranks/shapes rather than silently flattening.

Use the helper in `AdaptiveWise.sample_nonpreference`, `AdaptiveWise.sample_prob`, `ProposalAdaptiveWise.sample_nonpreference`, and `ProposalAdaptiveWise.sample_prob`. Do not alter p1 values, optimizer ownership, seed, evaluator, trace steps, tolerance, or corruption assets.

## Verification contract

- RED: a CPU test reproduces the current host/proposal sample and RNG mismatch.
- GREEN: the same test passes for row-constant proposals and a separate test checks non-constant row-wise sampling.
- Regression: E1, front-gate, controller, compile, and whitespace suites pass.
- Remote: one isolated seed-100 E1 attempt on GPU1; any checkpoint difference is terminal for that attempt and must be diagnosed by a new dated row.
