# Gate 0 u_tilde Diagnostics

Verdict: `fail`

Criterion:
- `abs(median_u_tilde(ML1M)) < 0.5`
- `median_u_tilde(Steam) > median_u_tilde(ML1M)`
- `median_u_tilde(Beauty) > median_u_tilde(ML1M)`

## Decision

- `SPRINT-05` main-table retrains: `blocked`
- Gate 0 failed on the production sentence-t5-xl banks; keep SPRINT-05 main-table retrains blocked.

## Hypothesis

- Original: Length-matched null calibration on production sentence-t5-xl banks should drive ML1M close to the null point while Steam and Beauty remain above ML1M, so text-evidence-poor regimes auto-fallback toward the core kernel.
- Revised: Length-matched null calibration alone does not drive ML1M near the null point on the production sentence-t5-xl banks. Instead ML1M remains strongly positive (median_u_tilde=1.427543) and sits above Steam (0.107291) and Beauty (0.798168). The calibrated-agreement signal is therefore not yet a reliable zero-information detector for ML1M, so the main path must stay on calibration/claim revision before any v2 main-table retrains.

## Dataset Summary

| dataset   | dataset_dir                                           |   user_count |   item_count | split_counts                                   | bank_hash                                                        |   mean_u_tilde |   median_u_tilde |   std_u_tilde |   p10_u_tilde |   p90_u_tilde |   mean_g |
|:----------|:------------------------------------------------------|-------------:|-------------:|:-----------------------------------------------|:-----------------------------------------------------------------|---------------:|-----------------:|--------------:|--------------:|--------------:|---------:|
| ML1M      | /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/ML1M   |       939809 |         3706 | {'train': 755782, 'val': 98622, 'test': 85405} | 31d8c059bbe138d53689cb0101d09f9eb358dfec5f6f567d9f1d59a6750a30ac |       1.42094  |         1.42754  |      0.841697 |      0.308527 |      2.52025  | 0.418354 |
| Steam     | /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/Steam  |      1150863 |         9265 | {'train': 988517, 'val': 81695, 'test': 80651} | aee6d302995df9603702145b3da1c1daa555b113926d5c71e17b994079f373d0 |       0.149508 |         0.107291 |      0.468781 |     -0.411316 |      0.781984 | 0.126015 |
| Beauty    | /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/Beauty |        22363 |        12101 | {'train': 17890, 'val': 2236, 'test': 2237}    | 23e28bf7cd0ac7fafd102e2c98d4a874a45bc54501231a51870ac306528af602 |       1.02307  |         0.798168 |      1.11432  |     -0.161801 |      2.53948  | 0.315874 |
| ATG       | /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/ATG    |        19412 |        11921 | {'train': 15529, 'val': 1941, 'test': 1942}    | b2f77836e49b1602c86dc87da6585982f0c4872577c21968eadc4e153c5efd17 |       0.922054 |         0.724168 |      1.06062  |     -0.198173 |      2.31797  | 0.303834 |

## Reasons

- |median_u_tilde(ML1M)|=1.427543 exceeds 0.50
- median_u_tilde(Steam)=0.107291 is not greater than ML1M=1.427543
- median_u_tilde(Beauty)=0.798168 is not greater than ML1M=1.427543
