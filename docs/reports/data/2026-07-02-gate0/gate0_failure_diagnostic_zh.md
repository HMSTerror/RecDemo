# Gate0 失败追因补充诊断（中文）

## 1. 这份补充诊断要回答什么

正式 Gate0 已经确认失败，见：

- [gate0_u_tilde_report.md](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_u_tilde_report.md:1)
- [gate0_u_tilde_report.json](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_u_tilde_report.json:1)

但 Gate0 的失败只告诉我们“当前主路径不能继续开训”，还没有回答：

1. `ML1M` 为何会明显高于 null 点？
2. 主要矛盾是 raw agreement 本身太高，还是 null curve 的 spread / scaling 有问题？
3. 下一步更合理的是继续修 calibration，还是直接转入 frozen-claim downgrade？

这份补充诊断就是为回答这三个问题而做的。

对应的正式英文机器产物是：

- [gate0_failure_diagnostic.md](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_failure_diagnostic.md:1)
- [gate0_failure_diagnostic.json](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_failure_diagnostic.json:1)
- [gate0_failure_component_summary.csv](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_failure_component_summary.csv:1)

## 2. 诊断方法

仍然使用和 Gate0 完全相同的生产环境：

- 服务器：`l20`
- 远端仓库：`/data/Zijian/goal/RecDemo`
- 数据目录：`/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/{ML1M,Steam,Beauty,ATG}`
- 文本银行：正式 `sentence-t5-xl`

不同之处在于，这次不只读 `u_tilde` 和 `g`，而是把下列分量都拆出来做 per-dataset 汇总：

- `agreement`
- `mu_null`
- `sigma_null`
- `agreement - mu_null`
- `(agreement - mu_null) / sigma_null`
- `history_length`
- `completeness`
- `history_reliability`
- `history_ess`
- `history_recency`
- `history_stability`
- `u_tilde`
- `g`

也就是说，这次追因不再停留在最终 `u_tilde`，而是顺着

```text
agreement -> (agreement - mu_null) -> / sigma_null -> u_tilde -> g
```

这条链往前拆。

## 3. 最关键的新结果

### 3.1 ML1M 的 raw residual 并不夸张

`ML1M` 的关键量是：

- `median(agreement) = 0.942712`
- `median(mu_null) = 0.931382`
- `median(agreement - mu_null) = 0.011330`

这说明 `ML1M` 并不是因为 raw agreement 比 null baseline 高出非常夸张的一截。  
它确实高于 null，但高得不算离谱，只是一个 **小的正 residual**。

### 3.2 真正被放大的是 sigma / scaling

`ML1M` 的：

- `median(sigma_null) = 0.003968`
- `median((agreement - mu_null) / sigma_null) = 2.855086`

对比：

- `Steam`
  - `median(sigma_null) = 0.007465`
  - `median((agreement - mu_null) / sigma_null) = 0.214581`
- `Beauty`
  - `median(sigma_null) = 0.005042`
  - `median((agreement - mu_null) / sigma_null) = 1.596337`

也就是说，`ML1M` 的问题不是“残差特别大”，而是：

> **一个并不算大的正 residual，被一个很紧的 sigma_null 放大了。**

因为最终

```text
u_tilde = (agreement - mu_null) / (k * sigma_null)
```

而当前 `k = 2.0` 固定时，`sigma_null` 过小会把这个 residual 直接放大成很高的 `u_tilde`。

## 4. 这说明 Gate0 为什么失败

结合正式 Gate0 和这次 follow-up 诊断，可以把失败原因更精确地说成：

1. `ML1M` 的 raw agreement 相对 null baseline 仍然是正的；
2. 但更关键的是，`ML1M` 的 `sigma_null` 太紧；
3. 小的正 residual 在 tight sigma 下被放大；
4. 放大后 `median_u_tilde(ML1M)=1.427543`，远高于 Gate0 阈值 `0.5`；
5. 同时 `Steam` 和 `Beauty` 相对 `ML1M` 的排序也被压在了下面。

所以这次 follow-up 给出的主驱动不是：

- 单纯的 `raw agreement floor too high`

而是：

- **`null_curve_spread_or_scaling_mismatch`**

这也是英文正式诊断里给出的主 driver。

## 5. 对主路径意味着什么

这次补充诊断把下一步路径判断得更清楚了。

### 5.1 现在仍然不能开 `SPRINT-05`

这一点没有变化：

- Gate0 仍然是 `fail`
- `SPRINT-05` 仍然必须 `blocked`

所以不能把这次 follow-up 理解成“虽然 Gate0 fail 了，但可以先开主表再说”。

### 5.2 更合理的下一步是 calibration repair first

这次 follow-up 的一个重要收获是：

> 当前更像是一个 calibration / scaling 问题，而不是整个文本可靠性故事彻底崩掉。

因此，最合理的下一步不是直接 claim downgrade，而是：

- **先做 calibration repair**

更具体地说，下一步应该优先检查：

1. `agreement_null_curves` 的 spread 是否过紧；
2. 当前 `k=2.0` 在 production bank 上是否明显偏小；
3. null curve 的估计方式是否需要更稳健的 spread 估计或 floor；
4. `ML1M` 的 length-matched null 是否在分桶或估计方式上过于乐观。

### 5.3 但 frozen-claim downgrade 仍然保留为 fallback

虽然推荐路径已经从之前较模糊的 “broader repair or downgrade” 收敛到了

- `calibration_repair_first`

但这并不意味着降级写作路径被取消。  
如果后续 calibration repair 仍然不能把 Gate0 拉回主路径，或者时间表撑不住，那么：

- `frozen_claim_downgrade_if_schedule_expires`

仍然是明确保留的 fallback。

## 6. 这次 follow-up 相比正式 Gate0 多带来了什么

正式 Gate0 告诉我们的是：

- 主路径不能继续开训

这次 follow-up 多回答了一个更细的问题：

- **不能继续开训，主要不是因为 raw agreement 已经完全失真，而是因为当前 null spread / scaling 把 ML1M 的小正 residual 放大成了很高的 `u_tilde`。**

这让“回主路径”的可能性比之前更具体了一点：

- 不是抽象地说“也许需要修 calibration”
- 而是比较明确地说“优先修 null curve spread / scaling”

## 7. 当前结论

一句话总结：

> Gate0 fail 的主驱动更像是 `sigma_null` 过紧带来的 scaling 放大，而不是单纯 raw agreement 太高；因此当前最合理的下一步是先做 calibration repair，再决定是否能重新打开 `SPRINT-05`。

当前实际状态可以归纳为：

- Gate0：`已完成，但 fail`
- 主路径：`未回正`
- 主表重训：`继续阻塞`
- 推荐下一步：`calibration_repair_first`
- 备用退路：`frozen_claim_downgrade_if_schedule_expires`
