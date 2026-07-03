# Future Work 组合(多模态推荐 × 证据条件化)

- 生成日期:2026-07-04;文献扫描截至 2026-06(arXiv cs.IR,4 路检索 × 15-20 篇)
- 决策人:Claude(受托全权决定,无用户中途选择)
- 每个 idea 一个目录:`ideas/NN-slug/spec.md`(gap/方法/决定性实验)+ `issues.csv`(mission 账本,可直接执行)

## 0. 我们的可复用资产(所有 idea 的杠杆)

1. **Fallback-safe 门控核**(命题 1-6 + TV 界 + g≡0 等价套件):对任意合法 proposal 成立 → 换锚点/换模态零理论成本
2. **U_ds 效用统计量 + 反转发现**:"证据太好反而有害于腐蚀核"(4/4 逆序)→ 可迁移到任何负采样场景
3. **零点校准方法论**(长度匹配随机历史 null;几何地板 0.93-0.95 的教训)
4. **raw-data-first 协议 + 冻结 bank 管线**(t5-xl 文本 bank、SigLIP 图像管线残余、ASO/ATG 构建脚本)
5. **预注册纪律模板**(§7.4/§8.4 式冻结判据)— 每个 idea 的 spec 都内置

## 1. 文献扫描摘要(2025-2026 关键坐标)

**缺失/失衡/噪声模态(拥挤,全在判别侧)**:Meta-Modal Agent(2605.25007,RL 证据路由)、GRE-MC(2605.00670,图检索补全)、Malitesta 免训练插补(2602.17354,TKDE)、Single-Branch(2509.18807,TORS)、MMPCBench(2601.19750,MLLM 补内容基准)、REVEAL(2606.09082,视觉失衡)、CLEAR(2603.01536,零空间去冗余)、Trustworthy-MM(2602.00730,Sinkhorn 模态整流)。**空位:生成式/扩散核内部的缺失模态处理与保证。**

**扩散 × 推荐(热,但无人碰腐蚀律的模态条件化)**:DualFashion(2605.17357,SIGIR'26,图文双扩散生成)、JBM-Diff(2604.03654,图扩散去噪特征+反馈)、GTC(2604.03014,交互引导内容过滤)、MealRec(2603.01926,微视频分层扩散)、A2G-DiffRec(2602.14706,SIGIR'26,**自适应 autoguidance 权重** — 我们 score 侧最近邻)、StageCF(2605.05165,定制腐蚀过程 — 无模态、无证据定价)、FAVE(2604.04427,语义锚先验)。

**语义 ID / 生成式(工业热)**:RaG(2606.25496,SID 桥接推荐与视频生成)、SSRLive(2606.06970,多模态动态 SID)、MoToRec(2602.11062,RQ-VAE 稀疏 token 化)、SIDInspector(2606.10375,tokenizer 诊断)、TokenMinds/GR2/OneReason(用户 token/重排/推理)。**空位:codebook 学习对"腐蚀面效用"的感知。**

**MLLM/VLM**:ReasonRec(2606.28357,VLM agent + 不确定性委派)、VLM4Rec(2603.12625,图→文grounding)、PerPEFT(2602.09445)。**空位:MLLM 作离线证据审计员(校准输出、服务路径外、成本有界)。**

**基准资源**:Binge Watch **M3L-10M/20M**(2602.15505,MovieLens+海报/预告片/剧情)— 本组合多个 idea 的现成实验床。

## 2. 组合总表(12 个,按优先级分层)

| # | Idea | 一句话 | 目标会议 | 层 |
|---|---|---|---|---|
| 01 | m-usdpd-modality-gated-kernel | 每模态独立效用门控的 fallback-safe 多模态腐蚀核 | SIGIR'27 | **A** |
| 02 | modality-utility-atlas | 跨 20+ 数据集 × 编码器的模态效用地图 + 预检工具包 | RecSys'27/资源 | **A** |
| 03 | missing-modality-generative-kernel | 缺失模态下锚点可用性感知混合核,精确归约保证 | WWW'27 | **A** |
| 04 | mllm-evidence-auditor | MLLM 离线审计证据质量→校准分→蒸馏小校准器 | WSDM'28 | C |
| 05 | utility-aware-semantic-ids | 腐蚀面效用正则的多模态语义 ID codebook | KDD'27 | B |
| 06 | visual-onboarding-trust-ramp | 纯图像冷启动的证据信任爬坡(有界后悔) | RecSys'27 | C |
| 07 | null-calibrated-crossmodal-agreement | 跨模态一致性分数的零点校准(CLIPScore 地板问题) | CIKM'27 | C |
| 08 | utility-guided-multimodal-cfg | 由 train-only 效用定价的每模态 guidance 权重(score 侧对偶) | SIGIR'27 | B |
| 09 | corruption-routing-schedules | 时变模态锚路由的腐蚀调度(早期褪向流行、后期褪向语义) | NeurIPS'27 | C |
| 10 | fn-aware-contrastive-alignment | U_ds 定价的去偏对比对齐(多模态推荐对齐损失的 FN 修正) | WWW'27 | **A** |
| 11 | encoder-leakage-audit | 基础模型编码器记忆对多模态推荐基准的泄漏审计 | NeurIPS D&B'27 | B |
| 12 | unified-evidence-conditioning-theory | kernel/score/负采样三种证据条件化的统一估计量理论 | TMLR/ICLR'28 | C |

**层含义**:A = 直接兑现现有资产、12 个月内可成稿;B = 新领地但工具现成;C = 高风险/高新颖或偏理论,作组合期权。

## 3. 组合逻辑(为什么是这 12 个)

1. **一条主线**:全组合围绕"证据条件化生成式推荐"— 01/03/05/08/09 是方法轴,02/07/11 是测量轴,10/12 是外溢轴,04/06 是应用轴。互相引用,形成研究纲领而非散点。
2. **卡位判断**:缺失模态判别侧已红海(见 §1),我们只从生成核切入;guidance 自适应已被 A2G-DiffRec 占先手,我们用"证据统计量而非学习信号"差异化。
3. **AAAI'27 结果的三种延续**:若中 → 01 是直接续作;若 borderline → 10(把 U_ds 泛化到对比学习)是更大舞台的重述;若拒 → 02+11(测量与审计)不依赖方法胜负。
4. **执行顺序建议**:AAAI 投稿后立即启动 02(纯离线、无 GPU 竞争),9 月起 01 与 10 并行,其余按会议窗口错峰。

## 4. 使用方式

每个 `issues.csv` 兼容 mission-csv-execute 流程(与主账本同 schema);启动某个 idea 时把它交给执行器即可。spec 中的"决定性实验"是该 idea 的 Gate-0 等价物 — **先跑决定性实验,不过线就砍**,组合的意义就是让砍单个 idea 无痛。
