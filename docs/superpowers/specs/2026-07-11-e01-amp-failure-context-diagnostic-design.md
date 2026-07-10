# E1 R7 AMP failure-context diagnostic

## Purpose

R6 was a terminal execution failure rather than a graph-sampler result. The
production run reached the training boundary and raised
`NotImplementedError: aten::_amp_foreach_non_finite_check_and_unscale_` for the
CPU backend. R7 records the complete exception traceback and the last frozen
production phase/arm/step/device/scaler context so the failure can be attributed
to the exact call site before any repair is considered.

## Frozen constraints

- Keep seed `100`, `cuda:1`, trace steps `0, 1, 100, 1000`, evaluator, optimizer,
  model parameters, AMP/scaler configuration, and FP32 tolerance `1e-6` unchanged.
- Do not disable AMP, move parameters or gradients between devices, alter
  optimizer membership, modify the sampling kernel, change the dataset, or add a
  retry. R7 is evidence-only.
- Update one execution-context record immediately before each construction,
  initial-sampling, training-arm/step, and step-1000 evaluation boundary. The
  record must not call RNG, alter tensors, or catch/replace the underlying error.
- On failure, preserve the original exception type/message, add its full Python
  traceback and the last context record to the structured report, and write no
  pass marker.

## Acceptance

The isolated R7 report must prove which phase, arm, and trace step raised the AMP
error (or show a different terminal cause), include device and scaler state
without changing them, and record `training_started` and downstream authorization
as false unless a valid E1 pass is independently reached. R7 itself cannot unlock
seed100 continuation or any other experiment.
