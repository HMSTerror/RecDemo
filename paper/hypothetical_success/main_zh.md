# 当更强证据反而有害：离散扩散推荐的 Fallback-Safe 腐蚀核

> **全实验成功情景稿，不是真实证据稿。** 本文假设所有预注册实验最终达到成功标准，但所有结果单元格均故意留空。任何数字必须由 dated artifact、SHA-256、共同 evaluator 和 selector 合同回填；`--` 表示“未回填”，不是零。

## 摘要

离散扩散推荐器先把观察到的偏好向 proposal 分布腐蚀，再学习逆转该过程。现有方法通常在去噪器或 guidance 侧进行个性化，而让所有用户共享腐蚀 proposal。本文研究向 proposal 注入冻结文本证据时出现的可靠性问题：能够准确预测未来正例的强证据，可能把更多腐蚀质量分配给正例，使腐蚀机制受到假负例污染。我们把证据链拆成三个不可互换的层次：train-only 的跨域发现统计量 `U_ds`、已观察下一正例暴露代理 EPE，以及在训练前预注册的条件级风险干预 `phi_R`。方法用 history-only 用户因子与 `phi_R` 控制宿主 proposal 和冻结文本锚点之间的凸组合；门为零时精确回到宿主核，门非零时只给出 proposal 与单步转移行的 TV 界。本文是假设所有四域主实验、腐蚀响应、归因、baseline、不确定性与效率实验均成功的完整论文故事，数值表格保持空白直至真实工件授权。

## 1. 引言

偏好扩散不是在普通序列模型外套一个随机噪声层。forward proposal 决定偏好消失后由什么物品替代，并进入平稳分布、细致平衡参考测度、score-entropy 权重与解析反演比率。PreferGrow 一类方法已经在 score 侧利用用户条件，但 forward proposal 仍是全局对象。

文本侧信息看似可以直接解决这一局限。用户历史的语义中心能够构造一组内容上合理的替代物品。然而 proposal 的角色不是预测，而是腐蚀。若文本相似度把真实下一物品排在前面，强文本证据会把腐蚀质量集中到未来正例。这使“证据越强越应该使用”的直觉在 corruption kernel 中可能反转。

本文不把一次跨域相关性直接写成生产门。`U_ds` 只负责在训练集上发现文本相似度区分下一物品和流行度匹配负例的能力；EPE 衡量文本 proposal 相对宿主 proposal 给已观察下一正例增加了多少对数暴露；`phi_R` 则根据预注册 corruption 条件在训练前冻结。三层分工使发现、机制测量和干预不会在看到结果后被混成一个量。

方法只修改 proposal，不修改 encoder、loss 或 reverse guidance。history-only 用户因子在长度匹配随机历史零点上校准，和 `phi_R` 一起控制宿主可学习 proposal 与冻结文本锚点之间的插值。`g=0` 时 proposal 及其派生的 forward、score-entropy、sampling 和 analytic-reverse 核对象回到宿主；非零门只保证 proposal 与单步 transition row 的 TV 半径，不对独立训练后的 NDCG 作确定性承诺。

本文预留的完整实验体系回答四个问题：暴露风险是否预测文本腐蚀何时有效；证据被完全破坏时是否回收宿主；history-only 对齐与 anchor 是否都是必要部件；在统一 split、catalog、selector 与 evaluator 下，方法是否能与原论文对齐的序列和扩散 baseline 公平比较。

## 2. 相关工作

### 2.1 序列推荐 baseline

SASRec、Caser、GRURec 与 BERT4Rec 分别代表自注意力、卷积、循环和双向掩码序列建模。本文不直接抄录其他论文中协议不同的数字，而是让本地实现读取相同冻结行、完整真实 catalog、validation selector 与修正 evaluator。

### 2.2 扩散推荐 baseline

DiffRec 是与原 PreferGrow 比较路线一致的确认性扩散 baseline。DreamRec、PreferDiff 与 DDSR 只有在官方代码可用并通过 mapping、split、catalog 和 evaluator 审计后，才进入单独的本地扩展表。DiffuRec 不进入确认性比较，因为它是早期探索锚点而不是目标 DiffRec 模型族。

### 2.3 自适应腐蚀与可靠性

已有自适应 masking 或 confidence-ordered decoding 主要依赖模型内部置信度；可靠性推荐通常修改表示、loss 或预测权重。本文直接修改 forward proposal，并保留显式宿主端点，因此能够表达“门关闭时就是宿主核”的保证。

### 2.4 假负例

负采样研究避免把可能正例作为负例。在偏好褪色核中，transition law 本身就是结构化负采样器。EPE 测量 proposal 给已观察下一正例增加的暴露，但不冒充对所有未观察潜在正例的完整计数。

## 3. 方法

设真实物品集合为 `Ω`，宿主伪物品为 `⋆`。宿主学习 proposal `p_core`，其秩一 forward kernel 为：

```math
P_{σ,p}=α_σ I+(1-α_σ)1p^T.
```

冻结物品文本 embedding 对历史 `h` 定义锚点：

```math
c_h(i) ∝ exp(<ē_h,e_i>/τ).
```

用户因子 `ũ` 通过同长度随机历史的均值和方差进行零点校准，再裁剪到 `[0,1]`。发现统计量只使用训练 transition：

```math
U_ds = Pr[s(h,y)>s(h,n)],
```

其中 `y` 是观察到的下一物品，`n` 是训练集内流行度匹配负例。EPE 为：

```math
EPE(h,y)=log(q_text(y|h)+1e-12)-log(q_core(y)+1e-12).
```

对预注册 corruption 条件 `R`，门为：

```math
g(h,R)=g_max·phi_R·clip(ũ,0,1).
```

门只混合真实物品坐标，伪物品质量保持宿主值：

```math
p_u(⋆)=p_core(⋆),
p_u^Ω=(1-g)·p̃_core^Ω+g·c_h.
```

**命题 1：精确回退。** 当 `g=0` 时，`p_u=p_core`，指定生产路径中所有 proposal-derived forward、score-entropy、sampling 与 analytic-reverse 核对象与宿主一致。

**命题 2：核级偏差。** 对固定历史与 condition：

```math
TV(p_u,p_core)≤g,
TV(P_{σ,p_u}(i,·),P_{σ,p_core}(i,·))≤(1-α_σ)g.
```

该界不约束独立训练后的 score model 或端到端推荐指标。

## 4. 实验协议

数据集为 Steam、ML1M、Amazon Beauty 与 Amazon Toys and Games。全部本地方法共享冻结 train/validation/test frame、物品 mapping、完整真实 catalog、row-weighted HR@10/NDCG@10 evaluator 和 validation NDCG@10 selector。新增运行先使用 seed=100；若完成重复种子，则完整报告，不删除不利运行。模型选择只使用 validation，但开发过程中记录过 test，因此不得把 test 称为 untouched final holdout。

确认性核心 baseline 包括：

1. SASRec；
2. Caser；
3. GRURec；
4. DiffRec；
5. matched PreferGrow host；
6. 本文方法。

BERT4Rec 是扩展序列 baseline。DreamRec、PreferDiff、DDSR 只有在官方代码共同合同审计通过后进入扩展本地比较。任一 baseline 一旦启动，必须交齐四域或显式标为 incomplete，不能只报告有利子集。

## 5. 假设全部成功时的结果结构

> 本节描述“若真实工件满足成功标准，应如何解释”，不是已经发生的实验结论。

### 5.1 主对比

在全成功情景中，完整主表应支持：本文方法在预注册主判据上优于 matched PreferGrow host，并在不同架构的序列与扩散 baseline 中保持竞争力。空单元格不表示零。

| 方法 | Steam HR@10 | Steam NDCG@10 | ML1M HR@10 | ML1M NDCG@10 | Beauty HR@10 | Beauty NDCG@10 | ATG HR@10 | ATG NDCG@10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SASRec | -- | -- | -- | -- | -- | -- | -- | -- |
| Caser | -- | -- | -- | -- | -- | -- | -- | -- |
| GRURec | -- | -- | -- | -- | -- | -- | -- | -- |
| BERT4Rec | -- | -- | -- | -- | -- | -- | -- | -- |
| DiffRec | -- | -- | -- | -- | -- | -- | -- | -- |
| PreferGrow host | -- | -- | -- | -- | -- | -- | -- | -- |
| 本文方法 | -- | -- | -- | -- | -- | -- | -- | -- |

可选的官方代码扩展块必须单列：

| 可选 baseline | Steam | ML1M | Beauty | ATG | 本地共同合同审计 |
|---|---:|---:|---:|---:|---|
| DreamRec | -- | -- | -- | -- | -- |
| PreferDiff | -- | -- | -- | -- | -- |
| DDSR | -- | -- | -- | -- | -- |

### 5.2 腐蚀响应

成功情景要求：随着证据 corruption 增强，EPE/PNE 风险按预注册方向变化，`phi_R` 相应下降；clean 条件保留有用行为；c100 通过显式 `phi_R=0` 回收宿主。c100 只能解释成实现 sanity check，不能写成模型自动学会关闭。

| 数据集 | Arm | Corruption | Val HR@10 | Val NDCG@10 | Test HR@10 | Test NDCG@10 | EPE | PNE@10 | Mean gate |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Beauty | Host | 0 | -- | -- | -- | -- | -- | -- | -- |
| Beauty | Anchor only | 0/60/100 | -- | -- | -- | -- | -- | -- | -- |
| Beauty | Full | 0/60/100 | -- | -- | -- | -- | -- | -- | -- |
| Steam | Host | 0 | -- | -- | -- | -- | -- | -- | -- |
| Steam | Anchor only | 0/60/100 | -- | -- | -- | -- | -- | -- | -- |
| Steam | Full | 0/60/100 | -- | -- | -- | -- | -- | -- | -- |

Beauty 的任何正向 test 数字都必须同时展示 validation，不能只报 test。

### 5.3 归因和消融

成功情景中，anchor-only 显示原始文本腐蚀压力；shuffled-user 去掉用户对齐；global-p 去掉个性化；full arm 证明 history alignment 是 load-bearing，而不是全局偏置或额外参数带来的表面变化。

| Arm | Steam NDCG@10 | ML1M NDCG@10 | Beauty NDCG@10 | ATG NDCG@10 |
|---|---:|---:|---:|---:|
| Host | -- | -- | -- | -- |
| Text anchor only | -- | -- | -- | -- |
| No user factor | -- | -- | -- | -- |
| Shuffled user factor | -- | -- | -- | -- |
| Global proposal control | -- | -- | -- | -- |
| Full risk-gated proposal | -- | -- | -- | -- |

若某消融只在 Beauty/Steam 预注册，则最终表必须明确两域范围，不能把空缺扩张为四域证明。

### 5.4 多 seed 与不确定性

成功证据包应区分训练随机种子变异和固定 checkpoint 下的用户重采样不确定性。二者不能合并成一个“稳定性”数字。

| 数据集 | Host mean±std | Ours mean±std | Paired Δ | 95% CI | Seeds | User bootstrap reps |
|---|---:|---:|---:|---:|---:|---:|
| Steam | -- | -- | -- | -- | -- | -- |
| ML1M | -- | -- | -- | -- | -- | -- |
| Beauty | -- | -- | -- | -- | -- | -- |
| ATG | -- | -- | -- | -- | -- | -- |

缺 user ID 的 records 不能产生用户 bootstrap；配置中的 `1000` 不能冒充实跑次数。

### 5.5 效率

全成功情景还需要证明可靠性层的部署代价可控。比较必须在独占 L20、相同 batch、precision、warm-up、timed workload 和 repeats 下执行。

| 方法 | Trainable params | Frozen buffers | Checkpoint size | Peak GPU GiB | Train examples/s | Eval examples/s | Sampling ms/user |
|---|---:|---:|---:|---:|---:|---:|---:|
| PreferGrow host | -- | -- | -- | -- | -- | -- | -- |
| 本文方法 | -- | -- | -- | -- | -- | -- | -- |

### 5.6 Evaluator 仲裁

所有本地方法必须在同一 evaluator 下整体移动，不能只替换有利方法。

| 方法 | 数据集 | Legacy HR@10 | Legacy NDCG@10 | Corrected HR@10 | Corrected NDCG@10 | Evaluated rows | Verdict flip |
|---|---|---:|---:|---:|---:|---:|---|
| SASRec/Caser/GRURec/BERT4Rec/DiffRec/Host/Ours | Steam/ML1M/Beauty/ATG | -- | -- | -- | -- | -- | -- |

## 6. 讨论

若上述空表最终由成功工件填满，最强的合理因果链是：受控文本 corruption 增加已观察下一正例暴露；预注册 `phi_R` 减少 proposal tilt；history-only 对齐在可用条件下贡献非平凡作用；显式零门回收宿主核。即使全部成功，也不能由此推出所有侧信息都应采用相同门、EPE 已观察所有潜在正例、或单步 TV 界能够保证 NDCG。

论文价值不应只写成“加文本后涨点”，而应写成：外部证据在 corruption mechanism 中既是资源也是风险，使用前应定价；将宿主 proposal 保留为显式插值端点，可在证据误导时给出可审计 fallback。该视角能迁移到内容驱动负例挖掘和其他 proposal-conditioned 生成过程，但精确回退依赖可显式保留的宿主 kernel。

## 7. 局限

即使所有实验成功，仍有以下边界：四个数据集不足以证明总体规律；多 seed 不能消除开发期 test 记录带来的研究者过拟合风险；文本 bank 是冻结单模态证据；`phi_R` 是条件级干预而非学习到的因果估计器；EPE 不是完整假负例率；理论保证只覆盖 proposal 和单步 transition row；可选扩散 baseline 在官方代码审计前不能参与本地排序。

## 8. 结论

本文提出一种在离散扩散推荐 forward proposal 中使用外部证据的 fallback-safe 方法。方法区分训练前发现、暴露测量和预注册干预，并在门关闭时保留精确宿主端点。本情景稿展示了所有预注册实验成功时能够成立的完整 AAAI 故事，同时故意留空所有结果数字，确保论文措辞不能先于证据。
