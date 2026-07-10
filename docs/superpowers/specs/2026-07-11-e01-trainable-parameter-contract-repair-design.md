# E1 R9 trainable-parameter contract repair

## Root cause

R8 moved host `graph.p1` to CUDA and reached training. Step 0 passed exactly,
but step 1 showed a large optimizer-state difference although raw gradients,
loss terms, parameters, proposals, and RNG were within the frozen `1e-6`
comparison rule. The production `losses.get_step_fn` passed only
`model.parameters()` to gradient clipping and EMA. Therefore host excluded its
graph-owned core proposal parameter while proposal arms included their
`text_side_builder.p1`; the two arms optimized different effective parameter
sets.

## Minimal repair

Introduce one explicit `training_parameters` list in each production state:
all model parameters plus the graph's core `p1` exactly once, excluding noise
parameters. Use that same list for gradient clipping, EMA update, and EMA
store/copy/restore. Keep the optimizer's existing `compose_optimizer_parameters`
membership (model + graph core p1 + noise) unchanged; do not alter formulas,
learning rate, AMP, seed, evaluator, proposal values, or checkpoint selector.

## Frozen constraints

- Seed `100`, `cuda:1`, trace steps `0,1,100,1000`, tolerance `1e-6`, and all
  existing E1 arm/config contracts remain frozen.
- No noise parameter enters EMA solely because it is in the optimizer; EMA is
  still model plus canonical graph core p1.
- Preserve R1--R8 and create one isolated R9 attempt. A failed R9 creates no
  pass marker and unlocks no continuation.

## Acceptance

1. A RED/GREEN unit test proves `losses.get_step_fn` sends the explicit training
   list (including an extra graph parameter) to optimize and EMA operations.
2. Existing E1/graph/controller tests and compile checks pass.
3. The remote R9 trace has no failed comparisons at steps 0, 1, 100, and 1000;
   only then may RISK-02 pass validation and seed100 continuation be considered.
