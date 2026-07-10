# CLOSE-02 ML1M 宿主噪声地板

## 当前状态

- 已完成种子数: 3/3
- 远端执行根要求: `/data/Zijian/goal/RecDemo_clean_closeout_chain`
- 最大成对 |delta test p2 NDCG@10|: 0.003171207143786
- Gate-1 ML1M 官方 delta_test_p2_ndcg10: -0.015133045070724
- 决策线: `outside_noise_red_flag` (gate1_ml1m_delta_exceeds_measured_host_noise_floor)

## Per-seed

| seed | status | best_step | val_p5_ndcg10 | test_p2_ndcg10 | test_p5_ndcg10 | test_p10_ndcg10 |
| --- | --- | --- | --- | --- | --- | --- |
| 100 | completed | 536000 | 0.124685330366904 | 0.105785303613534 | 0.113518733534569 | 0.116092629562717 |
| 101 | completed | 464000 | 0.120935813132208 | 0.102614096469748 | 0.111240689979095 | 0.113402353936557 |
| 102 | completed | 514000 | 0.124194315792578 | 0.104959298928549 | 0.11345029595008 | 0.115472523870577 |

## Pairwise

| seed_a | seed_b | abs_delta_test_p2_ndcg10 | abs_delta_test_p5_ndcg10 | abs_delta_test_p10_ndcg10 |
| --- | --- | --- | --- | --- |
| 100 | 101 | 0.003171207143786 | 0.002278043555474 | 0.00269027562616 |
| 100 | 102 | 0.000826004684985 | 0.000068437584489 | 0.00062010569214 |
| 101 | 102 | 0.002345202458801 | 0.002209605970985 | 0.00207016993402 |
