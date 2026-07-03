# Gate 0-v2 Family D 降级决策备忘

## 结论

冻结的 Gate 0-v2 三条件判据未通过，因此 `SPRINT-05` 不重开，主线进入 Family D claim downgrade 路径。
根据修订规范，这意味着不再进行第三轮门控修复。

## 三条冻结条件

1. Condition 1: ML1M has the maximum U_ds：通过
   - margin = 0.041111
   - ranking=['ML1M', 'Beauty', 'ATG', 'Steam']; ML1M U_ds=0.753539; next-best non-ML1M U_ds=0.712427
2. Condition 2: phi(U_ML1M) <= 0.2：通过
   - margin = 0.200000
   - phi(U_ML1M)=0.000000; threshold=0.200000
3. Condition 3: at least two of Steam/Beauty/ATG have phi(U_ds) >= 0.5：失败
   - margin = -1.000000
   - qualifying_datasets=['Steam']; count=1; required_count=2

## 为什么失败

第三条要求 Steam/Beauty/ATG 中至少两个数据集满足 phi(U_ds) >= 0.5，但本次只有 Steam 满足，实际数量为 1。
这说明 utility-gated 路线已经成功把 ML1M 的门基本关掉，但没有同时把足够多的 v1 获益数据集推入明显开门区，因此不足以支撑重开四数据集 v2 主表训练。

## 对 SPRINT-05 的影响

- `SPRINT-05` decision: `blocked_family_d_downgrade`
- 不再进行第三轮门控修复
- 后续应按 Family D 路线冻结更弱但诚实的论文主张
