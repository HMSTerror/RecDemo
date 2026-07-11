# PreferGrow 实验协议（提交前版本）

_PreferGrow AAAI-27；本协议用于把论文贡献映射到可复现实验，所有尚未运行的数值均不得填入结果段。_

---

## 📋 研究对象与主假设

研究对象是离散偏好扩散推荐中的 proposal-side reliability gate。冻结文本 bank 只参与 corruption proposal，不改 encoder、loss 或 guidance。主假设是：文本对真实 next item 越有预测性，proposal 越可能污染负例；因此 `U_ds`/`phi` 应在 train-only preflight 阶段决定是否打开 gate，并在 `g=0` 时精确回退 host kernel。

## ⚙️ 数据与划分

主数据集为 Steam、ML1M、Beauty、ATG；RISK-04/RISK-05 controlled-corruption pilot 仅覆盖 Beauty 与 Steam。每个数据集使用项目冻结的 train/validation/test split、item mapping 与 full-catalog evaluator。`U_ds` 只读 train transitions；model selection 只读 validation；开发期会记录 test metrics，论文必须披露 `model selection used validation only; test metrics were logged during development`，不得称 test 为 untouched final holdout。

立即执行阶段固定 `seed=100`，每个 dated root `max_attempts=1`、`failure_policy=fail_closed`、GPU1-only；三 seed（100/101/102）只在单 seed 证据闭环后另行运行。统计汇报规则为：单 seed 只能写 `single-run result/observation`，不得写 significant、stable、statistically equivalent 或 within noise。

## 🔬 实验族与控制

| 实验族 | 目的 | 对照/指标 | 运行状态 |
|---|---|---|---|
| E0 evaluator amendment | 统一尾批过滤与全方法重评 | host/ours/controls/DiffuRec；NDCG@10、HR@10、row count | 已完成，判据未翻转 |
| E1/R12 | 验证 `g=0` kernel/optimizer/checkpoint 路径 | host、final-v2、global-p 三路径；2986 comparisons | trace 已完成；非性能证据 |
| RISK-04/05 | 预注册 severe corruption 与 `phi_R` | clean vs Steam c60；EPE、mean gate、hash | 资产/门/协议已完成 |
| RISK-06/07 | 真实 Beauty/Steam host、anchor、full corruption pilot | 14 pass + 8 audit；e0_full_tail_v2 | r6 startup probe 后执行 |
| Classic baseline | 外部可比性 | SASRec 四域 atomic group；同 split/evaluator/selector | 未开始，投稿阻塞 |
| Attribution/robustness | 排除 gate/数据集/随机替代解释 | ATG global-p、u-shuffle、Steam severe | 未开始或只具前置资产 |
| Replication/uncertainty | 评估 seed dispersion 与 `U_ds` 精度 | 3 seeds；user-cluster bootstrap ≥1000 reps | 未完成 |

## 📐 统计与停止规则

主结果先保存每个 task 的原始 validation/test 文件、checkpoint、环境与 SHA-256；三 seed 后报告均值、标准差或 bootstrap CI，并以 user/task 为配对单位做 Wilcoxon signed-rank 或 permutation test，明确多重比较校正（Benjamini–Hochberg）。单 seed 阶段不做显著性检验。任何 hash、split、GPU、seed、selector、evaluator、`phi_R` 或 queue containment 不一致都硬停止，不得 retry 或 rescue tune。

## 🧾 证据分级

`artifact-proven` 仅表示 dated 文件与 hash 可核验；`single-run observation` 表示一次真实训练的方向性观测；`engineering contract` 表示单测、manifest、smoke 或 trace；`in-progress` 表示已启动但未完成；`not-started` 表示没有运行。只有完整四域、共同 evaluator、共同 selector、真实 task artifacts 和预注册统计汇总才能支撑跨数据集 efficacy 结论。
