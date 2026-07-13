# AAAI-27 figure data manifest

| Figure | Measurement | Required input | Script/output | Current state |
|---|---|---|---|---|
| F1 method architecture | injection location and exact fallback boundary | code/spec references only | architecture source to be prepared; no synthetic metric | planned |
| F2 train-only risk response | EPE/PNE@10, `phi_R`, mean gate across c0--c100 | immutable RISK-03/04 risk report | `docs/reports/data/2026-07-13-aaai-local-fixed-disk/risk_response_source.csv`; performance overlay remains blocked | `phi_R` source ready; EPE/PNE overlay pending exact rows |
| F3 validation/test response | host-relative validation and test deltas for r7 | 14/14 r7 artifacts and terminal RISK-08 | `scripts/build_r7_paper_evidence.py` -> `r7_paper_metrics.csv` | blocked by r7 terminal |

Captions must state what is measured. F3 must show Beauty validation and test together. c100 must be
labeled as explicit `phi_R=0` fallback sanity check.

No r6a point may be silently substituted for r7 in F3. If the deadline arrives before the release
gate opens, F3 is removed or replaced by a non-performance audit diagram.
