# Gate0 更深层修复设计备忘（中文）

## 1. 这份 memo 的目标

到 `FOLLOWUP-03` 为止，我们已经把边界钉死了：

- 原始 scientific question 还在；
- `SPRINT-05` 不能开；
- 简单 global `k / sigma_scale / sigma_floor` 修复已经被正式否掉；
- 如果还要救主路径，下一步必须是 **deeper repair**，而且这个 repair 不能把问题换掉。

这份 memo 的任务就是：

1. 把“还能做的更深层 repair”列清楚；
2. 判断哪些 repair 仍然算在原始设计边界内；
3. 给出优先级排序；
4. 选出最值得先实现的一条。

## 2. 先重申不能越过的边界

根据原始设计、7 月 2 日 sprint 设计，以及 `FOLLOWUP-03` 的冻结判断，下面这些是不能动的硬边界：

1. 仍然是 `history-only`；
2. 仍然是 `fallback-safe v2 kernel` 主体；
3. 仍然把问题定义为“证据可靠性条件化 proposal kernel”，不是改成别的 research question；
4. 在新的 Gate0 通过之前，不允许直接重开 `SPRINT-05`；
5. 不引入依赖 target、依赖 current corrupted state、或依赖训练时泄漏信息的修复；
6. 不允许用新黑盒 learnable head 把 Gate0 问题包起来后继续宣称“只是校准修复”。

换句话说，repair 允许更深，但不能更飘。

## 3. 为什么简单 global repair 已经不够

`FOLLOWUP-02` 给了一个很关键的信息：

- 最好候选 `k4_scale2_floor0` 已经能把 `ML1M` 拉到 `0.356886`；
- 但 `Steam = 0.026823`、`Beauty = 0.199542` 仍然都低于 `ML1M`；
- 说明问题不是“整体都缩小两倍就行”，而是：

> 当前的 spread / null 结构，至少在一部分局部区间上，对 `ML1M` 与 `Steam/Beauty` 的影响不是同构的。

因此，下一步如果还要坚持 calibration 方向，repair 至少得从“统一全局缩放”走向“局部、结构化、但仍显式”的修复。

## 4. 候选 repair 家族

### 4.1 Family A：按长度桶做更稳健的局部 spread 重估

#### 核心想法

不要再只用一个全局 `sigma_scale` 去乘所有长度桶，而是直接回到 `sigma_null(L)` 本身：

- 重估每个长度桶的 spread；
- 用更稳健的估计器替代当前可能过紧的 spread；
- 允许不同长度桶有不同 floor。

#### 可能做法

1. 用更稳健的 spread 估计器替代当前版本，例如：
   - IQR-based spread
   - MAD-based spread
   - 高分位差值近似 spread
2. 不再只用一个全局 `sigma_floor`，而是按长度桶给 floor；
3. 对极低样本桶做平滑或相邻桶收缩，避免过拟合。

#### 为什么它仍在设计边界内

- 仍是 `history-only`
- 仍是 `mu_null(L), sigma_null(L)` 路线
- 没有改 kernel 结构
- 没有引入新的 learnable 模块

#### 它最像在修什么

它修的是：

> “某些长度桶上的 `sigma_null(L)` 被估得过紧，导致 `ML1M` 的局部 residual 被过度放大”。

#### 风险

- 如果真正的问题不是局部 spread，而是 null 生成机制本身错了，这条路只能缓解，不能治根；
- 需要确保局部修复不是“为了救 ML1M 而定制桶规则”。

#### 评价

- 与原设计贴合度：`最高`
- 实现侵入性：`低到中`
- 成功概率：`中高`

### 4.2 Family B：把 zero-information detector 从 z-score 改成更稳健的 rank / percentile 校准

#### 核心想法

当前 `u_tilde = residual / (k * sigma_null)` 默认依赖“残差近似高斯、spread 足够稳定”这类假设。  
如果这个前提不稳，可以把“是否接近 null”的判定改成：

- length-bin 内的经验分位数
- 或 rank-normalized score

例如：

- 用 `percentile(residual | L)` 代替原始 z-score；
- 令 `g=0` 对应某个明确的 null percentile 区间。

#### 为什么它仍在设计边界内

- 仍是显式、history-only 的校准；
- 仍是对 zero-information detector 的重定义；
- 没有把可靠性信号换成新的黑盒预测器。

#### 它最像在修什么

它修的是：

> “当前 z-score 形式对尾部、偏态或长度桶分布差异过于敏感”。

#### 风险

- 解释性比 z-score 略弱一点；
- 需要非常明确地把“哪个 percentile 算 null”写成显式规则，否则容易滑向经验魔法参数。

#### 评价

- 与原设计贴合度：`高`
- 实现侵入性：`中`
- 成功概率：`中`

### 4.3 Family C：改 null 生成器，而不是只改 null 统计量

#### 核心想法

如果当前伪历史的构造方式本身就不够像“该数据集里的零信息状态”，那只修统计量可能不够。  
这时要往前追一层，重做 null generator。

可能方向包括：

1. 伪历史不只按长度匹配，还按文本完整性或 coverage 近似匹配；
2. 对极稀疏文本 item 的采样比例做约束；
3. 区分“随机 item 组合”和“更接近真实历史语义噪声”的伪历史生成。

#### 为什么它仍可能算在设计边界内

只要它仍然是：

- offline
- history-only
- 不看 target
- 不看真实 label

那么它仍属于“null calibration builder 的修复”，而不是换题。

#### 它最像在修什么

它修的是：

> “当前 null baseline 根本没有正确代表这个数据集中的零信息参考状态”。

#### 风险

- 侵入性明显大于 A/B；
- 更容易被质疑为“你是不是在重定义 null 来救结果”；
- 需要最严的审计和文档说明。

#### 评价

- 与原设计贴合度：`中高`
- 实现侵入性：`中高`
- 成功概率：`中`

### 4.4 Family D：停止技术修复，直接冻结更弱 claim

#### 核心想法

如果 A/B/C 都看起来代价太高、时间太紧，或者风险太像重新发明方法，那就不再继续救 technical path，而是：

- 保持当前结果；
- 冻结更弱、更诚实的 claim；
- 把 Gate0 fail 和 global repair fail 作为真实限制写进 paper。

#### 为什么它是合法选项

它不是技术修复，但它是 **边界一致** 的诚实收口方式。

#### 风险

- 最乐观的主张必须放弃；
- 论文的攻击性下降。

#### 评价

- 与原设计贴合度：`作为收口是高，作为继续冲 strongest version 是低`
- 实现侵入性：`最低`
- 成功概率：`写作层高，技术回正为零`

## 5. 方案比较表

| Repair family | 仍在设计内？ | 贴合原始问题 | 预期对 Gate0 的帮助 | 实现面 | 风险 | 排名 |
| --- | --- | --- | --- | --- | --- | --- |
| A. 局部 robust spread 重估 | 是 | 很高 | 最高 | 低到中 | 中 | `1` |
| B. rank / percentile null 校准 | 是 | 高 | 中 | 中 | 中 | `2` |
| C. null generator 重建 | 是，但要很谨慎 | 中高 | 中 | 中高 | 高 | `3` |
| D. 直接降 claim | 是，但不再救技术主线 | 中 | 不修 Gate0 | 低 | 对 strongest claim 很高 | `4` |

## 6. 我推荐的下一条实现目标

### 推荐：先做 Family A

也就是：

> **优先重做按长度桶的局部 spread / floor 估计，而不是再调全局 `k / sigma_scale / sigma_floor`。**

推荐它的原因有四个：

1. 与当前证据最对口  
   `FOLLOWUP-02` 已经说明“整体缩放”无效，说明该看局部结构。

2. 与原始设计最一致  
   它仍然完全停留在 `mu_null(L), sigma_null(L)` 的 builder 层，不改 kernel 本体。

3. 最容易保持 claim 纯度  
   这不是新方法，而是对“零点校准有没有把 null spread 估对”做更严格修正。

4. 失败也最有信息量  
   如果 A 做完新的 Gate0 仍不通过，那么我们就更有底气说：  
   “简单 global repair 不够，局部 robust spread 也不够”，此时再转 B/C 或直接降 claim 会更干净。

## 7. A 方案的最小实现边界

如果真的要把 A 落成下一条代码实现，我建议最小边界是：

1. 在 `build_agreement_null_curves.py` 中新增稳健 spread 估计模式；
2. 仍按历史长度桶输出 `mu_null(L), sigma_null(L)`；
3. 增加按桶 floor 或平滑规则；
4. 重新生成 production-bank null artifacts；
5. 重新跑 Gate0；
6. Gate0 若仍不过，才考虑 B/C。

注意，这里仍然**不允许**：

- 直接开 `SPRINT-05`
- 偷偷改 `g(u)` 主体逻辑
- 把修复混成“又一个新的可靠性模型”

## 8. 对后续 issue 排序的建议

如果继续按主路径推进，我建议顺序变成：

1. 实现 Family A 的局部 robust spread repair
2. 重新生成 null artifacts
3. 重跑 Gate0
4. 只有 Gate0 通过，才允许重开 `SPRINT-05`
5. 如果 A 后仍失败，再决定是转 B/C 还是直接降 claim

## 9. 最终判断

一句话总结：

> 在不换题的前提下，当前最值得先试的更深层修复，不是再调一次全局 `k / sigma`，而是回到 `sigma_null(L)` 的局部结构上，做更稳健的 length-bin spread / floor 重估；这仍在原始 history-only fallback-safe 边界内，也是当前最主路径兼容的下一条实现目标。
