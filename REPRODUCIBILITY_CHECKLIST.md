# Reproducibility Checklist

| Contract | Required disclosure | Current evidence | Release state |
|---|---|---|---|
| Data | paper_raw_v1 train/val/test frames; no native SASRec resplit | E5 source and split hashes | ready |
| Seed | all new runs use seed 100 | r7/E5 manifests | ready |
| Selection | validation NDCG@10 row-weighted v1 | summaries and manifests | ready |
| Test use | test logged during development | `single_train.py` and memo | must remain explicit |
| Evaluator | e0_full_tail_v2 and exact row counts | E0 amendment | ready |
| Text assets | bank, embedding, null-curve provenance | RISK-04/r7 manifests | ready for completed arms |
| Gate | U_ds/EPE/phi_R are distinct | dated method amendment | manuscript integration pending |
| Exact fallback | scope-limited R12 trace | 2,986 comparisons, zero failures | ready within scope |
| r7 performance | 14/14 + RISK-08 + terminal + nonempty logs | current snapshot nonterminal | blocked |
| External baseline | adapted common-contract SASRec, four domains | E5 manifest/source hashes | ready, single run |
| Uncertainty | user-level bootstrap | zero runs; no user IDs | not estimable |
| Code revision | source revision and bundle provenance | manifests and inventory | final hash backfill pending |

Submission must include the exact sentence: “Model selection used validation only; test metrics were
logged during development.” It must not describe test as an untouched final holdout.
