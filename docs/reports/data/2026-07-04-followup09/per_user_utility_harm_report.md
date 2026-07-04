# Per-user Utility vs Harm Report

This artifact pairs train-only sampled per-user text utility with frozen first-generation (`v1`) vs host-core
per-user `p2` ranking deltas on the same sampled train-user transitions.

## Protocol

- Generated at: `2026-07-04T15:34:20+08:00`
- Rows sampled per user: `4`
- Utility negatives per sampled row: `100`
- Seed: `7`
- Device: `cuda:0`
- Primary correlation claim: `per-user mean delta_ndcg10 under p2 personalization on sampled train-user transitions`

## Dataset Summary

| dataset | dataset_dir | user_count | sampled_row_count | rows_per_user | negative_count | bank_hash | split_hash | v1_log_path | v1_checkpoint_path | core_checkpoint_path | core_graph_type | v1_best_step | v1_test_p2_ndcg10 | core_best_step | core_test_p2_ndcg10 | pearson_utility_vs_delta_ndcg10 | spearman_utility_vs_delta_ndcg10 | inverse_ordering_observed | interpretation | utility_buckets | correlations | per_user_csv | bucket_csv | correlation_csv |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ML1M | /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/ML1M | 4832 | 19328 | 4 | 100 | 76fcfc25668145bfbaba194f2f0f652acda0c424363f689f35bb653eb525497d | 30783cebd83dbc601358fe08a2ae997bdaf9c1ee964a5a3f3bb8ddf365ad2adc | /data/Zijian/goal/RecDemoRuns/main_table_text_side/ml1m_proposal_adaptive_mainpath/logs/ml1m_proposal_adaptive_mainpath.log | /data/Zijian/goal/RecDemoRuns/main_table_text_side/ml1m_proposal_adaptive_mainpath/checkpoints-meta/ML1M/checkpoint_proposal_adaptive_best.pth | /data/Zijian/goal/RecDemo/checkpoints-meta/ML1M/checkpoint_hybrid_best.pth | hybrid | 111000 | 0.028844810656414362 | 302000 | 0.09102175325784369 | 0.057886118409508754 | 0.0276791920236945 | False | The within-dataset user-level association is weak or non-negative in this readout. | [{'utility_bucket': 'Q1', 'user_count': 1208, 'utility_mean': 0.53059187427931, 'utility_min': 0.1524999998509884, 'utility_max': 0.649999987334013, 'delta_ndcg10_mean': -0.09247265978167389, 'delta_hit10_mean': -0.16597682119205298, 'delta_rank_mean': -247.64755794701986, 'v1_ndcg10_mean': 0.02577236917684015, 'core_ndcg10_mean': 0.11824502895851403}, {'utility_bucket': 'Q2', 'user_count': 1208, 'utility_mean': 0.7151086330893742, 'utility_min': 0.649999987334013, 'utility_max': 0.773749977350235, 'delta_ndcg10_mean': -0.08452413877509288, 'delta_hit10_mean': -0.15480132450331127, 'delta_rank_mean': -104.99254966887418, 'v1_ndcg10_mean': 0.0359176043852769, 'core_ndcg10_mean': 0.12044174316036978}, {'utility_bucket': 'Q3', 'user_count': 1208, 'utility_mean': 0.8219981170968701, 'utility_min': 0.7737499848008156, 'utility_max': 0.8699999898672104, 'delta_ndcg10_mean': -0.08262730919022039, 'delta_hit10_mean': -0.1390728476821192, 'delta_rank_mean': 0.7775248344370861, 'v1_ndcg10_mean': 0.04771818973074686, 'core_ndcg10_mean': 0.13034549892096725}, {'utility_bucket': 'Q4', 'user_count': 1208, 'utility_mean': 0.9196709208067088, 'utility_min': 0.8699999898672104, 'utility_max': 0.9974999874830246, 'delta_ndcg10_mean': -0.07302147887696493, 'delta_hit10_mean': -0.1285182119205298, 'delta_rank_mean': 96.45633278145695, 'v1_ndcg10_mean': 0.06009805316586565, 'core_ndcg10_mean': 0.13311953204283059}] | [{'metric': 'utility_vs_delta_ndcg10', 'user_count': 4832, 'pearson': 0.057886118409508754, 'spearman': 0.0276791920236945}, {'metric': 'utility_vs_delta_hit10', 'user_count': 4832, 'pearson': 0.06708597196059574, 'spearman': 0.05292238440754258}, {'metric': 'utility_vs_delta_rank', 'user_count': 4832, 'pearson': 0.4371821141763035, 'spearman': 0.4442816257273997}] | /data/Zijian/goal/RecDemo/docs/reports/data/2026-07-04-followup09/ML1M_per_user_points.csv | /data/Zijian/goal/RecDemo/docs/reports/data/2026-07-04-followup09/ML1M_utility_bucket_summary.csv | /data/Zijian/goal/RecDemo/docs/reports/data/2026-07-04-followup09/ML1M_correlations.csv |
| Steam | /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/Steam | 31836 | 127292 | 4 | 100 | 78fed57c4afba29031624357ad7b8e543aa20a0b06b3373e69525625e6e78023 | 7bd272c71882ee53fe356677157392d0cae7a5b8cf6820437a604f30ed9610fa | /data/Zijian/goal/RecDemoRuns/main_table_text_side/steam_proposal_adaptive_mainpath/logs/steam_proposal_adaptive_mainpath.log | /data/Zijian/goal/RecDemoRuns/main_table_text_side/steam_proposal_adaptive_mainpath/checkpoints-meta/Steam/checkpoint_proposal_adaptive_best.pth | /data/Zijian/goal/RecDemo/checkpoints-meta/Steam/checkpoint_adaptive_best.pth | adaptive | 3000 | 0.019284021813307416 | 27000 | 0.012895807155712712 | 0.04554768526293251 | 0.045552119345236064 | False | The within-dataset user-level association is weak or non-negative in this readout. | [{'utility_bucket': 'Q1', 'user_count': 7959, 'utility_mean': 0.3694545912406415, 'utility_min': 0.026249999413266778, 'utility_max': 0.4637499861419201, 'delta_ndcg10_mean': -0.009216007270078371, 'delta_hit10_mean': -0.019809858859990787, 'delta_rank_mean': -233.85325836579133, 'v1_ndcg10_mean': 0.020669313272714124, 'core_ndcg10_mean': 0.0298853205427925}, {'utility_bucket': 'Q2', 'user_count': 7959, 'utility_mean': 0.5242438722644781, 'utility_min': 0.4637499861419201, 'utility_max': 0.5799999907612801, 'delta_ndcg10_mean': -0.007005387624389398, 'delta_hit10_mean': -0.016113833396155297, 'delta_rank_mean': -247.3954851949575, 'v1_ndcg10_mean': 0.019427207672673863, 'core_ndcg10_mean': 0.026432595297063263}, {'utility_bucket': 'Q3', 'user_count': 7959, 'utility_mean': 0.6357063650608259, 'utility_min': 0.5799999907612801, 'utility_max': 0.694999985396862, 'delta_ndcg10_mean': -0.004140309330735788, 'delta_hit10_mean': -0.009873518448716338, 'delta_rank_mean': -209.49753947313314, 'v1_ndcg10_mean': 0.017976495400230285, 'core_ndcg10_mean': 0.022116804730966073}, {'utility_bucket': 'Q4', 'user_count': 7959, 'utility_mean': 0.786800772719723, 'utility_min': 0.694999985396862, 'utility_max': 1.0, 'delta_ndcg10_mean': -0.0033427351361698617, 'delta_hit10_mean': -0.007318758638019852, 'delta_rank_mean': -50.11969677932739, 'v1_ndcg10_mean': 0.01451986040047087, 'core_ndcg10_mean': 0.01786259553664073}] | [{'metric': 'utility_vs_delta_ndcg10', 'user_count': 31836, 'pearson': 0.04554768526293251, 'spearman': 0.045552119345236064}, {'metric': 'utility_vs_delta_hit10', 'user_count': 31836, 'pearson': 0.044457145437736496, 'spearman': 0.046909699121924865}, {'metric': 'utility_vs_delta_rank', 'user_count': 31836, 'pearson': 0.11945734428093863, 'spearman': 0.09136376104982588}] | /data/Zijian/goal/RecDemo/docs/reports/data/2026-07-04-followup09/Steam_per_user_points.csv | /data/Zijian/goal/RecDemo/docs/reports/data/2026-07-04-followup09/Steam_utility_bucket_summary.csv | /data/Zijian/goal/RecDemo/docs/reports/data/2026-07-04-followup09/Steam_correlations.csv |

## ML1M

- User count: `4832`
- Sampled rows: `19328`
- Spearman(`utility`, `delta_ndcg10`): `0.0276791920236945`
- Pearson(`utility`, `delta_ndcg10`): `0.057886118409508754`
- Inverse ordering observed: `False`
- Interpretation: The within-dataset user-level association is weak or non-negative in this readout.

### Utility buckets

| utility_bucket | user_count | utility_mean | utility_min | utility_max | delta_ndcg10_mean | delta_hit10_mean | delta_rank_mean | v1_ndcg10_mean | core_ndcg10_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Q1 | 1208 | 0.53059187427931 | 0.1524999998509884 | 0.649999987334013 | -0.09247265978167389 | -0.16597682119205298 | -247.64755794701986 | 0.02577236917684015 | 0.11824502895851403 |
| Q2 | 1208 | 0.7151086330893742 | 0.649999987334013 | 0.773749977350235 | -0.08452413877509288 | -0.15480132450331127 | -104.99254966887418 | 0.0359176043852769 | 0.12044174316036978 |
| Q3 | 1208 | 0.8219981170968701 | 0.7737499848008156 | 0.8699999898672104 | -0.08262730919022039 | -0.1390728476821192 | 0.7775248344370861 | 0.04771818973074686 | 0.13034549892096725 |
| Q4 | 1208 | 0.9196709208067088 | 0.8699999898672104 | 0.9974999874830246 | -0.07302147887696493 | -0.1285182119205298 | 96.45633278145695 | 0.06009805316586565 | 0.13311953204283059 |

### Correlations

| metric | user_count | pearson | spearman |
| --- | --- | --- | --- |
| utility_vs_delta_ndcg10 | 4832 | 0.057886118409508754 | 0.0276791920236945 |
| utility_vs_delta_hit10 | 4832 | 0.06708597196059574 | 0.05292238440754258 |
| utility_vs_delta_rank | 4832 | 0.4371821141763035 | 0.4442816257273997 |

## Steam

- User count: `31836`
- Sampled rows: `127292`
- Spearman(`utility`, `delta_ndcg10`): `0.045552119345236064`
- Pearson(`utility`, `delta_ndcg10`): `0.04554768526293251`
- Inverse ordering observed: `False`
- Interpretation: The within-dataset user-level association is weak or non-negative in this readout.

### Utility buckets

| utility_bucket | user_count | utility_mean | utility_min | utility_max | delta_ndcg10_mean | delta_hit10_mean | delta_rank_mean | v1_ndcg10_mean | core_ndcg10_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Q1 | 7959 | 0.3694545912406415 | 0.026249999413266778 | 0.4637499861419201 | -0.009216007270078371 | -0.019809858859990787 | -233.85325836579133 | 0.020669313272714124 | 0.0298853205427925 |
| Q2 | 7959 | 0.5242438722644781 | 0.4637499861419201 | 0.5799999907612801 | -0.007005387624389398 | -0.016113833396155297 | -247.3954851949575 | 0.019427207672673863 | 0.026432595297063263 |
| Q3 | 7959 | 0.6357063650608259 | 0.5799999907612801 | 0.694999985396862 | -0.004140309330735788 | -0.009873518448716338 | -209.49753947313314 | 0.017976495400230285 | 0.022116804730966073 |
| Q4 | 7959 | 0.786800772719723 | 0.694999985396862 | 1.0 | -0.0033427351361698617 | -0.007318758638019852 | -50.11969677932739 | 0.01451986040047087 | 0.01786259553664073 |

### Correlations

| metric | user_count | pearson | spearman |
| --- | --- | --- | --- |
| utility_vs_delta_ndcg10 | 31836 | 0.04554768526293251 | 0.045552119345236064 |
| utility_vs_delta_hit10 | 31836 | 0.044457145437736496 | 0.046909699121924865 |
| utility_vs_delta_rank | 31836 | 0.11945734428093863 | 0.09136376104982588 |
