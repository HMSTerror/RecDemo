# Task packet: 2026-07-10 Gate-2 wording amendment

## Scope

Apply one synchronized English/Chinese claim correction to `paper/main_v2.tex` and `paper/main_v2_zh.md`. Preserve frozen Table 2 metrics. The amendment is evidence-constrained by E0, E1, E7, CLOSE-02, and the provenance-limited CLOSE-10 artifact.

## Inputs

- `docs/reports/data/2026-07-10-evaluator-amendment/e0_evaluator_amendment.json`
- `docs/reports/data/2026-07-10-e01-gzero-production-trace/e01_hard_stop.json`
- `docs/reports/data/2026-07-10-e07-u-ds-bootstrap-evidence-gate/e07_evidence_gate.json`
- `docs/reports/data/2026-07-07-close02-ml1m-noise-floor/close02_ml1m_noise_floor_report.json`
- `docs/reports/data/2026-07-10-close10-atg-noise-floor-provenance-limited/close10_atg_provenance_limited_report.json`
- User-approved Gate-2 wording rules dated 2026-07-10

## Allowed edits

- `paper/main_v2.tex`
- `paper/main_v2_zh.md`
- This dated amendment directory
- `plan/progress.md` and its dated task packet

## Required outcomes

- Restrict the TV claim to proposal and one-step forward transition-row kernels.
- Treat `1/24` as a descriptive exchangeability calculation.
- Use one closed-gate ML1M miss plus one barely-open ATG `phi=0.117` miss.
- Record the E1 step-0 optimizer-ownership hard stop and the resulting downstream no-launch decision.
- Describe CLOSE-10 only as a provenance-limited observed three-run spread; state that all three manifests are absent.
- Remove final-v2 corruption-response empirical wording because E3 was not launched.
- Confirm DiffuRec corrected-test evaluator comparability without checkpoint-selection-equivalence language.
- Add the validation-only model-selection and development-time test-logging disclosure.
- Keep all frozen Table 2 metric cells unchanged.

## Rejection checks

Reject the amendment if it introduces an end-to-end performance bound, a confirmatory interpretation of `1/24`, an unqualified ATG noise-floor claim, any claim that the E1 production paths matched, any final-v2 corruption-response empirical claim, any checkpoint-selection-equivalence claim, or any description of the test set as an untouched final holdout.

## Validation

Verify the actual paper diff, patch replay blocks, JSON parsing, source and package SHA-256 values, English/Chinese semantic pairing, frozen metric rows, prohibited-claim scans, and the best available LaTeX build.
