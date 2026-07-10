# E1 R12 row-constant score-entropy gradient repair

## Root cause

ADAPT-02-R11 passed steps 0 and 1 but diverged at step 100 in
`raw_score_entropy`. A focused CPU reproduction showed that host
`AdaptiveWise.score_entropy` and `ProposalAdaptiveWise.score_entropy` have
identical forward values for an identical row-constant proposal, while their
autograd gradients differ (maximum `7.629e-06`). The host path indexes one
probability vector and broadcasts it; the proposal path expands rows and uses
`gather`, producing a different reduction order. The R10 direct `p_core_full`
repair removed a redundant mixture path but could not remove this graph-kernel
path difference.

## Minimal repair

When the proposal input is rank-2 and every batch row is exactly identical,
evaluate `ProposalAdaptiveWise.score_entropy` with the same vector-indexing and
broadcast operations as `AdaptiveWise.score_entropy`. This is the registered
kernel-level closed-gate contract (`p_core_full` is an expanded row-constant
softmax). The existing rank-3 and row-varying proposal implementation is left
unchanged.

## Frozen constraints

- Keep seed `100`, CUDA device, trace steps `0,1,100,1000`, FP32 tolerance
  `1e-6`, optimizer/EMA membership, evaluator, selector, corruption, and all
  frozen artifacts unchanged.
- Do not alter nonzero-gate proposal values or introduce tolerance changes,
  retries, seed changes, or continuation launches.

## Acceptance

1. A focused regression test is RED before the repair and GREEN after it,
   proving exact forward and gradient identity for a row-constant proposal.
2. Existing graph, text-side, E1, and controller regressions pass.
3. One isolated remote R12 run on GPU1 reports `pass` at all four checkpoints
   and emits one valid RISK-02 marker; any failure closes R12 without training
   continuation.
