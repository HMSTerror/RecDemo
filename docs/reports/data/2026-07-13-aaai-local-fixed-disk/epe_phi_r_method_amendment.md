# EPE/`phi_R` 方法修正备忘

日期：2026-07-13
状态：论文方法与证据链修正案；不授权新训练
适用范围：Beauty/Steam 的 r6a/r7 风险响应实验

## 修正结论

当前生产实验不是把旧 Gate-0 的 U_ds hinge 原样用于所有数据集。完整证据链包含三个层次：
U_ds 提供跨数据集的发现性观察；EPE/PNE@10 在冻结训练 transition 上测量 proposal 对已观察
下一正例的暴露；`phi_R` 则把条件级 EPE 风险按预注册公式映射为 Beauty/Steam 各 corruption
condition 的冻结干预强度。论文若把这三层都写成“U_ds gate”，就会错误描述 r6a/r7 的实际
运行方法，并掩盖方法从发现性统计量到前瞻干预合同的演化。

## 三层定义

Gate-0 的 U_ds 是 AUC 型训练前统计量：对冻结的 4,000 个训练 transition，每个 transition
使用 100 个 popularity negatives，估计文本相似度把真实下一物品排在负例之前的频率。四域
点估计为 Steam 0.569566、ATG 0.688263、Beauty 0.712428、ML1M 0.753539。它适合陈述为
train-only discovery statistic，不适合陈述为已经验证的总体预测律或 r7 的唯一门控变量。

RISK-03 把主要风险量定义为

\[
\operatorname{EPE}(h,y)=
\log\{q_{\text{text}}(y\mid h)+10^{-12}\}
-\log\{q_{\text{core}}(y)+10^{-12}\}.
\]

这里的 (y) 是冻结训练 transition 中已观察的下一正例。正 EPE 表示文本 proposal 相对宿主
proposal 给该正例分配了更多概率质量。它仍不是“所有未来正例的完整 false-negative rate”，
因此论文统一称其为 observed next-positive exposure proxy。PNE@10 把该正例与九个冻结文本
近邻的 proposal 质量相加，用于机制可视化与敏感性分析；padding 和 pseudo-item 均被排除。

预注册的条件级响应为

\[
\phi_R(D)=\operatorname{clip}
\left(
\frac{R_{100}-R_D}{R_{100}-R_{\mathrm{clean}}},0,1
\right),
\]

其中 (R_D) 是 condition (D) 的冻结 EPE，`clean` 与 `100` 分别是同一数据集的 clean 与
100% corruption 端点。生产用户门为

\[
g(h,D)=g_{\max}\,\phi_R(D)\,
\operatorname{clip}(\widetilde u(h;B_D,N_{\mathrm{clean}}),0,1).
\]

`u_tilde` 只读取用户历史；(B_D) 是 condition 对应的冻结文本 bank；
(N_{\mathrm{clean}}) 是冻结 clean-null calibration。null curve 不随 corrupted bank 重建，
因为本实验要在同一参考系下观察 evidence corruption 如何改变历史一致性。生产 argv 通过
`text_side.gate_dataset_scale_override=<phi_R>` 显式传入条件级响应，避免自动发现旧 U_ds
报告。

## 冻结数值与来源

| 数据集 | condition | EPE | PNE@10 | preflight mean gate | `phi_R` |
|---|---:|---:|---:|---:|---:|
| Beauty | c0 | 0.250996 | 0.00100327 | 0.307095 | 1.000000 |
| Beauty | c60 | 0.102031 | 0.000866649 | 0.129744 | 0.136631 |
| Beauty | c100 | 0.078456 | 0.000848254 | 0.096476 | 0.000000 |
| Steam | c0 | -0.010702 | 0.00117387 | 0.117306 | 1.000000 |
| Steam | c60 | -0.071506 | 0.00113354 | 0.085838 | 0.058081 |
| Steam | c100 | -0.075256 | 0.00114206 | 0.113407 | 0.000000 |

完整六级数值来自
`inputs/risk/risk_preflight_report.json`；冻结 `phi_R`、公式、风险抽样 seed 7、corruption
seed 100、`no_second_seed=true` 与 `no_rescue=true` 来自
`inputs/r7/protocol/risk05_preregistration.json`。该 preregistration 生成时间为
2026-07-11 14:25 +08:00，绑定 E1 pass marker SHA-256
`040afa9328e05ba6fcfb36b26ae561657236a0d0a033e97e9ceb7c9a40a2924c`。

## 生产实现对应关系

r7 的 `pilot_adapters.py` 为 anchor arm 显式设置
`gate_dataset_scale_override=1.0`，从而保证 `text_anchor_only` 不被数据集关门条件劫持；full
arm 把该 token 替换为 bank manifest 中的 `phi_R`。`text_side.py` 要求 full/u-shuffle 的
v2 kernel 同时具有 null curve 与唯一 gate source，并拒绝 override 与旧 text-utility report
同时存在。门值由 `g_max * gate_dataset_scale * gate_user_factor` 构成，full arm 的用户因子为
`clip(u_tilde,0,1)`，anchor arm 的两个因子均强制为 1。

当 `phi_R=0` 时，生产代码的 `closed_gate` 分支直接返回 `p_core`。因此 c100 的正确陈述是：

> 在预注册 `phi_R=0` 下，生产训练路径的 selected best-summary 与 host 字节级相同；
> checkpoint 因包含 text-side builder 状态而不同。

不得再写“全腐蚀使 `u_tilde` 自动塌缩到零”。preflight 中 Beauty c100 的 mean `u_tilde`
约为 0.0123，Steam c100 约为 0.0685；更关键的是，生产关门在用户因子产生性能作用之前就由
显式 `phi_R=0` 决定。

## 实现边界与未闭合风险

r7 adapter 把 clean-null policy、null path、null SHA-256 和 clean source-bank SHA-256 写入
任务环境与 artifact provenance；`TextSideProposalBuilder.from_files` 本身只读取 null JSON，
没有在模型加载点重新计算并比对 SHA-256。论文可以陈述“运行合同绑定了 clean-null
provenance”，但不能把它扩大为“模型加载函数独立执行了 null hash 验证”。后续发布版应把该
校验下沉到 loader；本周期不因此重解释已经冻结的 r7。

r6a 的八个 full/host best-summary 可说明 argv 与数值链条能运行，但该 root 缺少原 RISK-08
要求的完整 artifact/log 合同，因此只属于 provenance-limited single-run snapshot。r7 的
14-task atomic output 与原始 RISK-08 terminal 才能进入 confirmatory paper table。

## 论文允许与禁止措辞

允许：U_ds 提供四个观测数据集上的 train-only descriptive discovery；EPE 是 observed
next-positive exposure proxy；`phi_R` 是在 pilot 前冻结的 condition-level intervention；
Beauty/Steam r7 使用 EPE/`phi_R` 合同；`g=0` 的保证限于 proposal/kernel 对象和指定生产
trace scope。

禁止：U_ds 是普适预测器；r7 直接使用旧 U_ds hinge；EPE 是完整 false-negative rate；
c100 证明模型学会自适应回退；`u_tilde` 在 c100 必然为零；kernel TV bound 是端到端 NDCG
下行界；单 seed 结果具有显著性、稳定性或统计等价性。
