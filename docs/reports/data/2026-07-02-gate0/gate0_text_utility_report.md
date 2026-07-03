# Gate0 Text Utility Diagnostic

This artifact freezes the production-bank `U_ds` inputs required by spec section 7.4.
It does **not** make the Gate 0-v2 pass/fail decision; that interpretation belongs to `FOLLOWUP-07`.

## Protocol

- Generated at: `2026-07-03T13:58:17+08:00`
- Sample size per dataset: `4000`
- Negatives per sampled transition: `100`
- Seed: `7`
- Primary statistic: `U_ds_popularity = P(sim(h,next) > sim(h,neg_pop)) with 100 train-next-popularity negatives`
- Diagnostic statistic: `U_ds_uniform = P(sim(h,next) > sim(h,neg_uniform)) with 100 uniform negatives`

## Dataset Summary

| dataset   | dataset_dir                                           |   train_row_count |   sampled_row_count |   usable_row_count |   skipped_row_count |   negative_count |   history_length_mean |   history_length_median |   coherence_mean |   coherence_median |   u_ds_popularity |   u_ds_uniform |   phi_u_ds | bank_hash                                                        | split_hash                                                       |
|:----------|:------------------------------------------------------|------------------:|--------------------:|-------------------:|--------------------:|-----------------:|----------------------:|------------------------:|-----------------:|-------------------:|------------------:|---------------:|-----------:|:-----------------------------------------------------------------|:-----------------------------------------------------------------|
| ML1M      | /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/ML1M   |            755782 |                4000 |               4000 |                   0 |              100 |              10       |                      10 |         0.885252 |           0.884892 |          0.753539 |       0.798526 |   0        | 76fcfc25668145bfbaba194f2f0f652acda0c424363f689f35bb653eb525497d | 7895e743467fd60060127264894250a0502d94028e84441400aa14dfd9118576 |
| Steam     | /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/Steam  |            988517 |                4000 |               4000 |                   0 |              100 |              10       |                      10 |         0.887562 |           0.886434 |          0.569566 |       0.565079 |   1        | 78fed57c4afba29031624357ad7b8e543aa20a0b06b3373e69525625e6e78023 | a0e0a7e03cb0823386da7f0832f595253633014dd50f64fc63c2d431d0f84006 |
| Beauty    | /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/Beauty |             17890 |                4000 |               4000 |                   0 |              100 |               6.38125 |                       6 |         0.898876 |           0.895393 |          0.712427 |       0.717204 |   0        | 591e4f4ee24160becd190f2b5279a48a351004ff6fd09f228473188a182b5d9b | ab2863e37b13290aa216ae4c83c725a852e2a7fdd9325afb1d501e0141e3f2b6 |
| ATG       | /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/ATG    |             15529 |                4000 |               4000 |                   0 |              100 |               6.24925 |                       5 |         0.904227 |           0.901095 |          0.688262 |       0.692013 |   0.117375 | 90ac91f8d54a19cf5f0c70a304b0a6ddf63d5803e45f0a85e293377642b9812f | 33315c196f7a377a223f2a20705d3557e827c39c547baf16b69645f2e43db0ec |

## Frozen Gate0-v2 Inputs

- `U_ds` descending rank: `ML1M, Beauty, ATG, Steam`
- `ML1M` rank by `U_ds`: `1`
- `ML1M` `U_ds`: `0.75353875`
- `ML1M` `phi(U_ds)`: `0.0`
- Non-`ML1M` datasets with `phi(U_ds) >= 0.5`: `1`
- Note: FOLLOWUP-07 owns the frozen Gate 0-v2 pass/fail decision.

## Coherence Quartiles: `ML1M`

| dataset   | coherence_bucket   |   row_count |   coherence_mean |   coherence_min |   coherence_max |   u_ds_popularity |   u_ds_uniform |
|:----------|:-------------------|------------:|-----------------:|----------------:|----------------:|------------------:|---------------:|
| ML1M      | Q1                 |        1000 |         0.868445 |        0.841115 |        0.875545 |          0.617805 |       0.683855 |
| ML1M      | Q2                 |        1000 |         0.880345 |        0.875546 |        0.884891 |          0.715175 |       0.764325 |
| ML1M      | Q3                 |        1000 |         0.889805 |        0.884893 |        0.894956 |          0.81169  |       0.84499  |
| ML1M      | Q4                 |        1000 |         0.902411 |        0.894974 |        0.940589 |          0.869485 |       0.900935 |

## Coherence Quartiles: `Steam`

| dataset   | coherence_bucket   |   row_count |   coherence_mean |   coherence_min |   coherence_max |   u_ds_popularity |   u_ds_uniform |
|:----------|:-------------------|------------:|-----------------:|----------------:|----------------:|------------------:|---------------:|
| Steam     | Q1                 |        1000 |         0.871279 |        0.840953 |        0.878406 |          0.53882  |       0.554995 |
| Steam     | Q2                 |        1000 |         0.882519 |        0.878409 |        0.886433 |          0.541205 |       0.55151  |
| Steam     | Q3                 |        1000 |         0.890813 |        0.886434 |        0.895849 |          0.567145 |       0.56386  |
| Steam     | Q4                 |        1000 |         0.905639 |        0.895856 |        0.94078  |          0.631095 |       0.58995  |

## Coherence Quartiles: `Beauty`

| dataset   | coherence_bucket   |   row_count |   coherence_mean |   coherence_min |   coherence_max |   u_ds_popularity |   u_ds_uniform |
|:----------|:-------------------|------------:|-----------------:|----------------:|----------------:|------------------:|---------------:|
| Beauty    | Q1                 |        1000 |         0.877136 |        0.858436 |        0.884439 |          0.645045 |       0.6523   |
| Beauty    | Q2                 |        1000 |         0.889835 |        0.884458 |        0.895381 |          0.67786  |       0.67795  |
| Beauty    | Q3                 |        1000 |         0.902147 |        0.895405 |        0.909968 |          0.728625 |       0.735595 |
| Beauty    | Q4                 |        1000 |         0.926384 |        0.909976 |        0.981128 |          0.79818  |       0.80297  |

## Coherence Quartiles: `ATG`

| dataset   | coherence_bucket   |   row_count |   coherence_mean |   coherence_min |   coherence_max |   u_ds_popularity |   u_ds_uniform |
|:----------|:-------------------|------------:|-----------------:|----------------:|----------------:|------------------:|---------------:|
| ATG       | Q1                 |        1000 |         0.882898 |        0.861442 |        0.890348 |          0.6274   |       0.63425  |
| ATG       | Q2                 |        1000 |         0.895733 |        0.890352 |        0.901084 |          0.65929  |       0.663965 |
| ATG       | Q3                 |        1000 |         0.907122 |        0.901106 |        0.914421 |          0.686615 |       0.69149  |
| ATG       | Q4                 |        1000 |         0.931153 |        0.914442 |        0.989156 |          0.779745 |       0.778345 |
