# E0 evaluator 修正案（2026-07-10）

## 范围与证据边界

本修正案仅报告共同全尾批、逐行加权、真实物品候选契约下的**单次运行观察**。精确范围是：**历史选择的冻结 checkpoint + 修正后的 test 评估**；validation 选择没有重算。

ATG 的旧 host checkpoint 按 11,924 个模型 item 槽训练，而真实目录是 11,921。历史 sentinel 11,921 在该冻结 host 中是普通非候选模型槽。E0 原样保留该输入语义，只把论文排名候选限定为真实 ID 0--11,920；不声称该 host checkpoint 的训练协议已与 ours 完全对齐。

未覆盖任何冻结 checkpoint、Gate-1、SPRINT-07、DiffuRec 或 Table 2 工件。

## 新旧指标

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

## 冻结预测重新宣读

| Dataset | Frozen criterion | Old delta/outcome | Corrected delta/outcome | Flipped |
|---|---|---|---|---|
| Steam | delta > 0; reference magnitude delta >= +0.003 | 0.002015 / directional_hit_reference_miss | 0.002142 / directional_hit_reference_miss | false |
| ML1M | abs(delta) < 0.01 | -0.015133 / miss | -0.014851 / miss | false |
| Beauty | abs(delta) < 0.01 | -0.003859 / hit | -0.003705 / hit | false |
| ATG | abs(delta) < 0.01 | -0.011410 / miss | -0.011505 / miss | false |

- 原始 Gate 0：`fail` -> `fail`，翻转=`false`；u-tilde 输入不受 E0 影响。
- Gate 0-v2：`fail` -> `fail`，翻转=`false`；U_ds/phi 输入不受 E0 影响。
- Gate 1 ML1M：`fail_no_diagnostic` -> `fail_no_diagnostic`，修正后 delta=-0.014850532981，翻转=`false`。

DiffuRec 已在本次修正后的 test evaluator 契约下完成可比性核验；不声称 checkpoint 选择过程等价。本周期 Table 2 继续冻结，后续论文回填只能执行全体系共同换尺。
