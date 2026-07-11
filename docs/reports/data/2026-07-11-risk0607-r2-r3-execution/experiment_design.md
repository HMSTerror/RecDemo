# AAAI 实验路线与 l20 实际执行边界（seed=100）

## 研究目标

本轮先建立可审计的单种子 evidence chain：修正 evaluator 尾批、固定 validation-only selector、验证 E1 implementation amendment，并在同一 split、item mapping、evaluator 和 selector 下运行 PreferGrow 的 host 与 proposal arms。单 seed 只能写作 `single-run observation`；任何显著性、稳定性、统计等价或 within-noise 结论都暂不使用。

## 路线、证据与资源

| 阶段 | 实验设计 | 数据/种子 | 主要产出与硬门 | 估计 GPU 资源/时间 | 当前状态 |
|---|---|---|---|---:|---|
| E1 amendment | common evaluator + common validation selector；先做尾批修正和 g=0 lockstep | 四域协议固定；新增训练 seed=100 | 所有方法同一把尺；不改 Gate-0/1 原文 | CPU 为主；约 0.5–2 h | E00/E01 证据已归档，E1 R12 通过 |
| Pilot RISK-06/07 | host、text-anchor-only 与 risk-gated-full 的 0/60/100 corruption arms；E1-pass 14 个任务，E1-fail-audit 8 个任务仅作冻结分支 | Beauty/Steam；seed=100；每卡一个进程 | RISK-04 severe gate、RISK-05 prereg、完整 artifact manifest；失败即 fail-closed | 当前 manifest high forecast 约 56 GPU-h（14 个 pass 任务；单 GPU 串行约 2.3 GPU-day，上限取决于 early stop） | r3 正在 l20 GPU1 运行 |
| 三 seed matched rerun | host/full 在四域、相同 selector 和 full-catalog evaluator 下重复 3 个 seed | Steam/ML1M/Beauty/ATG；仅在单 seed 通过且另行授权后 | 报告均值/区间和 seed dispersion；不得用单 seed 支撑稳定性 | 粗估 24 runs × 1–4 h = 24–96 GPU-h（1–4 GPU-day）；可用两张卡并行但 GPU0 当前被 CLOSE-10 占用 | 当前不启动 |
| ATG attribution + Steam severe | global-p、u-shuffle 等 attribution controls；Steam popularity-stratified 60% embedding permutation，clean→c60 mean gate drop ≥20% 才可训练 | ATG/Steam；corruption seed=100 | 排除数据集/噪声/门控替代解释；门不过则只留资产和 hash，不训练 | 约 4–12 GPU-h；corruption/preflight CPU 约 1–3 h | RISK-04 severe gate 已 pass；pilot 正在兑现训练证据 |
| SASRec/BERT4Rec baseline | shared split/mapping/full-catalog candidate/common selector；一旦启动必须四域齐报 | Steam/ML1M/Beauty/ATG；seed=100 | 不允许 favorable-only subset；每个 baseline all-four atomic group | SASRec 约 2–8 GPU-h；BERT4Rec 约 8–24 GPU-h（视实现与序列长度） | 当前队列不含 baseline；另行授权后再排 |
| U_ds uncertainty + additional datasets | 冻结 transition records 的 user-clustered bootstrap（≥1000 reps）；不重新采样、不训练 | 四域；sampling seed=7，bootstrap seed=100 | 95% 区间、order retention、负采样定义；p=1/24 只作 exchangeability 下描述性计算 | CPU 约 1–4 h；0 GPU-h | 既有 E07 hard-stop 证据保留，需补齐输入才可重开 |
| efficiency + final integration | host/full 100 warm-up + 1000 timed batches × 5 repeats；冻结 checkpoint；整合中英文 paper 和 reproducibility 句 | Steam/ML1M（若按既定 E08） | 绝对吞吐、峰值显存、延迟和 CV；论文写明 validation-only model selection | 约 2–6 GPU-h + 4–8 h 文稿整合 | 当前不与训练并发，避免抢卡 |

## 服务器调度与停止条件

当前唯一新增训练队列是 r3 dated root。controller 在 GPU0 忙时只会尝试 GPU1，且 runtime 会将生产 `single_train.py` 的 `cuda=` token 重写为租用的物理卡，防止训练器再次把 GPU1 映射回 GPU0。以下任一条件发生，队列不得继续派发：

1. `/data` 可用空间低于 40 GiB；
2. 新 PID 出现在 GPU0，或进程环境/命令中的 CUDA 绑定与记录不一致；
3. 非零退出、OOM、缺失 success artifact、hash/manifest 不一致；
4. 需要 retry、第二个 seed、改变 selector/corruption/threshold 或重新选择 checkpoint；
5. 任一 baseline 未能在同一次启动中覆盖四个数据集。

## 论文可写边界

在 r3 完成前只能写“controller/绑定检查通过”“Beauty/host single-run observation 已完成”等事实。pilot 完成后仍需 RISK-08 artifact-backed exit；三 seed、baseline、uncertainty 和 efficiency 未完成前，不把它们写成已验证结论。reproducibility 声明应包含：`model selection used validation only; test metrics were logged during development`，不得把 test 称为 untouched final holdout。

