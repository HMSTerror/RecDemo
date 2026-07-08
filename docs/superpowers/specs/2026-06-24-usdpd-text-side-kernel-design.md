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
3. PreferGrow analytic / stationary-reversal ratio 的闭式表达只是把原全局 proposal 替换为按用户条件化的 `p(u)`，而不是引入第二个独立 reverse bias；若讨论数据分布出发的精确 reverse kernel，则必须额外说明其依赖当前 marginal。
4. 若 `u` 依赖 `x_t`、`t`、target item，或在 reverse 过程中动态变化，则上述主张不再自动成立。

正文推荐使用的严谨表述是：

> Conditional on history-derived `u`, the transition process over `x_t` remains Markovian and preserves the detailed-balance structure of the original PreferGrow kernel with the stationary proposal replaced by `p(u)`.

避免写成“条件化后无条件保持 Markovianity”。否则审稿人会质疑：user-level context 变化后是否仍是 homogeneous Markov chain。

否则，“保持 Markovianity 与 reversibility” 会被审稿人视为 slogan，而不是 theorem-level contribution。

### 2.6 Proposal-conditioned kernel 的正式命题与证明

本节给出正文可直接使用的理论版本。证明只依赖有限状态 Markov kernel 的标准性质，因此不要求文本 encoder、`u` 的具体 proxy 或 score model 具有额外假设。关键约束是：对给定用户历史 `h`，`u=f(h)` 与由它确定的 proposal `p_u` 在整条 forward / reverse 扩散轨迹中固定。这里“固定”的是 proposal，而不是条件化到某一条已经实现的随机路径。

#### 2.6.1 状态空间与 proposal 定义

令 item 状态空间为固定有限集合

```text
Ω = {1, ..., M}
```

若 PreferGrow 实现中使用额外的 disliked / non-preference pseudo-item，则将该 pseudo-item 作为 `Ω` 的最后一个坐标即可；下面证明不区分真实 item 与 pseudo-item，只要求 proposal 是同一状态空间上的概率向量。以下采用 row-vector convention：分布 `μ` 按 `μP` 演化，`Q_u` 是 CTMC generator 而不是 transition matrix。

对用户历史 `h`，先计算

```text
u = f(h)
p_u = p(u) = softmax((1 / τ(u)) · [log p_pop + λ(u) · s_content(h)])
```

其中 `p_u(i) > 0` 且 `Σ_i p_u(i) = 1`。严格正性由 softmax 给出；实际实现中需要对 `p_pop` 做 `ε` smoothing，或把零概率 item 显式排除在 support 外。若实现中对部分 item 做 hard mask，则需要把下面的不可约性表述改成“在未被 mask 的 support 上成立”。

理论命题使用以下假设：

1. **有限状态空间**：`Ω` 在整条轨迹中固定。
2. **合法 proposal**：`τ(u)>0`，`λ(u)` 与 `s_content(h,i)` 有限，且 `p_u` 是 `Ω` 上的归一化概率分布。
3. **固定 conditioning**：`u=f(h)` 只依赖已观测历史 `h`，不依赖当前扩散状态 `x_t`、未来 target item、采样路径或 reverse 过程中的动态预测值。
4. **外生 schedule**：`α_t∈[0,1]` 或 `α_σ=exp(-σ)` 由预设 noise schedule 决定，不依赖扩散路径。
5. **reverse-ratio 可逆性**：若使用 `P^{-1}` 形式的 analytic reverse ratio，则需要 `α>0`。当 `α=0` 时 forward reset kernel 仍合法，但矩阵退化为 rank-one，不可逆。

定义 rank-one proposal kernel

```text
Π_u(i, j) = p_u(j),    i, j ∈ Ω.
```

也就是说，`Π_u` 的每一行都是同一个用户条件 proposal `p_u`。Text-Side USDPD 的 forward generator 定义为

```text
Q_u = Π_u - I,
```

等价地，

```text
Q_u(i, j) = p_u(j),          j ≠ i
Q_u(i, i) = -(1 - p_u(i)).
```

该定义与 PreferGrow / AdaptiveWise 的矩阵形式一致：原本的全局 `nonpreference_probs()` 被替换为用户条件 proposal `p_u`。这里的 corruption 允许从 `p_u` 重采样后仍采回原状态；如果实现改成“必须替换成不同 item”的 conditional resampling，则 stationary distribution 一般不再是 `p_u`，需要另行证明。如果代码采用 column convention，则矩阵写作转置形式；概率内容不变。

#### 2.6.2 Forward corruption distribution

**命题 1（proposal-conditioned transition）**
固定用户历史 `h` 与 `u=f(h)`。令扩散强度为 `σ ≥ 0`，记

```text
α_σ = exp(-σ).
```

则由 `Q_u` 生成的 forward transition kernel 为

```text
P_{σ,u}
= exp(σ Q_u)
= α_σ I + (1 - α_σ) Π_u.
```

因此，对任意初始状态 `x_0` 与任意 `x ∈ Ω`，

```text
q_σ(x | x_0, u)
= P_{σ,u}(x_0, x)
= α_σ · 1{x = x_0} + (1 - α_σ) · p_u(x).
```

**证明。**
因为 `Π_u` 的每一行都是 `p_u`，所以

```text
Π_u^2(i, j) = Σ_k Π_u(i, k)Π_u(k, j)
            = Σ_k p_u(k)p_u(j)
            = p_u(j)
            = Π_u(i, j).
```

即 `Π_u` 是 idempotent projection。又 `Q_u=Π_u-I`，且 `Π_u` 与 `I` 可交换，因此

```text
exp(σQ_u)
= exp(σ(Π_u-I))
= exp(-σ) exp(σΠ_u).
```

由 `Π_u^2=Π_u` 可得

```text
exp(σΠ_u) = I + (exp(σ)-1)Π_u.
```

于是

```text
exp(σQ_u)
= exp(-σ)I + (1-exp(-σ))Π_u
= α_σ I + (1-α_σ)Π_u.
```

取第 `x_0` 行第 `x` 列即得 `q_σ(x|x_0,u)`。证毕。

这说明 `p_u` 不是只出现在 negative sampling 侧，而是直接进入 forward corruption matrix。`σ` 控制“是否保持原偏好”，`p_u` 控制“偏好 faded 后流向哪里”。

若论文采用离散扩散步 `t=1,...,T`，并写

```text
P_{t,u} = α_t I + (1-α_t)Π_u,
bar_α_t = ∏_{r=1}^t α_r,
```

则由 `Π_u^2=Π_u` 立刻得到

```text
P_{1,u}P_{2,u}...P_{t,u}
= bar_α_t I + (1-bar_α_t)Π_u.
```

因此离散步 forward corruption distribution 为

```text
q_t(x_t=x | x_0, u)
= bar_α_t · 1{x=x_0} + (1-bar_α_t) · p_u(x).
```

这就是正文中 `q_t(x_t|x_0,u)` 应使用的闭式形式；连续 `σ` 形式只是取 `bar_α_t=exp(-σ)` 的记法。

#### 2.6.3 Conditional Markovianity

**命题 2（固定 `u` 条件下的 Markovianity）**
对每个用户历史 `h`，先计算并固定 `u=f(h)`。若 forward 过程只通过 `P_{Δσ_t,u}` 从 `x_t` 产生 `x_{t+1}`，则条件于该固定 `u`，`(x_t)` 是 Markov chain：

```text
Pr(x_{t+1}=j | x_0, ..., x_t, h, u)
= Pr(x_{t+1}=j | x_t, u)
= P_{Δσ_t,u}(x_t, j).
```

若时间步使用不同的 `Δσ_t`，该链是 time-inhomogeneous Markov chain；若在连续 `σ` 时间或固定步长下看，则由同一个 generator `Q_u` 生成，是 homogeneous Markov semigroup。

**证明。**
在固定 `u` 后，`p_u` 与 `Q_u` 都是确定的。构造上，下一步采样只调用当前状态 `x_t`、当前扩散步长 `Δσ_t` 和固定 kernel `P_{Δσ_t,u}`，不读取更早的 `x_0,...,x_{t-1}`。因此条件分布只依赖 `x_t` 与 `u`，满足 Markov property。证毕。

该命题不能改写为“无条件 Markovian”。若把不同用户历史混合在一起但不把 `u` 纳入条件变量，观测到的边际过程一般是 mixture of Markov chains，不必仍是同一个 homogeneous Markov chain。

#### 2.6.4 Stationary / limiting distribution

**命题 3（stationary proposal 与 limiting proposal）**
固定 `u` 后，`p_u` 是 `P_{σ,u}` 的 stationary distribution：

```text
p_u P_{σ,u} = p_u,    σ ≥ 0.
```

并且对任意初始分布 `μ`，

```text
μ P_{σ,u}
= α_σ μ + (1 - α_σ)p_u
→ p_u,    σ → ∞.
```

**证明。**
由于 `p_uΠ_u=p_u` 且 `p_uI=p_u`，

```text
p_uP_{σ,u}
= p_u[α_σI + (1-α_σ)Π_u]
= α_σp_u + (1-α_σ)p_u
= p_u.
```

对任意分布 `μ`，有 `μΠ_u=p_u`，因此

```text
μP_{σ,u}
= μ[α_σI + (1-α_σ)Π_u]
= α_σμ + (1-α_σ)p_u.
```

当 `σ→∞` 时 `α_σ=exp(-σ)→0`，故极限为 `p_u`。证毕。

该结论给出 Text-Side USDPD 的 limiting distribution：固定用户可靠性后，forward corruption 的极限不是全局 popularity，也不是无条件 uniform，而是用户条件 proposal `p(u)`。

注意，`p_u` 是 stationary / limiting distribution，不等于任意有限噪声强度下的 marginal。有限 `σ` 时，

```text
μP_{σ,u} = α_σ μ + (1-α_σ)p_u,
```

除非 `μ=p_u` 或 `σ→∞`，否则通常不等于 `p_u`。

#### 2.6.5 Detailed balance 与 reversibility

**命题 4（proposal-conditioned reversibility）**
固定 `u` 后，`P_{σ,u}` 关于 `p_u` 满足 detailed balance：

```text
p_u(i) P_{σ,u}(i, j)
= p_u(j) P_{σ,u}(j, i),
    i,j ∈ Ω.
```

因此，forward chain 在固定 `u` 条件下是 reversible 的。

**证明。**
由命题 1，

```text
P_{σ,u}(i,j) = α_σ · 1{i=j} + (1-α_σ)p_u(j).
```

若 `i=j`，等式两边显然相同。若 `i≠j`，则

```text
p_u(i)P_{σ,u}(i,j)
= p_u(i)(1-α_σ)p_u(j)
= p_u(j)(1-α_σ)p_u(i)
= p_u(j)P_{σ,u}(j,i).
```

故 detailed balance 成立。证毕。

这正是“继承原 PreferGrow reversibility 结构”的可证明版本：不是额外假设新的 reverse bias，而是把原链中的 stationary proposal 从全局 proposal 替换为用户条件 `p_u` 后，rank-one proposal kernel 的 detailed-balance 结构仍然成立。

#### 2.6.6 Reverse ratio 的闭式替换

**命题 5（stationary reverse ratio 只替换 proposal）**
令 `δ>0` 为一个 reverse step 对应的扩散强度差，记

```text
α_δ = exp(-δ),
P_{δ,u} = α_δ I + (1-α_δ)Π_u.
```

按代码中最后一维 score / ratio 向量作为行向量右乘 transition matrix 的约定，对任意 `r ∈ R^M`，冻结链的 stationary-reversal / analytic inverse-ratio operator 可写为

```text
r P_{δ,u}^{-1}
= α_δ^{-1} r + (1 - α_δ^{-1}) · <r, 1> · p_u,
```

其中 `<r,1>=Σ_i r(i)`。因此，在固定 `u` 且使用同一 PreferGrow analytic reverse 近似的前提下，若原 PreferGrow 使用全局 proposal `p_global`，Text-Side USDPD 的 proposal-conditioned reverse ratio 只是把该式中的 `p_global` 替换为 `p_u`：

```text
reverse_ratio_u(r)
= exp(δ) r + (1 - exp(δ)) · <r,1> · p_u.
```

在实现中，该向量再与 `P_{δ,u}` 的对应 row / column 相乘，得到 analytic reverse step 的候选概率。

**证明。**
因为 `Π_u^2=Π_u`，矩阵

```text
P_{δ,u}=α_δI+(1-α_δ)Π_u
```

在 `δ<∞` 时可逆，且其逆为

```text
P_{δ,u}^{-1}
= α_δ^{-1}I + (1-α_δ^{-1})Π_u.
```

直接相乘验证：

```text
[αI+(1-α)Π][α^{-1}I+(1-α^{-1})Π]
= I + [α(1-α^{-1}) + (1-α)α^{-1} + (1-α)(1-α^{-1})]Π
= I.
```

将该逆右作用在行向量 `r` 上，并用 `rΠ_u = <r,1>p_u` 的坐标形式，即得闭式表达。证毕。

该命题说明，在冻结链与 stationary-reversal 参考下，reverse ratio 没有引入第二个独立的 text-aware bias。所有文本侧可靠性只通过同一个 `p_u` 进入：

1. forward corruption `P_{σ,u}`
2. limiting proposal `p_u`
3. detailed balance reference measure `p_u`
4. analytic reverse ratio operator `P_{δ,u}^{-1}`

这也是避免被误解为 adaptive negative sampling 的关键数学点。

需要避免更强但不成立的表述：若 forward process 从任意数据分布 `μ_0` 而非 stationary distribution `p_u` 出发，则真实反向条件分布一般依赖当前 marginal `μ_t`。精确反向 kernel 的形式是

```text
P_rev(j, i)
= μ_s(i) P_{s,t,u}(i, j) / μ_t(j),
```

因此不能仅由 detailed balance 推出“任意数据分布下的真实 reverse kernel 只替换 proposal”。本文可安全主张的是：冻结 proposal 后，PreferGrow 原 analytic reverse operator 中的 proposal 项被一致地替换为 `p_u`；非平衡精确反向过程仍由 score / ratio model 近似。

#### 2.6.7 证明边界与反例条件

上述命题依赖以下边界条件，论文中必须显式保留：

1. `u` 必须是 history-only：`u=f(h)`，不能依赖当前 corrupted state `x_t`、reverse step `t`、待预测 target item，或模型当前 score。
2. `u` 必须在同一条 forward / reverse 扩散轨迹中固定。若每一步动态更新 `u_t`，过程仍可构造成 Markov chain on `(x_t,u_t)`，但单独的 `x_t` 不再自动继承同一个 `Q_u` 的 homogeneous semigroup 与 detailed balance。
3. `p_u` 必须和 kernel 使用同一状态空间。若实现有 disliked pseudo-item，则该坐标必须在 `p_u`、`P_{σ,u}`、`reverse_ratio_u` 中一致出现，不能只在采样函数里出现。
4. 若 hard mask 使某些 item 的 `p_u(i)=0`，stationary 与 convergence 仍可在 support 上表述，但 full-support irreducibility 与所有 item 间的 strictly positive transition 不再成立。
5. 上述 transition 形式要求从 `p_u` 直接重采样，并允许 self-resampling。若使用 `j≠i` 的强制替换、top-k / top-p 截断、或依赖当前状态的 mask 后重归一化，detailed balance 一般会被破坏，必须重新证明。
6. reverse ratio 的“只替换 proposal”表述只适用于冻结链的 stationary-reversal / PreferGrow analytic inverse-ratio operator。若声称数据分布出发的精确 reverse kernel，则必须额外引入当前 marginal `μ_t`。
7. 若 `τ(u)` 或 `λ(u)` 在训练时由当前 batch 的 `x_t` 或 target label 反向泄漏得到，则理论上证明的是另一个数据依赖 kernel，不能再声称是 history-conditioned proposal kernel。

因此，论文中最严谨的主张应写成：

> Conditional on a fixed history-derived reliability signal `u=f(h)`, Text-Side USDPD replaces the original global proposal in the PreferGrow transition semigroup by a user-conditioned proposal `p_u`. The resulting finite-state chain remains Markovian, has limiting distribution `p_u`, satisfies detailed balance with respect to `p_u`, and yields the same stationary-reversal analytic ratio form with the proposal term replaced by `p_u`; exact non-stationary reverse kernels may still depend on the current marginal distribution and are handled by the score / ratio model.

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

#### 2026-06-25 修正：raw-data-first 执行协议

本节由 `docs/reports/2026-06-24-raw-data-protocol-recommendation.md` 的最新落地结论覆盖。后续实现与论文实验不再把仓库内 legacy `dataset/*/*.df` 视为科学主协议，而是使用 `scripts/build_paper_datasets.py` 从 rawdata 一步步重建数据集，冻结生成后的 split，并让 PreferGrow、USDPD-text 与全部 baseline 使用同一批 regenerated artifacts。

强制执行后果：

1. 主表数据集必须记录 raw source、item mapping、filtering rule、dedupe rule、split rule 与 window-expansion rule。
2. text bank、proxy features、image/text manifests 与推荐 split 必须全部对齐到最终 regenerated `item_id`。
3. legacy processed files 只能作为兼容性参考，不能与 regenerated raw-data splits 混入同一张主结果表。
4. release package 必须保存 `train_data.df`、`val_data.df`、`test_data.df`、`item_mapping.csv`、text/proxy manifests 与 `protocol.json`。

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
