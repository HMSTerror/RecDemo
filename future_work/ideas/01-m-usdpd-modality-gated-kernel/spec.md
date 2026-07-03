# Idea 01 — M-USDPD:每模态效用门控的多模态 Fallback-Safe 腐蚀核

- 目标会议:SIGIR 2027(全文)| 层级:A | 依赖:AAAI'27 工作的直接续作
- 一句话:把单文本门控 `g = g_max·φ(U_ds)·clip(ũ,0,1)` 推广为**每模态独立门控向量**,proposal 变为多锚点凸组合,fallback-safe 性质逐字继承。

## 1. Gap(对着具体论文说)

1. 多模态扩散推荐(DualFashion 2605.17357、JBM-Diff 2604.03654、GTC 2604.03014、MealRec 2603.01926)全部把模态信号用于**特征去噪/生成/过滤**,没有一篇让模态证据进入**腐蚀律(转移核)**;
2. 模态加权工作(REVEAL 2606.09082、CLEAR 2603.01536、Trustworthy-MM 2602.00730)在表示/融合层做 reweighting/rectification,无安全保证、无"证据太好反而有害"的意识;
3. 我们 AAAI'27 已证明:文本效用 U_ds 与核倾斜收益 4/4 逆序。**未回答的自然问题:图像模态的 U_ds^img 是否服从同一反转律?两个模态的门是否应该独立开合?** 没有任何现有工作能提这个问题,因为没人有 per-modality 腐蚀核。

## 2. 方法核心

对模态集合 M = {text, image}(可扩展):

```text
p_u = p_core(⋆)·e_⋆ + (1−p_core(⋆))·[ (1−Σ_m g_m)·p̃_core + Σ_m g_m·c_h^m ]
g_m = g_max^m · φ(U_ds^m) · clip(ũ_m, 0, 1),   约束 Σ_m g_m ≤ g_total < 1
```

- 每模态独立锚点 `c_h^m`(冻结 bank:t5-xl 文本 / SigLIP 图像)、独立 null 校准 `ũ_m`、独立效用 `U_ds^m`;
- **理论零成本继承**:凸组合仍是合法 proposal,命题 1-6 与 TV ≤ Σg_m 逐字成立;g_m 全零 ⇒ 精确归约宿主核;
- 新理论增量:**模态间挤占引理** — 固定 g_total 下的最优模态分配与 (U_ds^m, 碰撞斜率) 的关系(rank-one 代数,2-3 行)。

## 3. 资产杠杆

核代码(graph_lib proposal 贯通)、null 管线、U_ds 估计器全部复用;图像侧只需 SigLIP bank 重建(`build_siglip_image_pickle.py` 残余管线)+ image 版 U_ds(估计器换 embedding 即可)。

## 4. 数据与指标

- 主:Amazon Beauty/ATG/ASO(图文双全)、**M3L-10M**(2602.15505,海报+剧情,检验 ML1M 家族的图像效用);Steam(图文)
- 指标:HR@10/NDCG@10 vs 宿主;每模态门控开合表;双模态 U_ds 矩阵

## 5. 决定性实验(Gate-0 等价,先跑先砍)

1. **图像反转检验**(纯离线,~1 天):四数据集算 U_ds^img,与文本版 v1/验证跑结果做秩相关 — 若图像效用与倾斜收益**不**呈负相关,反转律不跨模态,idea 降级为"文本核 + 图像消融"附录;
2. **模态门独立性**(2 天 GPU):Beauty 上 {text-only, img-only, both, both+shared-gate} 四臂 — both 必须 > max(single) 且 independent-gate > shared-gate,否则"每模态独立门"无卖点;
3. u-shuffle 双模态版必须掉点。

## 6. 风险与边界

- 图像 U_ds 在 Amazon 类目上可能极高(视觉同款→未来正例)⇒ 图像门恒关 ⇒ 论文变成"图像证据不可用于腐蚀核"的负结果 — **仍可发**(反转律的跨模态确认),但要在标题措辞里预留;
- SigLIP bank 重建成本(全量商品图下载)— 先用 M3L 现成特征打决定性实验 1。

## 7. 时间线

2026-08 决定性实验 → 2026-10 全矩阵 → 2027-01 SIGIR 截稿。
