# Local evidence-integration protocol

## Data and split contract

- PreferGrow uses the archived `paper_raw_v1` train/validation/test frames and frozen item mapping.
- EPE/PNE inputs must be train-only; validation/test targets invalidate risk preflight evidence.
- Model selection is validation NDCG@10 only; test metrics were logged during development.
- The evaluator is `e0_full_tail_v2` for corrected comparisons and must be explicitly labeled when
  legacy values are retained.

## Result contract

- New training is outside this local task.
- r7 metrics may enter paper-facing outputs only through immutable task records, nonempty logs,
  nonempty artifact manifests, and nonempty best summaries bound to the frozen queue manifest.
- A missing arm, hash mismatch, unknown arm, duplicate identity, wrong seed, wrong evaluator, wrong
  selector, or nonterminal RISK-08 exit produces `not_ready`/failure, never a partial favorable table.
- Beauty results must show validation and test side by side.
- c100 is a `phi_R=0` production fallback sanity check, not evidence of learned adaptive collapse.

## Baseline contract

- E5 SASRec is the only completed external four-domain common-contract baseline currently eligible
  for local integration.
- Caser, GRURec, and DiffRec remain documented gaps until real adapters pass; DiffuRec is excluded
  from confirmatory comparison but its frozen artifacts remain preserved.

## Statistics

- All current added performance results are seed 100 single-run observations.
- The `1/24` quantity is a descriptive combinatorial fraction under exchangeability, not a
  confirmatory p-value.
- E7 uncertainty is `not_estimable` because frozen transition records lack user IDs; zero bootstrap
  replicates were executed.
