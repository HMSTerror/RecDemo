# AAAI Manuscript Local Integration Design

## Objective

Move the submission package to a state where the only unresolved empirical input is the terminal r7 result. All edits remain local, preserve negative evidence, and never convert the current partial r7 queue into a paper result.

## Frozen decisions

- The paper uses a three-layer account: train-only `U_ds` discovery, EPE/PNE exposure-risk measurement, and preregistered condition-level `phi_R` intervention.
- The strict four-domain `4/4` rank claim is withdrawn. Steam/ML1M endpoints are retained; Beauty/ATG swap adjacent ranks under both evaluators.
- c100 is an explicit `phi_R=0` production sanity check, not evidence that user-level `u_tilde` collapsed.
- E5 is reported as an adapted common-contract SASRec baseline over all four domains. Beauty validation and test are always presented together.
- DiffuRec is excluded from the confirmatory comparison without deleting historical artifacts.
- r7 performance remains blocked until 14/14 tasks, nonempty logs, valid manifests, consistent RISK-08/TERMINAL markers, and a `risk_gated_method` exit.
- The manuscript retains the disclosure that model selection used validation only and test metrics were logged during development.

## Components

1. Revise the English and Chinese manuscripts using the dated Gate-2 amendment and claim map.
2. Add evaluator arbitration and the four-domain SASRec baseline without partial or selective reporting.
3. Maintain three external conditional result modules for `risk_gated_method`, `audit_only`, and `submission_stop`; none is inserted before the real exit exists.
4. Replace method-figure placeholders with deterministic vector schematics and prepare a numeric `phi_R` source figure. The r7 performance figure remains blocked.
5. Prepare an AAAI compilation wrapper around the existing manuscript without modifying an official style file. If no current official author-kit file is present locally, record that blocker rather than inventing one.
6. Prepare a supplement/reproducibility appendix using only frozen artifacts.
7. Add a read-only PowerShell synchronizer that creates a new dated local snapshot, never writes remotely, and invokes the existing fail-closed evidence builder only on a complete snapshot.

## Safety and acceptance

- No GPU or remote queue mutation.
- No partial r7 metrics in manuscript or figures.
- No new E7 records or bootstrap claim.
- No `significant`, `stable`, `within noise`, or untouched-holdout claim for single-run evidence.
- English/Chinese scientific claims remain synchronized.
- New scripts follow RED/GREEN TDD and reject nonterminal or hash-mismatched evidence.
- Final review includes spec compliance, scientific-quality review, LaTeX/static checks, JSON/CSV checks, tests, and a capability-use audit.
