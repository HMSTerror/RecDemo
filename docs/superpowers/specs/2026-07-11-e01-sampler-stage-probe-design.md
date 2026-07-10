# E1 sampler-stage probe design

R4 localizes the remaining divergence to the first p2 validation sampler call. The next diagnostic wraps only the first call for each arm and records RNG metadata around the internal boundaries:

1. `model.encode_history_context(history)`;
2. `graph.sample_nonpreference(...)`;
3. each predictor `update_fn` categorical draw;
4. the final denoiser categorical draw.

Each wrapper invokes the original operation exactly once and does not restore or reseed RNG. The probe therefore observes the production stream without changing it. It records shapes and operation names, and leaves all subsequent calls unwrapped. The result is diagnostic only: no pass marker or training launch is permitted.

The next implementation change must be selected only after the first divergent internal operation is observed. If the first difference is a sampler implementation mismatch, the repair must be a shared production kernel; if it is context encoding, the repair must preserve the closed-gate proposal values and remove only the unintended stochastic side effect.
