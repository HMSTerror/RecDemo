# E0 dated evaluator amendment (2026-07-10)

## Scope and evidence boundary

This amendment is a **single-run result/observation** under the common full-tail, row-weighted, real-item test contract. Its exact scope is **legacy-selected frozen checkpoint + corrected test evaluation**. Validation selection was not recomputed.

The legacy host ATG checkpoint used model item count 11,924 while the real catalog contains 11,921 items. Its history sentinel 11,921 was an ordinary non-candidate model slot during frozen training. E0 preserves that frozen input meaning and only restricts paper-facing ranking to real IDs 0--11,920; fully protocol-aligned training comparability is not claimed for that host checkpoint.

No frozen checkpoint, Gate-1, SPRINT-07, DiffuRec, or Table 2 artifact was overwritten.

## Old/new metrics

| Artifact | Dataset | Old HR@10 | New HR@10 | Old NDCG@10 | New NDCG@10 | Rows |
|---|---:|---:|---:|---:|---:|---:|
| host_steam | Steam | 0.029750 | 0.029572 | 0.012896 | 0.012841 | 80651 |
| host_ml1m | ML1M | 0.165341 | 0.165225 | 0.091022 | 0.090936 | 85405 |
| host_beauty | Beauty | 0.052246 | 0.050067 | 0.033295 | 0.031603 | 2237 |
| host_atg | ATG | 0.048549 | 0.046859 | 0.041878 | 0.040360 | 1942 |
| ours_full_steam | Steam | 0.034859 | 0.035127 | 0.014911 | 0.014983 | 80651 |
| ours_full_ml1m | ML1M | 0.168884 | 0.169299 | 0.075889 | 0.076086 | 85405 |
| ours_full_beauty | Beauty | 0.052734 | 0.050067 | 0.029436 | 0.027898 | 2237 |
| ours_full_atg | ATG | 0.046875 | 0.044799 | 0.030467 | 0.028855 | 1942 |
| global_p_steam | Steam | 0.030618 | 0.031047 | 0.013244 | 0.013408 | 80651 |
| u_shuffle_steam | Steam | 0.031969 | 0.033019 | 0.013834 | 0.014216 | 80651 |
| text_anchor_only_steam | Steam | 0.068750 | 0.068604 | 0.030181 | 0.030004 | 80651 |
| global_p_beauty | Beauty | 0.052734 | 0.050067 | 0.029436 | 0.027898 | 2237 |
| u_shuffle_beauty | Beauty | 0.052734 | 0.050961 | 0.033004 | 0.031606 | 2237 |
| text_anchor_only_beauty | Beauty | 0.052246 | 0.050961 | 0.028989 | 0.028199 | 2237 |
| diffurec_steam | Steam | 0.132471 | 0.131480 | 0.073822 | 0.073313 | 80651 |
| diffurec_ml1m | ML1M | 0.257926 | 0.258088 | 0.141162 | 0.141249 | 85405 |
| diffurec_beauty | Beauty | 0.057165 | 0.058561 | 0.043489 | 0.044220 | 2237 |
| diffurec_atg | ATG | 0.046790 | 0.048404 | 0.036934 | 0.037861 | 1942 |

## Frozen prediction reread

| Dataset | Frozen criterion | Old delta/outcome | Corrected delta/outcome | Flipped |
|---|---|---|---|---|
| Steam | delta > 0; reference magnitude delta >= +0.003 | 0.002015 / directional_hit_reference_miss | 0.002142 / directional_hit_reference_miss | false |
| ML1M | abs(delta) < 0.01 | -0.015133 / miss | -0.014851 / miss | false |
| Beauty | abs(delta) < 0.01 | -0.003859 / hit | -0.003705 / hit | false |
| ATG | abs(delta) < 0.01 | -0.011410 / miss | -0.011505 / miss | false |

- Original Gate 0: `fail` -> `fail`; flipped=`false`; its u-tilde inputs are unchanged.
- Gate 0-v2: `fail` -> `fail`; flipped=`false`; its U_ds/phi inputs are unchanged.
- Gate 1 ML1M: `fail_no_diagnostic` -> `fail_no_diagnostic`; corrected delta=-0.014850532981; flipped=`false`.

DiffuRec test-evaluator comparability is confirmed under the dated corrected contract. Checkpoint-selection equivalence is not claimed. Table 2 remains frozen in this cycle; later paper backfill must use an all-system common-ruler replacement.
