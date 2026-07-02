# Gate0 Calibration Repair Audit

- Gate0 report JSON: `/data/Zijian/goal/RecDemo/docs/reports/data/2026-07-02-gate0/gate0_u_tilde_report.json`
- Gate0 verdict: `fail`
- `SPRINT-05` status: `blocked`
- Candidate count: `96`
- Passing candidate count: `0`

## Gate0 Reasons

- |median_u_tilde(ML1M)|=1.427543 exceeds 0.50
- median_u_tilde(Steam)=0.107291 is not greater than ML1M=1.427543
- median_u_tilde(Beauty)=0.798168 is not greater than ML1M=1.427543

## Decision

- Decision: No audited global k/sigma_scale/sigma_floor repair candidate directionally passes Gate0 on the current production-bank path, so SPRINT-05 must remain blocked.
- Recommended next path: `downgrade_claim_or_design_deeper_repair`
- Inference: Steam max order margin=-0.330063, Beauty max order margin=-0.157344; simple global spread/scaling repairs never flip the ML1M ordering gate.

## Best Candidate

- Candidate id: `k4_scale2_floor0`
- Family: `k+sigma_scale`
- agreement_k: `4.0`
- sigma_scale: `2.0`
- sigma_floor: `0.0`
- ML1M median_u_tilde: `0.356886`
- Steam median_u_tilde: `0.026823`
- Beauty median_u_tilde: `0.199542`
- Gate0 pass: `False`
- Gate0 min margin: `-0.330063`

## Baseline Dataset Summary

| dataset   | dataset_dir                                           |   user_count |   item_count | split_counts                                   | bank_hash                                                        |   baseline_median_residual |   baseline_median_sigma_null |   baseline_median_u_tilde |   baseline_median_g |
|:----------|:------------------------------------------------------|-------------:|-------------:|:-----------------------------------------------|:-----------------------------------------------------------------|---------------------------:|-----------------------------:|--------------------------:|--------------------:|
| ML1M      | /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/ML1M   |       939809 |         3706 | {'train': 755782, 'val': 98622, 'test': 85405} | 31d8c059bbe138d53689cb0101d09f9eb358dfec5f6f567d9f1d59a6750a30ac |                 0.0113299  |                   0.00396832 |                  1.42754  |           0.5       |
| Steam     | /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/Steam  |      1150863 |         9265 | {'train': 988517, 'val': 81695, 'test': 80651} | aee6d302995df9603702145b3da1c1daa555b113926d5c71e17b994079f373d0 |                 0.00160176 |                   0.00746457 |                  0.107291 |           0.0536453 |
| Beauty    | /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/Beauty |        22363 |        12101 | {'train': 17890, 'val': 2236, 'test': 2237}    | 23e28bf7cd0ac7fafd102e2c98d4a874a45bc54501231a51870ac306528af602 |                 0.00690132 |                   0.00504228 |                  0.798168 |           0.399084  |
| ATG       | /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/ATG    |        19412 |        11921 | {'train': 15529, 'val': 1941, 'test': 1942}    | b2f77836e49b1602c86dc87da6585982f0c4872577c21968eadc4e153c5efd17 |                 0.00623018 |                   0.00436016 |                  0.724167 |           0.362083  |

## Top Candidates

| candidate_id            | family                    |   agreement_k |   sigma_scale |   sigma_floor |   ml1m_median_u_tilde |   ml1m_median_g |   steam_median_u_tilde |   steam_median_g |   beauty_median_u_tilde |   beauty_median_g |   atg_median_u_tilde |   atg_median_g |   ml1m_abs_margin |   steam_order_margin |   beauty_order_margin |   gate0_min_margin | gate0_pass   |
|:------------------------|:--------------------------|--------------:|--------------:|--------------:|----------------------:|----------------:|-----------------------:|-----------------:|------------------------:|------------------:|---------------------:|---------------:|------------------:|---------------------:|----------------------:|-------------------:|:-------------|
| k4_scale2_floor0        | k+sigma_scale             |             4 |          2    |        0      |              0.356886 |        0.178443 |              0.0268226 |        0.0134113 |                0.199542 |         0.099771  |             0.181042 |      0.0905208 |         0.143114  |            -0.330063 |             -0.157344 |          -0.330063 | False        |
| k4_scale2_floor0.0045   | k+sigma_scale+sigma_floor |             4 |          2    |        0.0045 |              0.356886 |        0.178443 |              0.0268226 |        0.0134113 |                0.199542 |         0.099771  |             0.181042 |      0.0905208 |         0.143114  |            -0.330063 |             -0.157344 |          -0.330063 | False        |
| k4_scale2_floor0.005    | k+sigma_scale+sigma_floor |             4 |          2    |        0.005  |              0.356886 |        0.178443 |              0.0268226 |        0.0134113 |                0.199542 |         0.099771  |             0.181042 |      0.0905208 |         0.143114  |            -0.330063 |             -0.157344 |          -0.330063 | False        |
| k4_scale2_floor0.0055   | k+sigma_scale+sigma_floor |             4 |          2    |        0.0055 |              0.356886 |        0.178443 |              0.0268226 |        0.0134113 |                0.199542 |         0.099771  |             0.181042 |      0.0905208 |         0.143114  |            -0.330063 |             -0.157344 |          -0.330063 | False        |
| k4_scale2_floor0.006    | k+sigma_scale+sigma_floor |             4 |          2    |        0.006  |              0.356886 |        0.178443 |              0.0268226 |        0.0134113 |                0.199542 |         0.099771  |             0.181042 |      0.0905208 |         0.143114  |            -0.330063 |             -0.157344 |          -0.330063 | False        |
| k4_scale2_floor0.007    | k+sigma_scale+sigma_floor |             4 |          2    |        0.007  |              0.356886 |        0.178443 |              0.0268226 |        0.0134113 |                0.199227 |         0.0996133 |             0.181042 |      0.0905208 |         0.143114  |            -0.330063 |             -0.157659 |          -0.330063 | False        |
| k4_scale1_floor0.007    | k+sigma_floor             |             4 |          1    |        0.007  |              0.404639 |        0.202319 |              0.0536453 |        0.0268226 |                0.246476 |         0.123238  |             0.222506 |      0.111253  |         0.0953611 |            -0.350994 |             -0.158163 |          -0.350994 | False        |
| k4_scale1.25_floor0.007 | k+sigma_scale+sigma_floor |             4 |          1.25 |        0.007  |              0.404639 |        0.202319 |              0.0429162 |        0.0214581 |                0.246476 |         0.123238  |             0.222506 |      0.111253  |         0.0953611 |            -0.361723 |             -0.158163 |          -0.361723 | False        |
| k4_scale1.5_floor0.007  | k+sigma_scale+sigma_floor |             4 |          1.5  |        0.007  |              0.404639 |        0.202319 |              0.0357635 |        0.0178818 |                0.236398 |         0.118199  |             0.219149 |      0.109575  |         0.0953611 |            -0.368875 |             -0.16824  |          -0.368875 | False        |
| k4_scale1_floor0.006    | k+sigma_floor             |             4 |          1    |        0.006  |              0.472079 |        0.236039 |              0.0536453 |        0.0268226 |                0.287555 |         0.143778  |             0.259591 |      0.129795  |         0.0279213 |            -0.418433 |             -0.184524 |          -0.418433 | False        |
| k4_scale1.25_floor0.006 | k+sigma_scale+sigma_floor |             4 |          1.25 |        0.006  |              0.472079 |        0.236039 |              0.0429162 |        0.0214581 |                0.279655 |         0.139828  |             0.257939 |      0.12897   |         0.0279213 |            -0.429162 |             -0.192424 |          -0.429162 | False        |
| k4_scale1.5_floor0.006  | k+sigma_scale+sigma_floor |             4 |          1.5  |        0.006  |              0.472079 |        0.236039 |              0.0357635 |        0.0178818 |                0.254873 |         0.127436  |             0.236389 |      0.118194  |         0.0279213 |            -0.436315 |             -0.217206 |          -0.436315 | False        |
