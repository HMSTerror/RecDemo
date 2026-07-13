# Table 1 新旧 evaluator 仲裁

## 判定

旧 Gate-1 数字下，按 U_ds 从低到高排列数据集会得到 Steam、ATG、Beauty、ML1M；按文本核
效果从高到低排列得到 Steam、Beauty、ATG、ML1M。由实际冻结数字可见，旧尺也不是严格的
四项全序一致：Beauty 与 ATG 已经相邻互换。历史文档所称“4/4”更接近四个数据集的方向/端点
判读，而不是严格 rank equality。E0 尾批修复后，效果顺序仍为 Steam、Beauty、ATG、ML1M，
首尾端点和相邻互换结构均保持。因而本文不得继续把该证据写成“修正前严格 4/4、修正后才
破裂”；更准确的仲裁是：旧文案把方向性命中压缩成了严格全序，而逐项重算显示严格全序从未
成立。

## 数值

| 数据集 | U_ds | legacy Δ NDCG@10 | corrected Δ NDCG@10 | U_ds 低→高名次 | corrected 效果高→低名次 |
|---|---:|---:|---:|---:|---:|
| Steam | 0.569566 | +0.002015 | +0.002142 | 1 | 1 |
| ATG | 0.688263 | -0.011410 | -0.011505 | 2 | 3 |
| Beauty | 0.712428 | -0.003859 | -0.003705 | 3 | 2 |
| ML1M | 0.753539 | -0.015133 | -0.014851 | 4 | 4 |

U_ds 来自 `gate0_text_utility_summary.csv` 的 popularity-negative point estimate；legacy 和
corrected delta 均由 `e0_old_new_metrics.csv` 中同一数据集的 ours 减 host 得到。E0 对所有
方法使用同一 tail-complete test contract，四域评估行数分别为 Steam 80,651、ML1M 85,405、
Beauty 2,237、ATG 1,942。该修正没有翻转原 Gate-1 pass/miss verdict，但它也不能把四个
aggregate 点转化为总体统计规律。

## 对论文叙述的约束

建议把中心句改为：

> Across the four archived datasets, lower train-only text utility coincided with a more favorable
> single-run text-kernel response at the two endpoints, while Beauty and ATG formed an adjacent
> rank inversion. The tail-complete evaluator amendment preserved this descriptive pattern and did
> not flip any preregistered pass/miss verdict. We do not interpret four aggregate points as a
> population-level law.

中文对应为：

> 在四个归档数据集上，较低的 train-only 文本效用与首尾端点上更有利的单次文本核响应相伴，
> Beauty 与 ATG 则构成相邻名次互换。尾批完整的 evaluator 修正保留了这一描述性结构，且未
> 翻转任何预注册 pass/miss 判定。本文不把四个 aggregate 点解释为总体层面的规律。

`1/24` 只能保留为 exchangeability 假设下“一个预先指定全序占 (4!\) 个等可能全序之一”的
组合比例。由于严格全序并未被逐项数字满足，该数值更不能作为当前表的经验 p 值。E7 实际
bootstrap replicates 为 0，排序保持概率和置信区间均为 not estimable。

冻结 Table 2 本周期不做选择性数值替换。若正文使用 corrected 数字，必须按 E0 的整体移动
规则同时替换相关 host/ours/control 口径并保留 legacy 对照；否则主表标 legacy evaluator，
corrected 仲裁放在附录或 dated amendment。
