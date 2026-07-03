# AAAI-27 冲刺:Fallback-Safe 证据条件化核 设计

- **日期**: 2026-07-02
- **状态**: 设计已分节讨论通过;待写 implementation plan
- **投稿目标**: AAAI-27 主会(摘要 2026-07-21 / 全文 2026-07-28 / 补充材料 2026-07-31,AoE)
- **与旧 spec 的关系**: 本文档是 `2026-06-24-usdpd-text-side-kernel-design.md` 的冲刺修订版。旧 spec 的理论骨架(命题 1–5)、图核接口(§4)、数据协议(§3)原样继承;旧 spec 的 `u -> (τ, λ)` 三旋钮参数化(§2.1/2.4)、u 三分量组成(§2.3)与主表成功标准(§5.6/5.7)由本文档取代。
- **一句话方法**: 把用户级证据可靠性门控 `g(u)` 作为唯一旋钮,在核心 PreferGrow 的**可学习全局 proposal**与冻结文本锚点之间做插值;`g=0` 时精确归约为核心核(fallback-safe),文本证据无信息的数据集自动退回核心行为。

## 0. 背景与决策记录

### 0.1 触发条件

截至 2026-07-02 冻结基线(`2026-07-01-text-side-vs-core-main-table-remote-v77.csv`):

| 数据集 | delta_test_p2_ndcg10 | 角色 |
| --- | ---: | --- |
| Steam | +0.0064 | 正锚点 |
| ATG | +0.0019 | 正锚点 |
| Beauty | −0.0006 | 机制主证据 |
| ML1M | **−0.0622** | 负约束 |

按旧 spec §5.7 的门槛,该证据状态不足以投 AAAI 主会;冻结的 safe claim(`regime-dependent`)在 AAAI 录取率下是弱拒信号。用户决策:**冲 AAAI-27 这一轮**,采用方案 A(No-Regret 重锚定),算力充足(远程并行多跑、单跑 ≤1 天)。

### 0.2 ML1M 失败的三个结构性诊断

1. **agreement 无零点校准**(`model/text_side.py` 的 `encode_history_context`):agreement 是历史项对其文本均值方向的 `(cos+1)/2` 重缩放相似度。本地 legacy embedding 指示性检验:**随机伪历史即可得 agreement ≈ 0.81 (ML1M) / 0.77 (Beauty) / 0.87 (Steam)** — 地板极高且随数据集文本几何漂移,而 `u` 的绝对值直接决定 kernel 工作点,导致跨数据集行为失控(表面的 regime-dependent)。
2. **回退极限是退化核而非核心核**:`u→0` 时 `pseudo_mass = clamp((1−u)^p, 0.05, 0.95) → 0.95`;ML1M 典型 `u≈0.7` 下 pseudo_mass≈0.3,而核心的伪物品质量是**学出来的**,量级错位与文本质量无关,单独可贡献大幅落后。
3. **冻结核打可学习核**:核心 PreferGrow 的全局 proposal 是 `softmax(p1)`、`p1` 可学习(`graph_lib.py:1171-1174`);text-side 自适应 proposal 零可学参数。文本方向弱的数据集上结构性必输。

诊断 1 的生产级复核(t5-xl bank 上)列为 Gate 0 必做项。

### 0.3 创新性核查记录(2026-07-02)

- **PreferGrow (NeurIPS 2025, arXiv:2509.26063)**:forward kernel 确认为全局(转移矩阵无用户索引);个性化仅在 score/guidance 侧(CFG 式条件丢弃 + 推理期全局标量 `w` 外推)。**本文位置:个性化 kernel 本身,是同一框架中空缺的另一半。**
- **CDRec (arXiv:2511.12114)**:popularity-aware 转移矩阵/schedule,item 级全局信号,非每用户、非可靠性。
- **TDPM (arXiv:2606.01670)**:时间轴调制,作用于 semantic-ID token,与证据可靠性无关。
- **A-CFG (arXiv:2505.20199) / CFG-in-RecSys (arXiv:2409.10494)**:自适应 guidance 在 score 侧、信号为模型自身置信度,非推荐扩散核。
- **一句话定位**:*PreferGrow personalizes the score; we personalize the kernel — safely.*
- 已知攻击面与防御:数学初等(贡献在注入位置+保证+经验证据)、adaptive negative sampling 之嫌(旧 spec §7.7 防御继承)、为何不端到端学 u(history-only 理论要求 + u-shuffle 控制)。

## 1. 方法改动(v2 kernel)

### 1.1 新 proposal 形式

用单一证据门控替换现有 温度缩放 / popularity_mix / pseudo_mass 三旋钮:

```text
p_u = p_core(伪物品)·e_pseudo + (1 − p_core(伪物品)) · [ (1−g(u))·p̃_core + g(u)·c_h ]

p_core = softmax(p1)        # 与核心 PreferGrow 相同的可学习全局 proposal,联合训练、参数结构不变
p̃_core = p_core 在真实物品坐标上的重归一化
c_h    = softmax(sim(h_txt, item_emb)/τ0)   # 冻结文本锚点;τ0 固定超参,初值沿用现配置 temperature=0.2;无文本/低 completeness 物品在 c_h 内降权
g(u)   = g_max · clamp(ũ, 0, 1)             # 单调、低容量、无黑盒;g_max 固定超参,初值 0.5
ũ      = (A_h − μ_null(L_h)) / (k·σ_null(L_h))   # 零点校准后的 agreement;k 固定超参,初值 2.0(高于 null 两个标准差时 ũ=1)
```

无伪物品配置(`is_disliked_item=False`)时退化为 `p_u = (1−g(u))·p_core + g(u)·c_h`,命题不受影响。

> **2026-07-03 修订**:Gate 0 失败后,`g` 增加数据集级效用因子(见 §7);本节其余定义不变。

### 1.2 四个关键设计决定

1. **伪物品质量完全冻结在核心值**:`u` 不再触碰 pseudo mass。这是命题 6 干净成立的前提,也是诊断 2 的根治。
2. **零点校准带长度匹配**:`μ_null(L), σ_null(L)` 在每个数据集的冻结 bank 上抽随机伪历史离线计算一次(按历史长度 L 分桶),训练/推理期查表。仍是 history-only、无目标泄漏。**`g(≤null) = 0`** 使"文本 bank 无信息的数据集自动退回核心核"成为方法的可证伪推论;ML1M 即其实证。
3. **u 收敛为校准 agreement 单信号**(agreement-centered):Beauty 证据表明 history_reliability 是负担、completeness 弱。二者降级为 u-组成消融臂;completeness 仅用于 `c_h` 内部对无文本物品降权。
4. **消融模式在 v2 下的映射**:`global_p` = 强制 `g≡0`(恰为核心等价检查);`text_anchor_only` = 固定 `g≡g_max`(无可靠性门控);`u_shuffle` = 在 batch/user 间打乱 `ũ`。三种注入模式(kernel/encoder/loss)基建原样保留。

### 1.3 不动的部分

图核 proposal 贯通接口(`graph_lib.py:1323+` 的 `sample_prob / score_entropy / reverse_prob_ratio / sample_nonpreference / prob_matrix_row`,均带 `proposal` 参数)、score 模型、训练循环、数据协议(raw-data-first)、现有测试基建。改动集中于 `model/text_side.py`;新增离线脚本 `scripts/build_agreement_null_curves.py`(+ 对应测试)。

### 1.4 实现级验收条件

1. **等价性测试**:`g≡0` 配置下,forward corruption、score_entropy、reverse ratio 与核心 PreferGrow 在数值容差内逐项一致(单测),且短跑训练曲线与核心重合(集成检查)。未过此关不开远程主表重训。
2. 梯度经 `p_u` 流向 `p1` 的路径与核心一致;不引入新的可学习模块。
3. null 曲线构建可复现:固定 seed、bank 哈希入 `protocol.json`。

## 2. 理论增量

命题 1–5(旧 spec §2.6)对任意合法固定 proposal 已证,原样适用于混合形式 `p_u`。新增:

- **命题 6(fallback-safe 归约)**:若 `g(u)=0`,则 `p_u = p_core`,故 `Q_u ≡ Q_core`,forward corruption、stationary distribution、analytic reverse ratio、score-entropy 权重全部与核心 PreferGrow 重合。证明约 3 行,进正文。
- **引理(有界偏离)**:`TV(p_u, p_core) ≤ g(u)`。一行证明;给出有限 `g` 下偏离宿主核的定量安全阀。
- 术语约束:正文用 **fallback-safe / anchored**;"no-regret" 仅作非正式描述并加脚注,避免与 online-learning 的 regret 界撞车。

## 3. 实验矩阵与 GO/NO-GO 门

### 3.1 三档实验(约 28 跑,单跑 ≤1 天,并行 ≥3,约 9–10 日历日)

| 档 | 内容 | 规模 |
| --- | --- | --- |
| P0 生死线 | ① 生产 bank null 曲线 + ũ 分布诊断(离线);② `g≡0` 核心等价检查;③ Steam/ML1M/Beauty/ATG 四数据集 v2 主表重训 | ~5 跑 |
| P1 主张支撑 | 控制组(u_shuffle / text_anchor_only / global_p)于 Beauty+Steam;Beauty token_dropout corruption 链在 v2 下重跑(复用 corrupted bank) | ~8 跑 |
| P2 加分项 | u-组成消融(校准agreement / +completeness / +history / 旧 full_u)、3-way 注入(Beauty+Steam)、主表 3 seeds | ~15 跑;时间不够按此序砍 |

### 3.2 四道门

| 门 | 日期 | 通过条件 | 未过动作 |
| --- | --- | --- | --- |
| Gate 0 | ≤7/5 | 生产 bank 上真实用户 ũ 分布支持诊断 1(经验判据:`|median ũ_ML1M| < 0.5` 且 `median ũ_Steam / ũ_Beauty > median ũ_ML1M`);`g≡0` 等价性测试通过 | 假设修正后再开训;不过此门不开主表重训 |
| Gate 1 | ≈7/9 | ML1M v2 首跑 `delta_test_p2_ndcg10 > −0.01` | 若 ≤ −0.03,允许一次诊断迭代 |
| Gate 2 | 7/14(降级检查点) | 主表 v2 + 控制组齐,定最终主张强度 | 三出口:强(fallback-safe + 正锚点保持)/ 中("safety without loss" 主线)/ 弱(按冻结口径 B 方案成稿,新诊断作分析节) |
| Gate 3 | 7/21 / 7/28 / 7/31 | 摘要 / 全文 / 补充材料提交 | — |

写作自 7/6 起与实验并行:先用冻结数字起 LaTeX 骨架,v2 数字落地即替换。

## 4. 论文骨架

### 4.1 标题候选

1. `Fallback-Safe Evidence Conditioning for Discrete Preference Diffusion`(推荐)
2. `Reliability-Gated Proposal Kernels for Discrete Preference Diffusion in Sequential Recommendation`

### 4.2 主 claim

> We personalize the *kernel* of discrete preference diffusion — not the score — via a single evidence-gated interpolation anchored to the host's learned proposal: it provably reduces to the host kernel when text evidence is uninformative (TV ≤ g(u)), and empirically gains where evidence is reliable while matching the host where it is not.

### 4.3 四条贡献

1. kernel 侧个性化(对照 PreferGrow 的 score 侧),保 Markovianity / detailed balance(命题 1–5)。
2. fallback-safe 设计(命题 6 + TV 界)与零点校准 — 把未校准可靠性信号造成的虚假 regime 依赖变成被解释的现象。
3. 机制证据链:控制组、corruption backoff、校准分桶(Beauty 资产复用)。
4. 四数据集验证理论预测:证据富数据集获益、证据贫的 ML1M 归于持平 — 可证伪预测被确认。

### 4.4 3-way 的处理

不再声称 kernel 全局最优;论证 **kernel 是唯一能表达安全归约保证的注入位置**(encoder/loss 注入无法定义"退回宿主核"),3-way 降级为 regime 分析节。

### 4.5 页面预算与图

7 页正文(投稿时按 AAAI-27 CFP 复核):Intro 1.0 / PreferGrow 预备 0.75 / 方法+理论 1.25(命题 6 进正文,余证明进附录)/ 实验 2.5 / 校准分析 0.5 / Related 0.5 / 结论+限制 0.25。

图:方法示意、null-校准图(ML1M 故事一图)、主表、corruption backoff 机制图、校准分桶;复用 `generate_main_path_paper_figures.py` 工具链。

### 4.6 明确不 claim

全局一致更优;metadata sparsity robustness(负结果如实进附录);"first multimodal / first uncertainty-aware" 等旧 spec §1.4 禁用句全部继承。

### 4.7 Related work 定位轴

PreferGrow(score 侧个性化)/ CDRec(全局 popularity schedule)/ TDPM(时间轴)/ A-CFG(置信度自适应 guidance,LM 域)/ UGR·TruthSR(encoder/loss 层 reliability)/ 旧 spec §6 的三段式结构继承。

## 5. 风险与缓解

| 风险 | 缓解 |
| --- | --- |
| 生产 bank 上 ũ 分布不支持诊断 1 | Gate 0 先行离线复核,未过不开训 |
| ML1M v2 仍明显为负 | Gate 1 一次诊断迭代;Gate 2 三出口均有稿可写 |
| 正锚点(Steam/ATG)在 v2 下缩水 | "safety without loss" 中出口:安全性主线 + 机制链承载 |
| 数学被评为初等 | 贡献定位在注入位置 + 保证 + 经验证据;命题 6/TV 界给量化把手 |
| 被读作 adaptive negative sampling | 旧 spec §7.7 防御:kernel 级对象全覆盖 + 控制组 |
| 时间溢出 | P2 按序砍;写作并行;7/14 硬降级检查点 |

## 6. 一句话摘要

> 我们把 PreferGrow 的个性化从 score 侧补到 kernel 侧:一个零点校准的、history-only 的证据可靠性门控,在宿主可学习全局 proposal 与冻结文本锚点之间插值;门控归零时核精确退回宿主核(fallback-safe),因此文本证据无信息的数据集自动持平、证据可靠的数据集获益 — ML1M 与 Steam/ATG 恰好构成该可证伪预测的两端实证。

## 7. 修订 A(2026-07-03):Gate 0 失败后的效用门控修订

- **状态**: 已获用户批准(2026-07-03);φ 参数与 Gate 0-v2 判据在生产数据产出前冻结。
- **触发证据**: `docs/reports/data/2026-07-02-gate0/`(Gate 0 verdict=fail;96 个全局 k/σ 修复候选 0 通过;ML1M median ũ=1.428 全场最高,Steam=0.107 最低,与 §3.2 Gate 0 判据的预测近乎反序)。

### 7.1 诊断结论(构念错误,非缩放错误)

1. 零点校准机制本身工作正常(0.93–0.95 的 agreement 地板被正确扣除),但残差分子排序为 ML1M(0.0113)≫ Beauty(0.0088)> ATG(0.0080)≫ Steam(0.0022):**问题在统计量测什么,不在 σ 怎么估**。全局单调缩放(k/σ_scale)原理上不可能改变跨数据集排序;ML1M 只有单一长度桶,按桶稳健重估(原 Family A)对其为空操作。
2. 本地 legacy-bank 预检(`tmp/check_text_utility_legacy.py`,方向性证据):train-only 文本相似度对真实下一物品的判别力 text-AUC = ML1M **0.758**(popularity 负例 0.741)、Steam 0.589(0.595)、Beauty 0.508(0.505)。**ML1M 不是证据贫数据集 — 它文本证据强到能预测正例;Beauty 反而接近随机。**
3. 机制解释(当前最优统一假说,待生产复核):proposal 是 corruption/负采样分布,不是 ranker。文本 AUC 高的数据集(ML1M)上,文本倾斜把腐蚀质量砸向"可能的未来正例"(false-negative 污染,对应 v1 的 −0.06);文本 AUC 低但相似度结构存在的数据集(Beauty)上,倾斜产生 informative hard negatives(对应 v1 文本锚点获益)。

### 7.2 修订后的门控

```text
g(u) = g_max · φ(U_ds) · clamp(ũ, 0, 1)

U_ds  = 数据集级 train-only 文本效用统计量(见 §7.3)
φ(U)  = clip((0.70 − U) / 0.10, 0, 1)    # 冻结:U ≤ 0.60 全开,U ≥ 0.70 全关
```

- `φ(U_ds)` 是数据集级常数,由固定公式从**训练 split** 离线计算,与 `p_pop` 同等泄漏级别(设计内已有先例);用户级 `ũ` 因子与 §1.1 定义不变,history-only 边界不破。
- **理论不受影响**:`g` 仍是混合权重,命题 6(g=0 ⇒ 精确归约)与 TV ≤ g 引理原样成立;`g≡0` 等价测试(SPRINT-03)无需重跑。
- 不引入 learnable 模块;φ 的函数形式与参数(0.70/0.10)由 legacy 预检数字预注册,生产数据产出后不得回调(否则即 FOLLOWUP-03 边界 6 所禁止的"救结果式重定义")。

### 7.3 U_ds 估计量(冻结)

对每个数据集的 regenerated train split(`paper_raw_v1`):采样 4000 条转移(seed=7);对每条,history 向量 = 生产 t5-xl bank 中有效历史物品 embedding 的归一化均值;U_ds = P(sim(h, next) > sim(h, neg)) 的均值,负例为 100 个**按训练集流行度采样**的物品(popularity 负例为主统计量,uniform 负例与 coherence 四分位分解作为诊断输出)。产物记录 bank hash 与 split hash。

### 7.4 Gate 0-v2 判据(冻结)

在生产 bank 上计算四数据集 U_ds 后,**同时满足**以下三条则通过:

1. `U_ds(ML1M)` 为四数据集最大值;
2. `φ(U_ds(ML1M)) ≤ 0.2`(即 U_ML1M ≥ 0.68,ML1M 的门基本关闭);
3. `φ(U_ds) ≥ 0.5` 在 {Steam, Beauty, ATG} 中至少两个成立(即 U ≤ 0.65,门在 v1 获益数据集上有效打开)。

- **通过** → 以 §7.2 门控重开 SPRINT-05;
- **不通过** → 生产数据与 legacy 预检矛盾,构念修复失败,于 **2026-07-07 前**出 Family D 降 claim 决定备忘(带数据),不再做第三轮门控修复。

### 7.5 论文叙事影响

若 Gate 0-v2 通过,主叙事从"证据贫自动回退"升级为"**content tilt 何时是 hard negative、何时是 false negative**":ML1M 保持被机制解释的反例地位,可证伪预测结构保留且更深一层。`paper/main.tex` 的 §3.2/3.3 门控公式与 §4.5 校准分析节随 FOLLOWUP-06 同步;命题与附录证明不动。

## 8. 修订 B(2026-07-04):Gate 0-v2 失败后的验证跑授权与 Family D 基线

- **状态**: 已获用户批准(2026-07-04)。
- **背景**: Gate 0-v2 按 §7.4 冻结判据 FAILED(条件 1/2 通过,条件 3 仅 Steam 达标;见 `docs/reports/data/2026-07-02-gate0/gate0_v2_frozen_verdict.md`)。生产 U_ds 与 v1 结果呈 4/4 完美逆序(Steam 0.570/+0.0064、ATG 0.688/+0.0019、Beauty 0.712/−0.0006、ML1M 0.754/−0.062),机制构念增强;失败源于 φ 阈值以绝对 AUC 单位从 legacy 尺度冻结的校准迁移错误。两点并存,如实入档。

### 8.1 Family D 基线(不变量)

Family D 是论文的**承诺基线**:2026-07-07 前冻结降级 claim 措辞(安全性定理 + v1 机制链 + U_ds 逆序分析 + 诚实边界)。后续任何证据只能通过有记录的修订**升级**措辞,不得回退该基线纪律。

### 8.2 用户授权的例外:冻结配置验证跑

用户于 2026-07-04 显式授权重开 SPRINT-05,**目的重定义为验证,不是门控修复**:

1. **零参数改动**:φ 冻结于 (0.70, 0.10),U_ds 用已归档产物(bank/split hash 对齐),g_max/k/τ0 不变。
2. **预注册预测**(以 `delta_test_p2_ndcg10` 对核心冻结基线):
   - ML1M 与 Beauty(φ=0 ⇒ g≡0):`|delta| < 0.01`(no-loss 端到端检查,兼命题 6 的实现保险);
   - ATG(φ=0.117):`|delta| < 0.01`(弱开门,不设方向);
   - Steam(φ=1.0):`delta > 0`,参考量级 ≥ +0.003(v1 的一半,保守)。
3. **结果只升不降**:四条全中 → Gate 2 出口可升级为"safety demonstrated end-to-end + selective gain"(有记录修订);ML1M/Beauty 平价失败 → 实现红灯,论文中命题 6 相关经验主张暂停,先查实现;Steam 无获益 → 维持纯 Family D 措辞。
4. 论文只呈现最终冻结系统;Gate 0 流程史留在项目文档。

### 8.3 两个离线补强分析(无训练,双路线通用)

1. **用户级效用-伤害分析**:在 ML1M(必做)与至少一个其他数据集上,用生产 bank 计算每用户 train-only 文本效用,与 v1-vs-core 的每用户表现差做数据集内相关;若逆序关系在用户尺度成立,机制主张从 4 点跨数据集证据升级为千点内部证据。
2. **corrupted-bank U_ds 响应**:在 Beauty 已冻结 corrupted bank(token dropout)上复算 U_ds 与 φ,展示门控对证据退化的响应方向;只报告观察,不据此改任何冻结参数。

### 8.4 修订 C(2026-07-04):ASO 第五数据集预注册规则(在看到 U_ds(ASO) 之前冻结)

服务器恢复后**第 0 步**:在生产 bank 上以 §7.3 冻结估计量计算 `U_ds(ASO)`(纯离线)。以下规则在数值产出前固定,产出后不得回调:

1. **预注册预测**(对任何后续 ASO 验证跑,按 φ 档位):`φ(U_ds(ASO)) ≥ 0.5` ⇒ 预测 `delta_test_p2_ndcg10 > 0`;`φ ∈ (0, 0.5)` ⇒ 预测小幅 |delta|;`φ = 0` ⇒ 预测 `|delta| < 0.01`(平价)。
2. **是否开跑**:`φ(U_ds(ASO)) > 0` 则 ASO 进入验证跑集合(开门数据点是当前最稀缺资源);`φ = 0` 则默认不跑(平价信息已有 ML1M/Beauty 两个位),仅将 U_ds(ASO) 记录为反转分析的第五个统计点。
3. **科学地位**:ASO 无第一代结果,因此它是**纯粹的 out-of-sample 预测点** — 表 1 的四个点在 φ 定型时已知结果,ASO 的结果在预测做出时不存在;这是它证据价值的来源,论文中应如此陈述。
4. 任何在看到 `U_ds(ASO)` 之后对本节阈值、预测或开跑规则的修改,均视为违反 §7.2 同款冻结纪律。


