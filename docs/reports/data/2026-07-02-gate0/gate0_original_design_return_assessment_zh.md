# Gate0 之后：原始设计偏离度与主路径回归判断（中文）

## 1. 先给结论

这份文档要直接回答你最关心的四个问题：

1. 你原始的 idea 是什么？
2. 现在真正跑出来的结果是什么？
3. 结果是否符合原始预期？
4. 如果不符合，现在还能不能回到主路径？

我的结论先放在前面：

- **原始 scientific question 没有换题。**
- **当前结果不符合原始最乐观预期。**
- **偏离最严重的不是方法名称或代码入口，而是核心可证伪预测和 strongest claim。**
- **仍然可以回到主路径，但只能回到“更深层 repair 或更弱 claim”的主路径，不能再把“简单全局校准一修就能开训”当默认答案。**

更直白一点说：

> 这不是“项目彻底跑偏了”，而是“原始主张被更硬的证据压缩了”。现在还能继续做同一个问题，但不能再按最初那版乐观叙事往前写。

## 2. 原始 idea 到底是什么

### 2.1 6 月 24 日原始设计的中心问题

从原始设计文档看，核心不是“给推荐系统加文本”，而是：

- `kernel-level proposal shaping`
- 用 `history-only` 的显式证据可靠性信号去条件化离散偏好扩散核
- 让同一个 proposal 同时控制 preference fading 和 preference growing

对应文档依据：

- 原始设计把方法主轴明确写成 `kernel-level proposal shaping`：
  [2026-06-24-usdpd-text-side-kernel-design.md](E:/PreferGrow/docs/superpowers/specs/2026-06-24-usdpd-text-side-kernel-design.md:13)
- 原始标题级定位是 `Reliability-Shaped Discrete Preference Diffusion for Sequential Recommendation`：
  [2026-06-24-usdpd-text-side-kernel-design.md](E:/PreferGrow/docs/superpowers/specs/2026-06-24-usdpd-text-side-kernel-design.md:25)
- 最核心 claim 是：
  “explicit history-only evidence reliability signal to condition the proposal kernel of discrete preference diffusion”：
  [2026-06-24-usdpd-text-side-kernel-design.md](E:/PreferGrow/docs/superpowers/specs/2026-06-24-usdpd-text-side-kernel-design.md:59)

所以原始 idea 的本体是：

> 用显式、history-only 的证据可靠性信号去塑造 diffusion kernel 的 proposal，而不是把 side information 只放在 encoder 或 loss 里。

### 2.2 原始设计对实验证据的要求

原始设计并不只要求“跑通一个新核”，还要求：

- `global-p` 对照
- `u-shuffle` 对照
- `3-way ablation`
- `text corruption`
- `metadata sparsity`

对应位置：

- `global-p` / `u-shuffle`：
  [2026-06-24-usdpd-text-side-kernel-design.md](E:/PreferGrow/docs/superpowers/specs/2026-06-24-usdpd-text-side-kernel-design.md:698)
  [2026-06-24-usdpd-text-side-kernel-design.md](E:/PreferGrow/docs/superpowers/specs/2026-06-24-usdpd-text-side-kernel-design.md:700)
- `text corruption` / `metadata sparsity`：
  [2026-06-24-usdpd-text-side-kernel-design.md](E:/PreferGrow/docs/superpowers/specs/2026-06-24-usdpd-text-side-kernel-design.md:720)
  [2026-06-24-usdpd-text-side-kernel-design.md](E:/PreferGrow/docs/superpowers/specs/2026-06-24-usdpd-text-side-kernel-design.md:734)
- 原始成功标准里还要求 `kernel` 在 3-way 里稳定优于 `encoder/loss`，并且 `u-shuffle` 必须掉点：
  [2026-06-24-usdpd-text-side-kernel-design.md](E:/PreferGrow/docs/superpowers/specs/2026-06-24-usdpd-text-side-kernel-design.md:768)
  [2026-06-24-usdpd-text-side-kernel-design.md](E:/PreferGrow/docs/superpowers/specs/2026-06-24-usdpd-text-side-kernel-design.md:769)
  [2026-06-24-usdpd-text-side-kernel-design.md](E:/PreferGrow/docs/superpowers/specs/2026-06-24-usdpd-text-side-kernel-design.md:770)

所以原始设计的“理想成功图景”并不是一个很弱的命题，而是：

1. 核注入是主角；
2. 可靠性信号必须是有用的；
3. 文本证据贫与文本证据富的 regime 应该在结果上表现出可解释分化。

## 3. 7 月 2 日冲刺设计把问题收束成了什么

7 月 2 日的 fallback-safe sprint 不是换题，而是把原始问题收束到了一个更可证伪、也更容易硬落地的版本：

- 单一证据门控 `g(u)`
- 锚定宿主可学习全局 `p_core`
- `g=0` 时精确回到宿主核，也就是 `fallback-safe`

对应文档：

- 一句话方法：
  [2026-07-02-aaai27-fallback-safe-kernel-sprint-design.md](E:/PreferGrow/docs/superpowers/specs/2026-07-02-aaai27-fallback-safe-kernel-sprint-design.md:7)
- `g(<=null)=0` 的零点校准约束：
  [2026-07-02-aaai27-fallback-safe-kernel-sprint-design.md](E:/PreferGrow/docs/superpowers/specs/2026-07-02-aaai27-fallback-safe-kernel-sprint-design.md:62)
- `fallback-safe` 命题和 `TV(p_u, p_core) <= g(u)`：
  [2026-07-02-aaai27-fallback-safe-kernel-sprint-design.md](E:/PreferGrow/docs/superpowers/specs/2026-07-02-aaai27-fallback-safe-kernel-sprint-design.md:80)
  [2026-07-02-aaai27-fallback-safe-kernel-sprint-design.md](E:/PreferGrow/docs/superpowers/specs/2026-07-02-aaai27-fallback-safe-kernel-sprint-design.md:81)

这版设计最关键的新增可证伪预测，是：

> 文本证据无信息的数据集应自动贴近宿主核，文本证据可靠的数据集则应保留更强锚点。

在这个冲刺版本里，这个预测被具体压成了 Gate0：

- `|median_u_tilde(ML1M)| < 0.5`
- `median_u_tilde(Steam) > median_u_tilde(ML1M)`
- `median_u_tilde(Beauty) > median_u_tilde(ML1M)`

对应位置：

- [2026-07-02-aaai27-fallback-safe-kernel-sprint-design.md](E:/PreferGrow/docs/superpowers/specs/2026-07-02-aaai27-fallback-safe-kernel-sprint-design.md:98)

所以，Gate0 不是额外加戏，而是 7 月 2 日版本里最关键的“先别重训，先证明你的主假说没在生产 bank 上反着来”的硬门。

## 4. 真实结果是什么

### 4.1 Gate0 的正式结果

Gate0 在 `l20` 上正式跑出的结果是：

- `ML1M = 1.427543`
- `Steam = 0.107291`
- `Beauty = 0.798168`

正式报告：

- [gate0_u_tilde_report.md](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_u_tilde_report.md:1)

对应结论写得非常明确：

- `ML1M` 没有靠近 null；
- `Steam` 和 `Beauty` 都没有高于 `ML1M`；
- `SPRINT-05` 必须继续阻塞。

关键位置：

- Gate0 判据与失败说明：
  [gate0_u_tilde_report.md](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_u_tilde_report.md:6)
  [gate0_u_tilde_report.md](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_u_tilde_report.md:17)
  [gate0_u_tilde_report.md](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_u_tilde_report.md:31)

### 4.2 FOLLOWUP-01 的结果

FOLLOWUP-01 进一步说明：

- `ML1M` 的问题不像是 raw agreement 本体离谱；
- 更像是 `sigma_null` 过紧，把一个不算特别夸张的 residual 放大了；
- 所以主驱动更像 `null_curve_spread_or_scaling_mismatch`。

正式报告：

- [gate0_failure_diagnostic.md](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_failure_diagnostic.md:1)

关键证据：

- [gate0_failure_diagnostic.md](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_failure_diagnostic.md:16)

### 4.3 FOLLOWUP-02 的结果

FOLLOWUP-02 又往前推了一步：既然怀疑是 `spread/scaling`，那就把简单全局修复穷举掉。

结果是：

- 审计候选数：`96`
- 通过数：`0`
- 最好候选：`k4_scale2_floor0`
- 虽然能把 `ML1M` 拉到 `0.356886`
- 但仍然有 `Steam = 0.026823`、`Beauty = 0.199542`
- 所以排序门还是没过

正式报告：

- [gate0_calibration_repair_audit.md](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_calibration_repair_audit.md:1)
- [gate0_calibration_repair_audit_zh.md](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_calibration_repair_audit_zh.md:1)

关键位置：

- 96 个候选、0 个通过：
  [gate0_calibration_repair_audit.md](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_calibration_repair_audit.md:19)
  [gate0_calibration_repair_audit.json](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_calibration_repair_audit.json:2017)
- 最好候选仍未翻转排序：
  [gate0_calibration_repair_audit.md](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_calibration_repair_audit.md:23)
  [gate0_calibration_repair_audit.md](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_calibration_repair_audit.md:47)
- 更强结论：
  [gate0_calibration_repair_audit.json](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_calibration_repair_audit.json:2008)
  [gate0_calibration_repair_audit.json](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_calibration_repair_audit.json:2018)
  [gate0_calibration_repair_audit.json](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_calibration_repair_audit.json:2019)

## 5. 是否符合原始预期

答案很明确：

- **不符合。**

而且不是“差一点点”的不符合，而是原来最关键的可证伪预测没有成立。

### 5.1 不符合的到底是哪一层

最不符合预期的是这层：

> 文本证据贫的 `ML1M` 应该更接近 null，文本证据更可靠的 `Steam / Beauty / ATG` 应该更像正锚点。

当前真实结果却是：

- baseline 下，`ML1M` 反而最高；
- 简单 global repair 之后，`ML1M` 虽然下降了，但 `Steam / Beauty` 仍没有翻到它上面。

所以不符合预期的，不是某个次要数字，而是：

- **regime ordering 本身没有按原设想出现。**

### 5.2 为什么不符合

基于现有证据，最合理的解释是：

1. `ML1M` 的 residual 确实偏正；
2. 但真正把它推高的，是标准化和 spread；
3. 更麻烦的是，这个问题不是简单全局 `k / sigma_scale / sigma_floor` 就能修掉的；
4. 因而“证据贫 regime 自动回退”的检测器，在当前 production-bank 路径上并没有被建立起来。

换句话说：

> 原始 story 不是被“文本完全没用”否掉的，而是被“当前零点校准还不足以稳定地区分 evidence-poor 与 evidence-rich regime”否掉的。

## 6. 我认为偏离了多少

这里我给一个**启发式**判断，不是数学统计量，而是为了帮助后续决策：

| 层面 | 偏离判断 | 启发式偏离度 | 解释 |
| --- | --- | --- | --- |
| scientific question | 低到中度偏离 | `10% - 20%` | 仍然在做 history-only reliability-conditioned proposal kernel，没有换题 |
| kernel 结构与实现主线 | 低偏离 | `10% - 15%` | 7 月 2 日的 fallback-safe v2 核、Gate0、follow-up 审计都沿着设计要求推进 |
| Gate0 可证伪预测 | 高偏离 | `70% - 80%` | `ML1M` 没有贴近 null，反而高于 `Steam/Beauty`；这是当前最大冲突点 |
| strongest claim | 高偏离 | `65% - 80%` | 原本乐观版本不能再原样保留；至少要收紧到更弱口径 |
| 实验执行顺序 | 当前已回正 | `0% - 10%` | 这轮 Gate0 -> FOLLOWUP-01 -> FOLLOWUP-02 的顺序本身是对的，没有再漂去支线 |

这一段的最准一句话是：

> **现在偏离最明显的是 claim boundary，不是 research question。**

## 7. 还能不能回到主路径

### 7.1 如果“主路径”指的是原始 scientific question

- **可以。**

因为这个问题还没有被证明无意义。现在被证明的是：

- 当前这版零点校准在 production-bank 路径上不够；
- 简单 global repair 不够；

但这还不等于：

- reliability-conditioned kernel 这个研究问题本身被否掉。

所以如果你说的“回主路径”是：

> 继续围绕同一个 scientific question，把 evidence-poor regime 的自动回退做实，

那么答案是：

- **可以继续，但必须换到更深层 repair，而不是直接重开训练。**

### 7.2 如果“主路径”指的是 7 月 2 日冲刺版的最乐观叙事

- **目前不可以直接回。**

原因很简单：

1. Gate0 已经正式 fail；
2. FOLLOWUP-01 只把问题定位到 spread/scaling；
3. FOLLOWUP-02 又正式否掉了简单 global repair；
4. 所以“修几个全局旋钮就能回到原始 strongest version”这一条路，当前没有证据支持。

### 7.3 如果“主路径”指的是下一步允许做什么

现在可以把“允许继续推进的动作”与“已经算偏离设计的动作”区分清楚。

#### 仍然算在设计边界内的 deeper repair

下面这些仍然可以算“回主路径”，因为它们还在原始 scientific question 内：

1. 继续保持 `history-only`；
2. 继续保持 `fallback-safe v2 kernel` 主体不变；
3. 继续把修复集中在 `null calibration` 本身，而不是换研究对象；
4. 允许从“简单 global repair”走向“更深层、但仍是 calibration-centered 的 repair”。

具体例子包括：

- 更稳健的 `sigma_null` 估计方式
- 分长度或分桶的更细 spread 修复
- 不同数据集下的非统一但仍显式、可审计的 null estimator
- 不改变 kernel 主体的前提下，重新定义更可靠的 zero-information detector

#### 会被我视为明显偏离设计的动作

下面这些就不该再叫“正常回主路径”了：

1. **在没有新的 Gate0 通过证据前，直接重开 `SPRINT-05` 主表重训**；
2. 为了救结果，改成与原问题不一致的新目标或新注入位置；
3. 把 `history-only` 放弃掉，引入依赖 target、依赖 current corrupted state、或依赖训练时泄漏信号的修复；
4. 用一个全新的可学习黑盒头去掩盖 Gate0 问题，却继续声称这是同一个校准故事。

一句话说：

> “更深层 repair” 仍可能是主路径；“绕过 Gate0 直接开训” 不再是主路径。

## 8. 对你的原始 idea，该怎么重新表述

如果现在还想尽量忠实地保留你的原始 idea，我建议把它从“已经被证实的强结论”改成“仍在接受更强审计的主问题”：

原来更乐观的说法像是：

> 零点校准后，evidence-poor 数据集会自动退回核心核，evidence-rich 数据集保留正锚点。

现在更诚实的说法应该是：

> 我们的主问题仍然是能否用 history-only reliability-conditioned proposal kernel 让 evidence-poor regime 安全回退、让 evidence-rich regime 获益；但当前 production-bank 证据显示，现版本零点校准尚不足以实现这一点，且简单 global repair 已经被否掉。

这会让你的 idea 仍然保持“同一个问题”，但避免把当前证据不支持的部分硬写成已成立事实。

## 9. 当前最稳妥的决策建议

如果目标是**尽量诚实且尽量不偏题**，我建议这样分两条路：

### 路 1：技术上继续救主路径

前提：

- 接受 `SPRINT-05` 继续阻塞；
- 明确下一条不是重训，而是 deeper repair design；
- 修复边界严格受限在 history-only + fallback-safe v2 + calibration-centered。

这条路的收益是：

- 仍在原问题里；
- 一旦有新 Gate0 通过证据，主路径可以重新打开。

代价是：

- 现在还没有现成简单解；
- 时间表风险更高。

### 路 2：论文上先收紧 claim

前提：

- 接受当前 strongest version 不成立；
- 把结论冻结到更弱、更诚实的 claim 边界；
- 把 Gate0 失败与 global repair 失败写成限制或负结果证据。

这条路的收益是：

- 可以避免继续在一个已被部分否掉的简单修复假设上消耗时间；
- 文本会更诚实，也更稳。

代价是：

- 你最初最乐观的 story 需要降级；
- “自动回退已被证实” 这种写法必须放弃。

## 10. 直接回答你的问题

最后用最短的话，直接答你：

### 10.1 你的 original idea 是什么

你的 original idea 是：

> 用显式、history-only 的证据可靠性信号去条件化 diffusion kernel 的 proposal，让文本证据贫的 regime 更接近宿主核，让证据富的 regime 保留更强锚点。

### 10.2 结果是什么

结果是：

- Gate0 在生产 bank 上失败；
- FOLLOWUP-01 说明主问题像是 `null_curve_spread_or_scaling_mismatch`；
- FOLLOWUP-02 说明简单 global `k / sigma_scale / sigma_floor` 修复无效，`96` 个候选 `0` 个通过。

### 10.3 是否符合预期

- **不符合。**

### 10.4 如果不符合，为什么

因为当前 zero-information detector 没有立住：

- `ML1M` 没有回到接近 null；
- `Steam / Beauty` 也没有稳定高于 `ML1M`；
- 并且这不是简单 global calibration repair 就能补回来的。

### 10.5 还能不能回到主路径

- **能回，但不能按原来的乐观路径回。**

现在能回去的，是：

- “在同一 scientific question 内做更深层 repair”的主路径。

现在回不去的，是：

- “简单调几个全局校准参数后立刻重开主表训练”的那条主路径。

## 11. 一句话总结

> 当前偏离主要发生在 strongest claim 和 Gate0 预期，不在 scientific question 本体；因此项目并没有换题，但主路径已经从“简单校准后重开训练”收紧为“更深层 repair 或降级 claim”，而 `SPRINT-05` 在拿到新的 Gate0 通过证据前必须继续阻塞。
