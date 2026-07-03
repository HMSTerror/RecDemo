# Idea 08 — 效用定价的每模态 Guidance 权重(score 侧对偶)

- 目标会议:SIGIR 2027 | 层级:B
- 一句话:把 AAAI'27 的核侧门控搬到 **score/guidance 侧**:连续扩散推荐(DreamRec/DiffuRec/DualFashion 族)的每模态 classifier-free guidance 权重不再手调或学习,而由 train-only 的 U_ds^m 经冻结映射定价 — 并系统回答"kernel 侧 vs score 侧条件化,何时该用哪个"。

## 1. Gap

1. 扩散推荐的 guidance 权重现状:全局手调标量(DreamRec/PreferGrow 的 w)、或学习式自适应(A2G-DiffRec 2602.14706 用弱模型自引导,SIGIR'26;A-CFG 2505.20199 用模型自信度,LM 域)— **没有任何工作用外部证据统计量定价 guidance,更没有 per-modality 分解**;
2. 学习式/自信度式权重的通病:训练内闭环(模型信自己)⇒ 高效用假象无外部制衡 — 恰是我们反转律警告的盲区;
3. "同一个证据信号注入 kernel vs score 的系统对比"在文献中不存在 — 我们两边机制都有,是唯一能做这张表的组。

## 2. 方法核心

```text
score 侧:ŝ = s_uncond + Σ_m w_m·(s_cond^m − s_uncond),  w_m = w_max·φ(U_ds^m)·clip(ũ_m,0,1)
理论对照(论文骨架):kernel 门控 = 改数据分布(腐蚀律),score 门控 = 改估计器(采样时倾斜)
  → 前者有归约保证但影响训练目标;后者零训练成本但无 fallback 定理
  → 给出两侧在"高效用险区"的失效模式预测并实证:score 侧过引导 = 过度集中重排,kernel 侧 = 负例污染
```

## 3. 决定性实验

1. **外部定价 vs 学习定价**(核心):DreamRec 复现骨架上 {固定 w, A2G 式自适应, U_ds 定价} 三臂 × 4 数据集 — U_ds 定价必须在险区数据集(ML1M 型)显著更稳(不塌),甜区不输;
2. kernel-vs-score 对照表:同一 φ·ũ 信号两侧注入,按 U_ds 分区读结果 — 这张表本身就是论文核心贡献;
3. w-敏感性:U_ds 定价的 w 是否落在事后网格最优的平台内(复用敏感性脚本)。

## 4. 资产杠杆 / 风险

φ/ũ/U_ds 全复用;DreamRec 类骨架社区开源成熟。风险:A2G-DiffRec 同会前作压力 — 差异化必须钉死在"外部证据 vs 自引导"与 per-modality;若三臂实验中自适应基线全面更强,转投"对照研究"框架(kernel-vs-score 表仍然成立)。

## 5. 时间线

2026-10 决定性实验 → 2027-01 SIGIR 截稿(与 01 共享数据管线,错峰 GPU)。
