# AAAI-27 seed=100 adapter readiness audit

Date: 2026-07-11 01:40 (Asia/Shanghai)  
Worktree: `E:/PreferGrow/.worktrees/aaai27-seed100-controller`  
Revision: `bbb06d1`  
Scope: RISK-01--RISK-14 adapter audit only. No training, corruption-bank generation, remote mutation, or tmux launch was performed.

## Executive result

The resident controller is ready to validate a manifest, but the scientific execution layer is not ready to populate one. No RISK-01--RISK-14 item is runnable as a new queue task at this checkpoint. Two items have useful historical evidence (E0 artifact package and E1 terminal hard-stop); eleven require a new contract-compliant adapter; RISK-12 is intentionally disabled.

The most important hard stop is factual: the only external diffusion implementation in the worktree is `DiffuRec`, while the approved comparison requires `DiffRec`. The two names cannot be substituted. Likewise, historical text-side shell runners are not safe adapters because their print-only commands contain `tmux kill-session`, mutable skip/force behavior, and no atomic resident-queue success markers.

## Evidence and commands

- Primary risk ledger SHA-256: `902a6d2a6de2982b06aa4c08a8cab431974e557ef4e679b0adfb4a6668ef7b0f`.
- Existing E0 package: `docs/reports/data/2026-07-10-evaluator-amendment/e0_evaluator_amendment.json`; it records 18/18 matrix entries, `e0_full_tail_v2`, row-weighted aggregation, all mapped real catalog items, and `eval_seed=100`, but explicitly does not recompute validation checkpoint selection.
- Existing E1 package: `docs/reports/data/2026-07-10-e01-gzero-production-trace/e01_hard_stop.json`; it is a hard stop at step 0 (`core_proposal_logits.in_optimizer`), so no E1 pass marker exists.
- Existing adapter help probes exited zero for the scripts that exist. `scripts/build_corrupted_text_bank.py`, `scripts/run_sasrec.py`, `scripts/run_caser.py`, `scripts/run_grurec.py`, `scripts/run_diffrec.py`, and the RISK-08 decision producer were absent.
- E0, external-baseline-table, and Gate0 unit tests: 18 tests OK. The historical Beauty utility test passed separately with `KMP_DUPLICATE_LIB_OK=TRUE`; the combined default Windows run hit the known duplicate OpenMP-runtime failure and is not represented as a production pass.

## RISK matrix

| RISK | Readiness | Evidence | Blocking reason |
|---|---|---|---|
| RISK-01 | artifact-only, not queue-runnable | E0 18-artifact package and evaluator tests | No generic common evaluator/selector task adapter and success marker |
| RISK-02 | terminal fail | existing hard-stop JSON | Optimizer ownership mismatch at step 0; amendment trace not run |
| RISK-03 | missing contract adapter | U_ds/u_tilde/per-user historical scripts | No exact train-only EPE/PNE@10 report with user-clustered uncertainty contract |
| RISK-04 | missing adapter | referenced builder absent | No popularity-stratified Beauty/Steam six-level banks or 12 preflights |
| RISK-05 | missing adapter | older ASO reports only | No immutable preregistration consuming RISK-04 hashes and frozen thresholds |
| RISK-06 | legacy noncompliant | text-side tmux scripts | Kill/force/skip semantics and no exact seven/four-arm queue contract |
| RISK-07 | missing/legacy noncompliant | no Steam pilot adapter | Same as RISK-06 plus no approved Steam bank path |
| RISK-08 | missing adapter | controller only reads marker | No producer for one atomic `RISK-08_EXIT.json` from raw pilot artifacts |
| RISK-09 | missing adapter | no SASRec/Caser/GRURec files | No implementation or shared-protocol launcher |
| RISK-10 | blocked by RISK-09 | no training task | Cannot enforce 3 x 4 all-four completion |
| RISK-11 | identity blocked | only `run_close04_diffurec.py` | DiffuRec is not DiffRec; no official DiffRec identity/memory audit |
| RISK-12 | disabled | validator rejects it | Approved constraint excludes BERT4Rec/RISK-12 |
| RISK-13 | missing and gate-blocked | no matched-pair task builder | No exact seed100 eight-run group/provenance; E1 currently fails |
| RISK-14 | missing adapter | historical report builders only | No train-only condition replay and complete six-arm control launcher |

## Required next implementation order

1. ADAPT-02: implement and test the front-gate adapters in ledger order: common evaluator/selector binding, amended E1 trace, exact train-only EPE/PNE, corruption-bank builder/preflight, and immutable RISK-05 preregistration.
2. Only after ADAPT-02 produces real markers should ADAPT-03 implement the exact E1-pass/E1-fail pilots and the RISK-08 decision producer.
3. ADAPT-04 may add RISK-13/RISK-14 and classic/DiffRec groups only when their identities and all-four contracts are real. The current E1 hard stop means the automatic branch remains audit-only until an amended trace reaches a terminal outcome.

## Hard stops

- Do not build or launch the real queue from this readiness report.
- Do not report historical E0 or DiffuRec artifacts as newly runnable training evidence.
- Do not substitute DiffuRec for DiffRec.
- Do not launch any pilot, baseline, continuation, or mechanism-control training until its adapter, marker, hashes, and manifest mapping pass the controller validator.
