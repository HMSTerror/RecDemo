# Text-Side USDPD 设计

- **日期**: 2026-06-24
- **状态**: 设计已讨论通过；待写 implementation plan
- **投稿目标**: AAAI 2027 / KDD Research Track / RecSys-SIGIR 级别主会
- **实现宿主**: `PreferGrow / Fading to Grow`（离散偏好扩散）
- **一句话方法**: 我们不把侧信息可靠性用于 encoder 融合或 loss weighting，而是用显式**文本证据可靠性信号**去参数化离散偏好扩散核的 proposal 分布，从而共同塑形 preference fading 与 preference growing。

## 0. 设计动机

本设计是在原始 USDPD 多模态 spec 基础上的**收敛版主线**。收敛的原因不是方法降级，而是为了让论文主创新更聚焦到：

1. **kernel-level proposal shaping**
2. **显式可靠性信号的离散扩散核条件化**
3. **在 fixed history-derived conditioning 下保持 Markovianity 与 reversibility 的条件化链**

因此，图像模态不再作为主方法必要组成。本文将文本侧信息视为一种更稳定、更可规模化复现的实例化方式；方法的主语是离散扩散核，而不是多模态数目。

## 1. 论文定位与 claim 边界

### 1.1 核心定位

建议论文标题级定位为：

> **Reliability-Shaped Discrete Preference Diffusion for Sequential Recommendation**

对应中文可写为：

> **面向序列推荐的可靠性塑形离散偏好扩散**

或

> **基于显式证据可靠性信号的离散偏好扩散核条件化推荐方法**

`Uncertainty-Shaped ...` 可作为次选标题，但不建议作为最终标题。原因是 `uncertainty` 会直接贴近 uncertainty quantification、confidence calibration、UGR 等语义场，而本文真正贡献更接近：

- reliability-shaped proposal kernels
- evidence-conditioned discrete diffusion
- history-only reliability conditioning

### 1.2 主 claim

> Prior work typically uses side-information reliability signals at the encoder, fusion, or optimization level, while our method uses an explicit user-level reliability signal to parameterize the proposal distribution of a discrete preference-diffusion transition kernel.

该 claim 的中心不是文本模态，而是：

- `u` 是显式可靠性信号
- `p(u)` 是 kernel-level proposal
- 同一个 `p(u)` 同时控制 fading 与 growing

### 1.3 安全 claim

1. 首个把**显式可靠性信号**直接用于条件化离散偏好扩散转移核的推荐方法。
2. 通过单一用户级 proposal `p(u)` 共同塑形 preference fading 与 preference growing。
3. 当 `u = f(history)` 且在整条扩散轨迹中固定时，`x_t` 上的转移过程在条件于该 `u` 时保持 Markovian，并继承原 PreferGrow kernel 的 detailed-balance / reversibility 结构。

最安全、最有攻击力的主 claim 推荐写成：

> To the best of our knowledge, this is the first recommender method that uses an explicit history-only evidence reliability signal to condition the proposal kernel of discrete preference diffusion.

### 1.4 不安全 claim

禁止使用以下表述：

- "first multimodal diffusion recommender"
- "first uncertainty-aware recommender"
- "first text-aware diffusion recommender"
- "first trustworthy recommender"
- "first side-information-aware recommender"

### 1.5 术语约束

- `u`: **explicit text-evidence reliability signal**
- `p(u)`: **uncertainty-shaped proposal distribution**
- `s_content(h)`: **text-content anchor**
- 禁止使用 generic `trust score`、`confidence head`、`learned uncertainty head`

### 1.6 AAAI 包装约束

AAAI 版本必须把论文包装成：

- **how to condition discrete diffusion kernels with explicit reliability signals**

而不是：

- “给 PreferGrow 加文本”
- “一个文本增强的推荐系统”
- “一个 text-aware recommender trick”

推荐系统是主要验证场景，但论文贡献必须覆盖：

1. kernel parameterization
2. conditional Markov / reversible chain
3. empirical evidence on sequential recommendation

文本证据只是 reliability 的可复现实例化，不是本文主创新。

## 2. 方法骨架

### 2.1 保持不变的核心形式

宿主仍为 PreferGrow。核心形式保持为：

```text
p(u) = softmax((1 / τ(u)) · [log p_pop + λ(u) · s_content(h)])
```

其中：

- `p_pop`: behavior / popularity prior
- `s_content(h)`: 文本内容锚点
- `τ(u)`: proposal 的锐度控制
- `λ(u)`: content tilt 强度

方法的关键不在文本 feature 本身，而在于 `u -> (τ(u), λ(u)) -> p(u)` 这一条 kernel 参数化链。

### 2.1.1 必须形式化的 kernel-level 对象

为了让 novelty 站得住，正文必须把以下对象写成主方法，而不是 appendix：

1. `Q_u`：在固定 `u` 条件下的 proposal-conditioned transition kernel
2. `q_t(x_t | x_0, u)`：固定 `u` 条件下的 forward corruption distribution
3. limiting / stationary distribution：在固定 `u` 条件下链的极限分布形式
4. reverse ratio：proposal-conditioned reverse probability ratio

最低要求不是口头说“我们改了 kernel”，而是明确给出：

- proposal 如何进入转移矩阵
- 该矩阵在固定 `u` 下如何决定 fading / growing
- `p(u)` 为什么不是普通 text feature，也不是 negative sampling trick

对于 PreferGrow 风格核，固定 `u` 后的 proposal-conditioned limiting distribution 预期应回到 `p(u)` 本身；这一点应被写成正式命题或推论，而不是直觉性表述。

### 2.2 文本内容锚点 `s_content(h)`

无图像版中，`s_content(h)` 改为纯文本构造：

1. 为每个 item 建立**冻结文本 bank**
2. 用用户历史文本序列聚合成 `h_txt`
3. 对候选 item 文本向量与 `h_txt` 做相似度，得到 `s_content(h)`

语义上，`s_content(h)` 表示：

- 与用户历史文本语义更接近的内容方向
- 在 proposal 中承担 "content-similar hard negatives" 的角色

它只服务于 proposal shaping，不替代 PreferGrow 主干 score 模型。

### 2.3 显式可靠性信号 `u`

`u` 定义为用户级、仅依赖历史的显式文本证据可靠性信号，由三类 proxy 组成。

#### 2.3.1 behavior-text agreement

衡量用户行为历史方向与文本内容方向的一致程度。

直观解释：

- 若行为兴趣与文本语义方向一致，则文本证据更可信
- 若行为与文本方向分裂，则文本锚点不应被强推

这是删掉图像后最关键的 proxy，承担原多模态版中一部分 consistency 的作用。

#### 2.3.2 text completeness / quality

第一阶段只保留少量显式、低争议 proxy：

- 标题是否缺失
- 描述是否缺失
- 文本长度是否过短
- 字段覆盖率

这部分的目的不是构造复杂语言质量分数，而是判断：

> 该 item 文本是否足以作为可靠内容证据

禁止第一阶段引入：

- LLM 打分质量指标
- 复杂可读性指标
- 黑盒文本可信度头

#### 2.3.3 history reliability

沿用现有 USDPD 的 per-user 历史可靠性思路，保留：

- ESS
- recency
- history stability

这保证 `u` 不是单纯的文本分数，而是：

- 用户历史本身是否稳定
- 文本证据是否可信

的联合信号。

### 2.4 `u -> τ(u), λ(u)` 的解释

仍采用小型单调函数，不引入大黑盒头：

- 高可靠性: `τ(u)` 小，`λ(u)` 大，`p(u)` 更尖锐、更 content-tilted
- 低可靠性: `τ(u)` 大，`λ(u)` 小，`p(u)` 更接近 `p_pop`

论文主叙事保持为：

> 证据可靠时，更激进地利用内容锚点；证据不可靠时，更保守地回退行为先验。

## 2.5 理论连续性要求

理论部分必须把以下命题写清楚：

1. 对每个用户历史 `h`，先计算 `u = f(h)` 与 `p(u)`；在**固定该 `u`** 的条件下，`x_t` 上的 diffusion chain 是 Markovian。
2. 若 `Q_u` 依照 PreferGrow 原链的 detailed-balance 构造方式建立，并以 `p(u)` 作为 stationary / limiting proposal，则 proposal-conditioned chain 继承原有的 reversibility / detailed balance 结构。
3. reverse ratio 的闭式表达只是把原全局 proposal 替换为按用户条件化的 `p(u)`，而不是引入第二个独立 reverse bias。
4. 若 `u` 依赖 `x_t`、`t`、target item，或在 reverse 过程中动态变化，则上述主张不再自动成立。

正文推荐使用的严谨表述是：

> Conditional on history-derived `u`, the transition process over `x_t` remains Markovian and preserves the detailed-balance structure of the original PreferGrow kernel with the stationary proposal replaced by `p(u)`.

避免写成“条件化后无条件保持 Markovianity”。否则审稿人会质疑：user-level context 变化后是否仍是 homogeneous Markov chain。

否则，“保持 Markovianity 与 reversibility” 会被审稿人视为 slogan，而不是 theorem-level contribution。

## 3. 表示与数据协议

### 3.1 表示隔离原则

文本 bank 仅服务于：

- `s_content(h)`
- 文本证据可靠性 proxy

PreferGrow 原有 score / item 表示保持不变，避免把 encoder 切换扩散到整个 backbone。

### 3.2 文本 bank 要求

每个数据集建立一套冻结文本 bank。第一阶段允许复用现有文本 embedding 产物，只要满足：

1. item 级 key 对齐稳定
2. 可从相同文本面构造 `h_txt` 与 item text vectors
3. 不在训练中微调

若后续需要统一文本 encoder，可作为第二阶段实现优化，而非论文主创新。

对 `Beauty / ASO / ATG` 等数据集必须额外检查：

- 是否能获得 raw title / description / field-coverage 级别信息
- 若只能复用预计算 embedding 而没有足够文本字段元信息，则其上无法支撑完整的 text-evidence reliability 叙事

此时可以：

- 降为主表中的弱证据数据集
- 或放入 appendix，仅承担泛化验证，而不承担完整 proxy 解释

### 3.3 数据集选择原则

主表数据集必须满足：

1. 文本侧信息覆盖率高
2. 文本长度与字段完整性有足够分布差异
3. 已有稳定 processed split
4. 不引入额外大规模 raw-data 重建成本

### 3.4 推荐数据集组合

优先主表组合：

- `Steam`
- `ML1M`
- `Beauty`
- `ASO`

备用：

- `ATG`

规则：

- 若 `ASO` 的文本完整性 proxy 分布过平，或文本字段不足以支撑 quality proxy，则将其降到 appendix，换 `ATG`

该策略的目标是让文本版主线覆盖：

- 电影
- 游戏
- 商品类目

从而强化跨域泛化。

## 4. 与 PreferGrow 代码的集成

### 4.1 核心接口

沿用现有 USDPD 核心接口设计：

- `proposal_probs(history, u)` 取代全局 `nonpreference_probs()`
- `encode_history_context(history) -> {history_repr, u, proposal}`

### 4.2 必须贯通的图核位置

`proposal` 必须贯通进：

- `sample_prob`
- `score_entropy`
- `reverse_prob_ratio`
- `sample_nonpreference`

建议接口显式升级为：

- `sample_prob(i, sigma, proposal)`
- `score_entropy(score, sigma, x, x0, proposal)`
- `reverse_prob_ratio(score, dsigma, proposal)`
- `sample_nonpreference(batch_dims, proposal)`
- `prob_matrix_row(i, sigma, proposal)`

禁止通过 stateful graph 对象在内部缓存“当前 batch 的 proposal”。该做法会在训练 / 评估 / 多 GPU 情况下留下不稳定风险。

### 4.3 调用顺序约束

训练链中正向腐蚀先于 `model.forward`。因此：

- `u` 与 `proposal` 不能埋在 `forward()` 里现算
- 必须先通过 `encode_history_context(history)` 计算，再把结果传入图核采样与 reverse

这一条是实现约束，不是可选优化。

## 5. 实验设计

### 5.1 主指标

- HR@10
- NDCG@10

### 5.2 主表 baseline

主表最少包含：

1. `PreferGrow`
2. `AdaptiveWise / global proposal`
3. 一个连续扩散推荐 anchor（`DreamRec` 或 `DiffuRec`）
4. `iDreamRec`
5. 一个文本侧信息序列推荐 baseline（`RecFormer` 或 `UniSRec`）
6. `Ours (USDPD-text)`

baseline 数量不追求多，重点是：

- 同源对照强
- 需要区分“用户条件 proposal”与“更好的全局 proposal”
- 有 side-information 对照
- 有 continuous diffusion anchor

附录或 related work 实验中至少要讨论一个语义/离散 diffusion 近邻（如 `DDSR` / `SeeDRec` / `SDRec`）。

### 5.3 决定性 3-way ablation

必须保留：

1. `uncertainty-in-encoder`
2. `uncertainty-in-loss`
3. `uncertainty-in-kernel`（ours）

这里不是普通 ablation，而是全文最核心证据。只有当第 3 类 consistently 最强时，本文核心论断才成立。

### 5.3.1 必须补的反证式 ablation

建议主表或主 appendix 同时包含：

1. `global-p`: 不使用用户可靠性，只学习全局 proposal
2. `text-anchor only`: 固定 `λ, τ`，不用 `u`
3. `u-shuffle`: 在 batch / user 间打乱 `u`

若 `u-shuffle` 后性能不掉，则说明 `u` 没有学到可靠性；这会直接伤害论文主张。

### 5.4 `u` 组成消融

建议最少包含：

1. `agreement only`
2. `agreement + text completeness`
3. `agreement + history reliability`
4. `full u`

作用：

- 验证文本证据可靠性是否有独立价值
- 验证历史可靠性是否不能被文本 proxy 单独替代

### 5.5 诊断实验

#### 5.5.1 text corruption degradation

对文本证据做受控扰动：

- 描述字段 mask
- title 截断
- token dropout
- description 置空

预期：

- 高可靠性样本在文本证据受污染时退化更明显
- 这表明 kernel 真在利用 `u` 调 proposal

#### 5.5.2 metadata sparsity robustness

按文本完整性分桶：

- 高完整性
- 中完整性
- 低完整性

观察模型是否在低完整性样本上更保守地回退 `p_pop`

#### 5.5.3 reliability calibration

按 `u` 分桶，检查：

- 高 `u` 样本是否更 content-tilted
- 低 `u` 样本是否更 behavior-prior-tilted
- proposal shift 与命中率是否方向一致

#### 5.5.4 proxy-popularity correlation

必须补一个相关性表，报告以下量与 item popularity / exposure 的关系：

- text length
- field coverage
- `u`
- 主要 text completeness proxy

否则审稿人会怀疑你只是让 metadata 更完整或更热门的 item 获得更大 proposal mass。

### 5.6 成功标准

第一阶段论文级成功标准定义为：

1. 在至少 4 个数据集上，相对 PreferGrow 的 HR@10 / NDCG@10 取得稳定正收益，最好不是仅赢一个指标
2. 3-way ablation 中 `kernel` consistently 优于 `encoder` / `loss`
3. `global-p`、`text-anchor only`、`u-shuffle` 必须掉点，尤其 `u-shuffle` 必须掉点
4. 至少一项 text corruption 或 metadata sparsity diagnostic 与主假说一致
5. `u` 组成消融表明文本证据可靠性不是空变量
6. 正文给出 `Q_u`、`q_t(x_t|x_0,u)`、limiting distribution、reverse ratio，而不是只放 appendix

若只达到“主表小幅提升 + 普通 ablation”，不建议冲 AAAI main track。

### 5.7 投稿最低门槛

若要认真投 AAAI 2027，最低门槛定义为：

1. 主表至少 4 个数据集
2. `kernel > encoder/loss`
3. `u-shuffle` 明显掉点
4. 至少一个 corruption / sparsity 诊断支持假说
5. 做 proxy-popularity correlation 或 controlled analysis
6. baseline 至少覆盖 PreferGrow、global/adaptive proposal、continuous diffusion、text-guided diffusion、text SR
7. 报 reproducibility：固定 split、embedding bank 构造、seed、代码路径、数据协议

若这些达不到，优先考虑 RecSys / SIGIR / KDD workshop / weaker main submission，而不是 AAAI main。

## 6. Related Work 改写方向

无图像版的 related work 不再以多模态融合工作为主轴，而改为三段。

### 6.1 diffusion / generative recommendation

包含：

- `DreamRec`
- `DiffuRec`
- `PreferGrow`

目的：

- 建立生成式推荐背景
- 明确 PreferGrow 是直接宿主

### 6.2 uncertainty / reliability in recommendation

包含：

- `UGR`
- `TruthSR`
- 其他 reliability-aware recommendation

目的：

- 说明可靠性信号已被证明重要
- 但现有工作主要改 encoder / optimization / decision，不改 kernel

### 6.3 side-information-aware recommendation

包含文本侧信息推荐与 content-aware sequential recommendation。

目的：

- 说明文本证据是自然可靠性来源
- 但现有工作未将其用于离散扩散核 proposal 条件化

多模态文献如 `SPUMR` 可保留为背景或 appendix 中的邻近对比，不再作为 related work 主轴。

## 7. 关键风险与缓解

### 7.1 文本质量 proxy 与 popularity 混淆

风险：

- 长文本 item 可能天然更热门
- 完整 metadata 可能天然更高曝光

缓解：

- 报告文本质量 proxy 与 popularity 的相关性
- 在 appendix 中提供控制分析

### 7.2 `u` 退化为 feature soup

风险：

- 加入过多文本质量特征会让方法看起来像 feature engineering

缓解：

- 第一阶段只保留少量显式 proxy
- 保持 `u -> τ(u), λ(u)` 的单调、低容量映射

### 7.3 收益被误解为 "只是文本内容有用"

风险：

- 若无强对照，审稿人会认为只是加入文本相似性

缓解：

- 3-way ablation 必须进主表
- 明确比较 encoder / loss / kernel 三种注入位置
- `global-p` 与 `text-anchor only` 必须作为对照，证明不是单纯 text similarity proposal

### 7.4 被误解为“多模态版删图像”

风险：

- 审稿人可能把本文视为多模态 spec 的减配版

缓解：

- 在引言与方法定位中明确写成：
  - 研究对象是 reliability-conditioned proposal kernel
  - 文本证据是更稳定、更通用的实例化方式

### 7.5 理论主张写成口号

风险：

- 若没有 `Q_u`、`q_t(x_t|x_0,u)`、limiting distribution、reverse ratio 的明确形式，理论贡献会被认为只是叙事包装

缓解：

- 把 proposal-conditioned transition 写成正文主命题
- 在固定 `u` 条件下正式证明 Markovianity 与 reversibility

### 7.6 核心因果叙事不被经验结果支持

风险：

- 若 kernel 注入没有明显强于 encoder / loss 注入，则全文主 claim 会坍塌

缓解：

- 把 injection-location evidence 作为主表第一优先级
- 不在主 claim 上过度承诺，直到该证据稳定成立

### 7.7 被看成 adaptive negative sampling

风险：

- 审稿人可能将 `p(u)` 解读为“更复杂的 text-aware negative sampling”

缓解：

- 将 forward corruption、reverse ratio、stationary proposal、score entropy 全部写成 kernel-level 对象
- 在理论与实现上避免把 proposal 只出现在采样侧

### 7.8 AAAI 正文篇幅过载

风险：

- AAAI 正文页数有限，若理论、实验、related work 铺得过开，关键贡献会被挤到 appendix

缓解：

- 正文结构保持克制：
  - intro 约 1 页
  - method + theory 约 1.5-2 页
  - experiments 约 2 页
  - analysis / ablation 约 1 页
  - related + limitations 压缩处理
- appendix 放证明细节与扩展实验，但正文必须保留关键 ablation 和关键公式

## 8. 阶段性执行顺序

### 阶段 0：数据与 proxy 审计

1. 审计 `Steam / ML1M / Beauty / ASO / ATG` 的文本字段覆盖率
2. 选定主表 4 数据集
3. 确定第一版文本质量 proxy 分布是否有区分度

### 阶段 1：kernel 管线落地

1. 用冻结文本 bank 构造 `s_content(h)`
2. 落地 `u`
3. 接入 `proposal_probs(history, u)` 与 `encode_history_context`

### 阶段 2：核心立论验证

1. 跑通 PreferGrow 对照
2. 跑通 3-way ablation
3. 确认 kernel 注入优于 encoder / loss 注入

### 阶段 3：论文级证据

1. 主表
2. `u` 组成消融
3. text corruption / metadata sparsity diagnostics
4. reliability calibration
5. proxy-popularity controlled analysis
6. 正文理论对象整理（`Q_u`、`q_t`、limiting distribution、reverse ratio）

## 9. 一句话摘要

> We extend discrete preference diffusion with a user-level reliability-conditioned proposal kernel: an explicit history-only text-evidence reliability signal, computed from behavior-text agreement, text completeness, and history reliability, shapes a single proposal distribution that jointly controls where preference fades and grows back while, conditional on the fixed history-derived signal, preserving the original chain's Markovianity and detailed-balance structure.
