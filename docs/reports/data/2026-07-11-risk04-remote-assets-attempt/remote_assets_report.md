# RISK-04 remote asset attempt (2026-07-11)

This is a real l20 asset-generation attempt, not a training result. It used
the dated output root
`/data/Zijian/goal/RecDemoRuns/aaai27_risk04_assets_2026-07-11_ef84761_r2`
and the remote paper data under
`/data/Zijian/goal/RecDemo/dataset/paper_raw_v1`.

The first attempt was rejected before writing because its root used
`20260711` instead of the required `YYYY-MM-DD` form. It has been preserved as
a terminal failed attempt in the remote execution log; a new `_r2` root was
used and no old root was reused.

## Result

- Code revision: `ef84761e2c06af02bc6077e367b2a2d34956a568`.
- Datasets: Beauty and Steam.
- Levels: 0/20/40/60/80/100 for each dataset (12 bank manifests).
- Seed: 100; strata: 10; algorithm: popularity-stratified permutation of
  real-item embeddings with row-norm preservation.
- RISK-04 bundle file SHA-256: `dc2f728d0808f57117bc9b5c28f29fa103925e892df2fce185e98d1c2b181bcf`.
- Internal report artifact hash: `b4b345f9124dc349209b38ce4419cb953d5fbe1122d5edc555e936be2e33d6f5`.
- Remote validation: `status=pass` with `--allow-severe-gate-pending`.
- Row-norm maximum absolute difference: 0 at level 0 and at most
  `2.384185791015625e-07` at corrupted levels.
- GPU training started: **false**. GPU0 CLOSE-10 and GPU1 were not used by the
  asset builder (the builder ran on CPU).

## Severe gate

The severe gate remains `pending`: no train-only preflight `clean_mean_gate`
or Steam level-60 `mean_gate` has been supplied. Consequently
`training_start_authorized=false`; no RISK-05 freeze, pilot, or continuation
training may start from this asset root. The next scientific action is the
train-only preflight/evaluator report, followed by RISK-05 hash freeze.

Captured files:

- `risk04_config.json`
- `risk04_bundle.json`
- `RISK-04_PENDING.json`
- `SHA256SUMS`
- `aaai27_risk04_assets_2026-07-11_ef84761_r2.execution.log`
