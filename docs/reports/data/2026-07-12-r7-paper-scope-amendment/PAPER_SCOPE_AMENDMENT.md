# r7 paper-scope and deadline-gate amendment

Date: 2026-07-12 (Asia/Shanghai)

Status: paper-facing evidence amendment for P0-6. It does not modify any frozen experiment, selector, evaluator, seed, corruption level, threshold, queue manifest, or RISK-08 criterion. It does not report an r7 performance result.

## 1. Scientific arbitration

The manuscript now treats three objects as separate evidence generations:

1. Legacy `U_ds` is a train-only popularity-negative AUC discovery descriptor. Its first-generation inverse ordering is 4/4 only on the archived scale; the corrected common evaluator swaps adjacent Beauty/ATG and gives 3/4 strict agreement while preserving the Steam/ML1M endpoint contrast.
2. RISK-03 EPE/PNE@10 is a train-only observed-next-positive exposure audit. EPE is mean log excess proposal mass at the observed next positive; PNE@10 is a frozen-neighborhood mass view. Neither is a complete false-negative rate or an end metric. E7 is `not_estimable`: requested replicates 1000, executed replicates 0, because user IDs are absent.
3. Controlled `phi_R` is the dated evidence-retention/corruption-reliability intervention used by r6a/r7. For the frozen Beauty/Steam ladders it is increasing in EPE. The sign and numbers remain frozen, but the paper no longer calls it proof that high exposure automatically closes the gate.

The generalized manuscript gate is `g=g_max s_D clip(u_tilde,0,1)`, where each experiment declares whether `s_D` is legacy `phi_U(U_ds)` or controlled `phi_R`. The mathematical exact-reduction and one-step TV statements do not depend on how the frozen scale was obtained; the empirical interpretation does.

## 2. Controlled-corruption wording

- Steam c60 is a seed-100 single-run directional observation with validation and test moving in the same direction.
- Beauty c0/c60 are test-only positive observations because validation is approximately parity. Every presentation co-locates validation and test and discloses development-time test logging.
- c100 is an explicit `phi_R=0` fallback sanity check. Selected best summaries are byte-identical to the matched host, while checkpoints differ because full arms serialize text-side state.
- The withdrawn `u_tilde`-collapse/adaptive-user-backoff explanation is absent from positive manuscript prose.
- r6a cannot enter RISK-08 because anchors, per-run manifests, and nonempty run-local logs are missing. No r7 metric is reported before a same-root immutable exit exists.

## 3. Baseline arbitration

SASRec is the sole confirmatory external architecture under the project's common split, mapping, full-catalog evaluator, and validation-only selector. Its method citation was verified against Crossref on 2026-07-12: Kang and McAuley, *Self-Attentive Sequential Recommendation*, ICDM 2018, pp. 197--206, DOI `10.1109/ICDM.2018.00035`. The project's four-domain numeric table remains grounded in the E5 atomic artifact, not in the original paper. The Beauty validation-to-test drop is explicitly unresolved.

DiffuRec is excluded from confirmatory comparison. It remains only in related work and evaluator-audit provenance.

## 4. Reproducibility disclosure

The English and Chinese drafts state: model selection used validation only; test metrics were logged during development. The test split is therefore not described as an untouched final holdout. Every seed-100 outcome is scoped as a single-run observation, with no significance, cross-seed stability, equivalence, or within-noise claim.

## 5. Mechanical deadline gates

- 2026-07-16 evening: if r7 has started/completed and the original RISK-08 contract is executable, retain the full-submission path; if GPU remains unavailable but paper-side work is complete, hold the downgraded draft until 7/18.
- 2026-07-18: if no repaired anchor evidence exists, remove gate-efficacy wording and retain only the audit, EPE/PNE@10 measurement, and exact-fallback construction.
- `RISK-08=submission_stop`: remove the predictive-risk claim and prohibit threshold, corruption, seed, or rescue-tuning changes.
- AAAI-27 deadlines: abstract 2026-07-21, paper 2026-07-28, supplement 2026-07-31 (AoE).

## 6. Synchronized artifacts

- `paper/main_v2.tex`
- `paper/main_v2_zh.md`
- `paper/references.bib`
- `docs/reports/2026-07-09-abstract-freeze-candidate-cn.md` (content superseded by this 2026-07-12 amendment while retaining the referenced path)
- `docs/runbooks/2026-07-11-e1-pass-risk04-08-experiment-manual.md`
- `plan/evidence-map.md`
- `plan/chapter-blueprints/r7-paper-scope-integration-blueprint.md`
- `plan/review/evidence-coverage.md`
- `plan/task-packets/2026-07-12-r7-paper-scope-integration.md`

Machine-readable hashes and validation results are recorded in this directory after verification. Until then, this memo is a scope record rather than a completion claim.
