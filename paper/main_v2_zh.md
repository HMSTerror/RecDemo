# 当更强的文本证据反而有害:离散偏好扩散核的 Fallback-Safe 条件化(中文对照版 v2)

> 本文件是 `paper/main_v2.tex` 的中文对照,供作者审阅;英文版为投稿母本。2026-07-12 dated amendment 已把 legacy `U_ds`、RISK-03 EPE/PNE@10 与 r6a/r7 `phi_R` 三代证据分开；任何后续 r7 数字只能在同根 14-task 工件与不可变 RISK-08 出口生成后回填。
> 2026-07-08 同步注记:英文版已做去 AI 化风格重构(29 处标点/句构调整:破折号插入语改冒号/括号/分号、-ing 尾挂改限定动词;冻结句原样保留;语义与数字零变化,已通过必需短语与禁写清单扫描)。中文对照的语义与英文版保持一致,中文破折号为合法标点不在调整范围。

## 摘要

PreferGrow 一类离散偏好扩散推荐器把用户偏好物品向一个 **proposal 分布**褪色腐蚀,再学习把偏好长回来。该家族的个性化完全作用在 score 侧,转移核由所有用户共享。我们对核做个性化,并揭示一个反直觉现象:因为 proposal 本身是腐蚀分布,文本证据可能“好到不能直接用”。一个 legacy、train-only 的下一物品文本效用统计量,在归档测量尺度上与第一代文本倾斜结果呈描述性 4/4 逆序；尾批修正后的共同 evaluator 由于 Beauty 与 ATG 相邻互换,严格排序降为 3/4。因此它是 discovery signal,不是总体规律。我们进一步用 train-only 的 observed-next-positive exposure（EPE/PNE@10）直接测量所提机制,并用两因子、history-only 门 `g=g_max·s_D·clip(ũ,0,1)` 在宿主学到的 proposal 与冻结文本锚点之间插值。数据集尺度 `s_D` 随证据代际声明:legacy 四域铰链与 dated controlled-corruption `phi_R` 分开报告。fallback 保证严格限于核级:`g=0` 时精确归约到宿主；非零门下仅有 `TV(p_u,p_core)≤g` 与单步前向转移行 `TV≤(1−α_σ)g`,不构成端到端性能界。修复 optimizer ownership 后,版本绑定的 E1/R12 在指定路径完成 2,986 项比较且 0 失败,但未测试 standalone checkpoint replay 或指标等价。seed-100 controlled-corruption precursor 中,Steam c60 的 validation/test NDCG@10 同向；Beauty 的正差只出现在 test；c100 在显式 `phi_R=0` 下恢复宿主 best-summary。anchor 工件缺失且用户级不确定性不可估,因此本文不作 efficacy 主张或多次运行可靠性判断。本文贡献是可靠性审计与核级安全构造,不是一致性能提升。

## 1. 引言(2026-07-08 与英文版同步重写)

扩散式推荐器把单步预测替换为迭代的"腐蚀-重建"过程。在离散实例化中——物品词表上的偏好褪色与生长(PreferGrow),建立在结构化离散核(D3PM)与 score-entropy 训练(SEDD)之上——腐蚀直接作用于被排序的对象本身:前向核把偏好物品向一个**proposal 分布**褪色,反向过程在学到的 score 模型下把偏好长回来。

Proposal 分布是这个家族的中心对象。它编码"褪色的偏好由什么顶替",并经由这个选择决定前向链的平稳分布、细致平衡的参考测度、score-entropy 目标的权重、以及解析反演比率。然而现有离散偏好扩散中 proposal 是**全局的**:所有用户共享一个核,个性化只通过 score 网络与推理期对"非偏好用户"分支的引导进入(PreferGrow)。与此同时,物品文本——关于物品最丰富的外部证据——在序列推荐的**表示侧**被常规使用(RecFormer/UniSRec),连续扩散推荐器则把条件放在去噪器或引导信号上(DreamRec/PreferDiff/DiffuRec)。**腐蚀核本身始终无人条件化。**

让腐蚀**自适应化**如今是生成式推荐的活跃纲领:掩码扩散下的语义 ID 并行解码(LLaDA-Rec)、置信度排序的任意顺序解码(DiffGRM)、由"均匀掩码有害"驱动的位置自适应掩码调度(arXiv:2601.19501),理论分析开始跟进(arXiv:2511.23021),底层是离散扩散语言模型纲领(LLaDA)。但这一浪潮自适应的对象是**模型内生**信号——置信度与位置启发式。对**外部**证据而言缺两样东西:一个训练可算的、决定证据是否应被允许塑造腐蚀的判据;以及证据误导时对塑造后过程的保证。本文就是对这两样东西的预注册可靠性研究,选在能把问题提得最干净的最简核家族上。

直觉给出单调规则:文本证据越好,核越该倚重它。**我们的中心实证发现挑战了这一规则。**Proposal 是腐蚀分布——它偏爱的物品被当作“偏好褪色时去的地方”,即负例。若文本相似度把用户**真实的下一物品**排到前面,文本倾斜就会把腐蚀质量集中到可能的未来正例上。Legacy train-only 统计量 `U_ds`（文本相似度区分下一物品与流行度采样负例的 AUC）在归档四域尺度上与第一代倾斜结果呈描述性 4/4 逆序；修正后的共同 evaluator 保留 Steam/ML1M 端点对比,但交换 Beauty/ATG 的相邻位置,因此严格排序为 3/4。我们将其视为需要直接机制测量的发现,而非四域总体规律。

这一发现导出 **fallback-safe 证据条件化**。广义低容量门为 `g=g_max·s_D·clip(ũ,0,1)`:用户因子 `ũ` 由长度匹配随机历史零点校准且只依赖历史；冻结数据集尺度 `s_D` 必须声明自己的证据代际。Legacy 四域研究使用 `phi_U(U_ds)`；RISK-03 以 EPE/PNE@10 测量文本 proposal 对已观察下一正例及其文本邻域的暴露；dated Beauty/Steam controlled-corruption pilot 则使用不同的 `phi_R`。冻结的 `phi_R` 随 EPE 增大,所以只能解释为 evidence-retention/corruption-reliability scale,不能证明“高 EPE 自动关门”。门控核在宿主**学到的**全局 proposal 与冻结文本锚点之间插值,伪物品质量不动。给定固定历史信号,`g=0` 时 proposal 与派生核对象精确归约到宿主；非零门下只约束 proposal 与单步前向转移行的 TV。Legacy 四域验证与 controlled-corruption precursor 是两代证据,均不构成一致 gate efficacy 或端到端归约证明。

**四条贡献**:① legacy `U_ds` 效用逆序 discovery 与直接 EPE/PNE@10 exposure audit；归档尺度为 4/4,修正共同 evaluator 为 3/4,`1/24` 仅是 exchangeability 假设下某一指定全序的描述性比例；②核侧个性化的 fallback 保证严格限于 `g=0` 精确归约及 proposal/单步前向转移行 TV 界；③把随机历史零点校准、legacy discovery、直接 exposure measurement 与 frozen controlled-corruption intervention 分代版本化,不在看到结果后修改 `phi_R` 的符号或数值；④有边界的机制证据:所有 seed-100 数字只称 single-run observation,anchor 缺口和不可估用户级不确定性保留为 limitation。

## 2. 预备:离散偏好扩散

词表 Ω(M+1 态含伪物品 ⋆),行向量约定。秩一核 Π_p(i,j)=p(j),生成元 Q_p=Π_p−I,前向转移 P_{σ,p}=e^{σQ_p}=αI+(1−α)Π_p(α=e^{−σ}):偏好以概率 α 存活,否则从 p 重采样——**偏好向 proposal 褪色**。score 模型以去噪 score entropy(SEDD)训练;反演用解析平稳反演比率,proposal 以闭式出现。宿主的 proposal 是可学习的:p_core=softmax(p1)。以下只改 proposal,其余全部固定。

## 3. 方法:Fallback-Safe 门控 Proposal

**[图 1 位已预留(fig:method)]** 方法总览图:冻结文本 bank → 内容锚点 `c_h`;广义门 `g=g_max·s_D·clip(ũ,0,1)` 在宿主 `p_core` 与锚点间插值；`s_D` 分别标注 legacy `phi_U(U_ds)` 与 controlled `phi_R` 两种实例。边界只标 `g=0` 精确归约、proposal TV `≤g`、单步前向转移行 TV `≤(1−α_σ)g`,不作 NDCG 或完整轨迹保证。

**3.1 证据锚点**:每数据集一个冻结文本 bank(题名/品牌/类目/描述),现成编码器一次性嵌入、不微调。历史均值向量 ē_h 定义内容锚点 c_h(i) ∝ exp(⟨ē_h, e_i⟩/τ0),缺文本物品降权。锚点提出**内容上说得通的替代物**,从不替换宿主的 score 表征。

**3.2 用户因子:零点校准连贯性**:原始连贯性 A_h 有高且数据集相关的地板(生产 bank 上随机伪历史已得 0.931-0.942)。对每个数据集和历史长度 L 用冻结 bank 抽随机伪历史,记录 μ_null(L)、σ_null(L),定义 ũ=(A_h−μ_null(L))/(k·σ_null(L))。ũ 是 history-only 且沿轨迹固定。**零点校准必要但不充分**:校准后的连贯性度量"行为是否在文本空间聚簇",不度量"把腐蚀倾向该簇是否有益"——生产 bank 上中位 ũ 排序 ML1M(1.43)>Beauty(0.80)>ATG(0.72)>Steam(0.11),与倾斜真正有益的地方**几乎相反**。这正是需要第二个效用导向因子的原因。

**3.3 数据集证据:发现、测量与干预**。第一,legacy `U_ds` 是 train-only popularity-negative AUC:锚点相似度把已观察下一物品排在流行度采样负例之上的概率。原四域实例使用 `phi_U(U_ds)=clip((0.70−U_ds)/0.10,0,1)`；阈值在 production statistic 计算前冻结,事后未调。它是 discovery descriptor,不是 r6a/r7 当前 gate 的同义词。

第二,RISK-03 定义 `EPE_{D,c}=mean[log(q_text,c(y|h)+epsilon)−log(q_core(y)+epsilon)]`,并把 PNE@10 定义为冻结十物品文本邻域上的平均 text-proposal mass。两者都是 train-only observed-next-positive exposure proxy；不是完整 false-negative rate、不是端到端指标,且冻结 records 缺 user ID,无法执行用户级 bootstrap。

第三,Beauty/Steam controlled-corruption pilot 冻结 `phi_R(D,c)=clip((R_D,100−R_D,c)/(R_D,100−R_D,0),0,1)`,其中 `R=EPE`。两域均满足 `R_c0>R_c100`,因此实现映射随 EPE **增加**:clean scale 为 1,c100 为 0。本文保留该预注册符号与数值,把它限定为 evidence-retention/corruption-reliability intervention；不宣称它验证了“高 positive exposure 自动抑制 gate”。以下用 `s_D` 表示已声明的冻结尺度,两代结果不合并。

**3.4 门控核**:`p_u=p_core(⋆)e_⋆+(1−p_core(⋆))[(1−g)·renorm(p_core)+g·c_h]`,`g=g_max·s_D·clip(ũ,0,1)`。三个刻意限制:①伪物品质量精确取宿主值,门不碰；②`g` 是唯一旋钮,无证据依赖的温度或流行度混合；③无新可学习模块。`p_u` 替换**每一个**核级对象里的全局 proposal:前向腐蚀、score-entropy 权重、解析反演比率,不只是负采样。

**3.5 理论**(证明在附录；固定 `h` ⇒ `ũ`、声明的 `s_D` 与 `p_u` 沿轨迹固定):
- **命题 1(核有效性)**:前向腐蚀闭式 q_t(x|x0,u)=ᾱ_t·1{x=x0}+(1−ᾱ_t)p_u(x);条件马氏;平稳/极限分布为 p_u;对 p_u 细致平衡;解析反演=宿主公式换 proposal 项。
- **命题 2(精确归约/fallback 安全)**:g=0 ⇒ p_u=p_core ⇒ 一切导出对象与宿主核**逐一相等**。
- **引理 1(有界偏离)**:TV(p_u,p_core)≤g;前向转移每行 TV ≤ (1−α_σ)g。
- **注记(为什么核是正确的注入位置)**:encoder/loss 级注入不存在命题 2 的类比——"零可靠性下带文本特征的 encoder"没有"就是宿主模型"的意义。归约保证只在条件化进入转移律本身时可表达。注入位置对比因此是 regime 分析,不是安全主张的依据。
该界只约束 proposal 与单步转移行的核级分布差异,不约束训练后的 loss、NDCG 或完整轨迹差异。

## 4. 效用逆序分析(论文中心展品)

**[图 2 位已预留(fig:inversion)]** 发现与机制图:左半(低 legacy `U_ds`)文本相邻物品可充当困难负例；右半(高 `U_ds`)文本可能暴露下一正例。图中把 legacy `phi_U` 与 controlled `phi_R` 画成两条不同证据支路,禁止把后者画成前者的验证。

**表 1（legacy 尺度冻结数字）**:

| 数据集 | U_ds | φ(U_ds) | Δ NDCG@10(无 φ,第一代) |
|---|---|---|---|
| Steam | 0.570 | 1.000 | +0.0064 |
| ATG | 0.688 | 0.117 | +0.0019 |
| Beauty | 0.712 | 0.000 | −0.0006 |
| ML1M | 0.754 | 0.000 | −0.0622 |

三个读法:①归档尺度上的指定排序为 4/4；E0 修正共同 evaluator 后 Beauty/ATG 相邻互换,严格排序为 3/4,Steam/ML1M 端点不变。若在 exchangeability 假设下把 `4!` 种标签全序视为等可能,某一指定全序对应的 `1/24` 只是描述性组合计算,不是确认性 p 值；ATG 的 legacy `phi_U=0.117` 始终称 barely-open。②逆序对连贯性不可见。③流行度解释不了 legacy 信号（uniform 负例变体给出相同排序 0.799/0.692/0.717/0.565）。

**命题 3(目标碰撞随锚点效用增长)**:前向腐蚀把褪色偏好重定位到真实下一物品 y 的概率 = (1−ᾱ_t)p_u(y),对 g 仿射且当 c_h(y)>p̃_core(y) 时严格递增;对用户平均后斜率为 E_h[c_h(y_h)−p̃_core(y_h)]——U_ds 的质量形式类比。碰撞质量是通道而非终指标伤害的证明(score 模型可部分补偿);表 1 是经验仲裁。

**Legacy 铰链稳健性**:92 网格点扫描中 65% 保持两条冻结定性结论；预注册点 `(0.70,0.10)` 落在平台内。该报告只解释归档第一代尺度,不能覆盖 E0 修正排序或 controlled `phi_R`。

**用户级读出(诚实负结果)**:用户级逆序**不复现**——ML1M ρ=0.028(n=4832)、Steam ρ=0.046(n=31836),弱且非负;逆序主张保持在数据集级,不升级为用户级规律。

**腐蚀 bank 门响应(观察性)**:冻结 Beauty token-dropout bank 上,U_ds 随 dropout 单调下降(0.7133→0.7044)但全程高于 0.70 关断线,φ 恒为 0;相对干净 bank(0.7124)最轻腐蚀点略高(+0.0008)——仅记录为观察证据,不构成单调律,不支持任何冻结参数更新。

**纯 out-of-sample 检验(诚实 MISS)**:ASO 在四点表**之后**冻结、按预注册规则评估:U_ds=0.538、φ=1.0,冻结预测 Δ>0;实测 **−0.0108,预测未中**。如实记录为 out-of-sample miss,不作为升级门控主张的支持。

## 5. 实验

**设置**:四基准(Steam/ML1M/Beauty/ATG)从原始数据按冻结协议重建,row-level split 统计固定为 Steam `9265 / 988517 / 81695 / 80651`、ML1M `3706 / 755782 / 98622 / 85405`、Beauty `12101 / 17890 / 2236 / 2237`、ATG `11921 / 15529 / 1941 / 1942`。指标为 HR@10/NDCG@10。模型选择只使用 validation；test metrics 在开发过程中被记录,因此不称 test 为 untouched final holdout。宿主是冻结 PreferGrow run set。唯一 confirmatory 外部参照是最小 SASRec（seed=100,四域 atomic group）,使用共同 mappings/splits、full-catalog evaluator 与相同 validation selector。DiffuRec 从 confirmatory comparison 排除,只保留为 related work 和 evaluator-audit provenance。E0 只修正共同 full-tail、row-weighted、real-item test contract,没有重新选择 legacy validation checkpoint；表 2 本周期整体保留 legacy 尺度,禁止选择性换数。

**SASRec 四域共同协议参照（seed=100 single-run observation）**:

| 数据集 | best epoch | validation NDCG@10 | test NDCG@10 |
|---|---:|---:|---:|
| Steam | 10 | 0.043570 | 0.046416 |
| ML1M | 10 | 0.137651 | 0.121677 |
| Beauty | 4 | 0.011383 | 0.002680 |
| ATG | 3 | 0.010644 | 0.009062 |

SASRec 在 Steam/ML1M 明显高于冻结宿主,在 Beauty/ATG 较弱。Beauty 从 validation 到 test 的大幅下降仍未解释,不得据此宣称 PreferGrow 优越。这一表只提供一个外部架构锚点；baseline 覆盖仍薄,不作跨模型显著性主张。

**5.1 Legacy 冻结门四数据集验证（表 2,整体 legacy 尺度,test NDCG@10,p2 选择器,单种子）**:

| 数据集(φ) | 宿主 | 本文 | Δ | 对照预注册预测 |
|---|---|---|---|---|
| Steam(1.00) | 0.0129 | 0.0149 | +0.0020 | 方向 ✓,量级 ×(参考 ≥+0.003) |
| ATG(0.12) | 0.0419 | 0.0305 | −0.0114 | barely-open（勉强开门）平价 × |
| Beauty(0.00) | 0.0333 | 0.0294 | −0.0039 | 平价 ✓ |
| ML1M(0.00) | 0.0910 | 0.0759 | −0.0151 | 平价 × |

**判读(混合结果,如实报告)**:全开 Steam 保持正号但未达参考量级,关门 Beauty 守住平价带。关门 ML1M 的单次运行 miss 超过测得的宿主噪声地板;barely-open ATG（`φ=0.117`）的单次运行 miss 为 provenance-limited 三次运行观测 spread 的 4.37 倍,但三次运行均缺冻结 manifest,不能据此声称配置仅有 seed 不同或把 spread 当作完整 manifest 支撑的噪声地板。E0 修正后的共同测试契约没有翻转这两个 miss。初次 E1 生产路径 trace 在 step 0 发现 canonical core proposal 参数的 optimizer ownership 不同；修复 optimizer/EMA ownership 后，版本绑定的 R12 在 steps 0、1、100、1000 共 2,986 项比较中 0 项失败。R12 只覆盖指定内存路径，不证明推荐指标等价或 standalone checkpoint replay；E2 归因对照本轮仍未完成。命题 2 约束 `g=0` 时的核对象,不单独认证完整训练、选择和评估实现相同。本文报告的是“一个关门实现 miss 加一个 barely-open ATG miss”,两者均作为开放实现问题;不声称精确归约已被端到端经验演示。

**5.2 RISK-03 observed-next-positive exposure audit**:

| 数据集 | bank | EPE | PNE@10 | `phi_R` |
|---|---|---:|---:|---:|
| Beauty | c0 | 0.250996 | 0.001003 | 1.000000 |
| Beauty | c60 | 0.102031 | 0.000867 | 0.136631 |
| Beauty | c100 | 0.078456 | 0.000848 | 0.000000 |
| Steam | c0 | -0.010702 | 0.001174 | 1.000000 |
| Steam | c60 | -0.071506 | 0.001134 | 0.058081 |
| Steam | c100 | -0.075256 | 0.001142 | 0.000000 |

正 EPE 表示文本 proposal 对已观察下一正例分配的 log mass 高于冻结 core proposal；PNE@10 给出其文本邻域质量视角。两者都不是推荐指标。E7 因 transition records 缺 user ID 而 `not_estimable`；请求配置为 1000,实际执行 bootstrap 为 **0**。`phi_R` 是冻结的 evidence-retention intervention,不是对这些结果拟合出的响应。

**5.3 r6a controlled-corruption precursor（seed=100 single-run observations）**:

| 数据集 | arm | `phi_R` | val NDCG@10 | `Delta`val | test NDCG@10 | `Delta`test |
|---|---|---:|---:|---:|---:|---:|
| Beauty | host | — | 0.022175 | — | 0.038195 | — |
| Beauty | full c0 | 1.000000 | 0.022174 | -0.000002 | 0.039851 | +0.001656 |
| Beauty | full c60 | 0.136631 | 0.022212 | +0.000037 | 0.039824 | +0.001629 |
| Beauty | full c100 | 0.000000 | 0.022175 | 0.000000 | 0.038195 | 0.000000 |
| Steam | host | — | 0.013720 | — | 0.012234 | — |
| Steam | full c0 | 1.000000 | 0.014807 | +0.001087 | 0.013752 | +0.001519 |
| Steam | full c60 | 0.058081 | 0.016339 | +0.002619 | 0.015107 | +0.002874 |
| Steam | full c100 | 0.000000 | 0.013720 | 0.000000 | 0.012234 | 0.000000 |

Beauty c0/c60 的 validation delta 约为零,正差只出现在 test；因此任何表格都必须把 val/test 并列。Steam c60 是目前最强的非平凡方向性观察,因为 validation 与 test 同向。模型选择只使用 validation；test metrics 在开发过程中被记录。c100 是**显式 `phi_R=0`** 的 production fallback sanity check:Beauty 与 Steam 的 selected best-summary 均与 matched host 字节级相同,但 checkpoint 因 full arm 序列化额外 text-side state 而不同。它不是 `u_tilde` 自动塌缩,不是自适应用户级 backoff,也不是非平凡 efficacy 点。

r6a 缺每臂 `artifact_manifest.json`,run-local logs 为空,六个 anchor 在训练前 fail closed,且没有 RISK-08 出口；不能拼接六臂补跑来事后满足同根 14-task 合同。修复后的 r7 必须原子重跑 14 个 active tasks。在不可变 RISK-08 工件产生前,正文不填任何 r7 性能或 PASS。

**5.4 对照与机制证据(第一代实例化,Beauty token-dropout 语境)**:表 3 冻结数字——aligned 门控 0.0393 / 无门锚点 0.0366 / u-shuffle 0.0206 / global-p 0.0289(test NDCG@10)。对齐门控是承重的(shuffle 降至 0.0206),通用偏置也不能复现该结果(global-p 仅 0.0289)。描述置空时可靠性均值变化 −0.0134,token dropout 同向变化 −0.0031;门控第一代变体从干净到腐蚀的变化为 −0.0008,无门锚点为 −0.0043。这些只作为第一代腐蚀响应记录,不构成 final-v2 腐蚀响应证据。本周期没有可用的预注册 E3 full-arm 结果：一个 dated queue attempt 在任何 full arm 启动前因资产/协议检查失败而 fail closed。冻结两因子门的 clean-root v2 对照臂把“关门平价”和“开门机制”分开了: 对 Beauty,由于 $\phi(U_{ds})=0$, `global_p` 与 full 在 test NDCG@10 上数值完全相同(均 0.0294),`u-shuffle` 也未使其下降(0.0330),与数据集级门保持关闭一致;对 Steam,由于 $\phi(U_{ds})=1$,打乱用户可靠性信号会让 test NDCG@10 相对 full 下降 0.0011,而 `global_p` 仅比宿主高 0.00035 且仍低于 full,因此 full 的微弱正增益不能用数据集无关的通用偏置单独解释。`text_anchor_only` 只作为高方差参考对照报告,不当作门控方法的替代:它在 Steam 上升到 0.0302,在 Beauty 上则略低于 full。**[图待生成:第一代腐蚀响应图]**

**5.5 注入位置分析(限定表述)**:相同信号注入三个位置(encoder/loss/kernel)。第一代跑中,较早注入位置在干净 regime 有竞争力,核侧条件化在腐蚀下最强;**作为限定于该实例化的 regime 观察报告,不主张核位置一贯获胜**。按注记,核位置的论点不是全 regime 取胜,而是唯一能表达 fallback 保证的位置。*(v2 三方重跑已于 2026-07-06 剪枝取消;不做跨位置优越性主张。)*

## 6. 从门到调度(新增讨论节,零经验主张)

我们的门沿腐蚀轨迹是**常数**乘子:同一个 g 作用于每个噪声档。上述验证结果——开门数据集保号但未达参考量级、ASO 纯 out-of-sample 未中——与"常数门是过钝的执行器"相容:把腐蚀向内容倾斜的价值,在轻腐蚀(褪色物品几乎可恢复)与重腐蚀(proposal 支配状态分布)之间很可能不同。一个简单的代数事实使时变扩展是良定义的:形如 αI+(1−α)Π_p 的转移在 proposal **各不相同**时的乘积仍保持同一形式,有效 proposal 是路径上各步 proposal 的显式凸组合。因此闭式边缘、score-entropy 权重与归约性质在调度依赖的门控下**幸存**,而效用统计量 U_ds 自然成为**腐蚀调度**而非标量门的定价。以与本文相同的预注册纪律发展这一证据定价调度族,是本工作的直接延续。

## 7. 相关工作(五轴)

①**扩散推荐器**(连续:DreamRec/DiffuRec/PreferDiff;离散:PreferGrow/LLaDA-Rec;我们补宿主的核侧一半);②**[新增]离散扩散 LM 与生成式推荐的自适应腐蚀**(LLaDA/SEDD 底座;LLaDA-Rec 并行 SID、DiffGRM 置信度任意序解码、2601.19501 位置自适应掩码、2511.23021 分析——它们自适应于模型内生信号,无外部证据定价、无误导信号下的归约保证;本文是互补且警示性的:第一份预注册证据表明证据塑造腐蚀的价值会随证据质量**倒置**,并给出训练前定价统计量,以及具有 `g=0` 精确归约和 proposal/单步转移行 TV 界的条件化构造——我们视之为自适应腐蚀推荐器将需要的**可靠性层**);③**塑形转移核**(D3PM/CDRec/TDPM:全局或物品级信号,无按用户证据条件化、无归约保证、无效用逆序报告);④**Guidance 与自适应**(CFG 及其推荐应用、语言扩散的置信度自适应 guidance:score 侧全局权重;我们是核侧类比,权重由可测的 history-only 证据统计量设定,插值目标是宿主可学习 proposal——这正是精确归约与上述核级 TV 界可证的原因);⑤**推荐中的可靠性与侧信息 / 负采样中的假负例**(UGR/TruthSR、RecFormer/UniSRec;对比学习与隐式 CF 中的 FN 文献:我们把该失败模式搬运到扩散**核**——"负采样器"就是转移律本身,与平稳分布、细致平衡、训练目标纠缠——并提供训练前定价统计量 U_ds)。

## 8. 结论与限制

我们以两因子 history-only 证据门对离散偏好扩散的转移核做个性化,并把 formal guarantee 精确限定为:`g=0` 核对象归约、proposal TV 至多 `g`、单步前向转移行 TV 至多 `(1−alpha_sigma)g`。Legacy `U_ds` 是 train-only rank descriptor；EPE/PNE@10 直接审计 observed next-positive exposure；冻结数据集尺度按证据代际版本化,不冒充一个已被普遍验证的风险门。本文不作端到端性能下行保证或四域一致提升主张。

**限制(如实)**:跨数据集发现只有四个 aggregate 点；4/4 只属于归档尺度,修正共同 evaluator 为 3/4,`1/24` 只是描述性组合计算。用户级读出不复现该逆序。Legacy 冻结门验证仍含 ML1M closed-gate miss 与 barely-open ATG miss；E1/R12 只覆盖指定 revision/in-memory path,E2 未完成。Controlled `phi_R` 随 EPE 增大,所以它是 evidence-retention scale,不是“高 EPE 自动关门”的证据。r6a 仅有单 seed precursor:Steam c60 的 val/test 同向,Beauty 正差为 test-only,explicit-zero c100 仅是 fallback sanity check；缺 anchors、manifests、非空 run logs 与 RISK-08 出口阻止 efficacy claim。E7 因 user ID 缺失实际执行 0 次 bootstrap。SASRec 只有一个外部架构,Beauty validation-to-test drop 未解释。test metrics 在开发过程中被记录,所以这些 readout 都不是 untouched final holdout。理论保证仍限于平稳 proposal 下的核对象。

## 附录(骨架,CLOSE-07 从冻结稿合并全文)

A 证明(秩一代数/闭式/细致平衡/反演/碰撞恒等式)| B 范围与边界条件(history-only、自重采样腐蚀、伪物品坐标)| C legacy `U_ds` 与 `phi_U` 预注册| D 第一代实例化| E 实现与基建（同时记录 controlled `phi_R` 为 Beauty `1/0.136631/0`、Steam `1/0.058081/0`；r6a provenance 例外；E7 请求 1000、实跑 0、`not_estimable`；模型选择仅使用验证集,开发过程中记录 test metrics）| F 负结果(metadata-sparsity)

---

### 与英文版的占位符对账(提交前必须清零)

| 占位符 | 责任行 | 期限 |
|---|---|---|
| 数据集统计表 | CLOSE-07 | 7/27 |
| 外部 baseline 表 | 已由 E5 SASRec 四域 atomic group 回填；Beauty anomaly 保留 | 已完成 |
| 宿主噪声地板+红灯归因措辞 | CLOSE-02 | 7/13 |
| v2 对照臂表(SPRINT-07) | CLOSE-01 | 7/12 |
| 回退机制图 | CLOSE-07 | 7/27 |
| 附录全文合并(A/B/D/F)+ bib 元数据核实 | CLOSE-07 | 7/27 |
| Gate-2 定稿措辞(升级句启用与否) | CLOSE-05 | 7/14 |
