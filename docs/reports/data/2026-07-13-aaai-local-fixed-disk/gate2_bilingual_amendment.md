# Gate-2 中英文证据与措辞修正备忘（2026-07-13）

## 适用范围

本备忘统一约束 `paper/main_v2.tex`、`paper/main_v2_zh.md`、摘要、实验表及补充材料。它不改动历史工件，不把单次运行升级为统计结论，也不把 r7 非终态快照写入性能表。

## 中文冻结措辞

1. **E1/R12。** 初次 step-0 trace 触发 hard stop 的历史事实保留。修复后的 R12 指定路径 trace 在 revision `0338cc219f9ee983b8e9464b4df85f34471c7d6f` 上完成 2,986 项比较、0 项失败；marker SHA-256 为 `040afa9328e05ba6fcfb36b26ae561657236a0d0a033e97e9ceb7c9a40a2924c`。该证据只覆盖指定 Beauty 路径、指定算子序列和 revision，不代表所有 checkpoint、数据集或旁路注入模式。
2. **三层方法结构。** `U_ds` 是 train-only 的跨数据集发现统计量；EPE 是 `log(q_text(y|h)+1e-12)-log(q_core(y)+1e-12)`，在论文中称为“已观察下一正例暴露代理”；生产 `phi_R` 是预注册的 corruption-risk 干预量。三者不可互换。
3. **Table 1。** 撤回“严格 4/4 全序命中”。新旧 evaluator 下的严格排序均为 Steam、Beauty、ATG、ML1M，而 `U_ds` 从低到高为 Steam、ATG、Beauty、ML1M；Beauty/ATG 相邻互换，Steam/ML1M 两端保持。`1/24` 只可作为 exchangeability 假设下的描述性排列比例，不能称为经验 p 值或显著性检验。
4. **c100。** 统一写为：“在预注册 `phi_R=0` 下，生产训练路径的 selected best-summary 与 host 字节级相同；checkpoint 因包含 text-side builder 状态而不同。”禁止写成用户级 `u_tilde` 自动塌缩。
5. **Beauty。** 任意 c0/c60 表格必须并列 validation 与 test。Beauty c0 的 validation 差约为零而 test 为正向单次观测；selector 只使用 validation，test 在开发期间被记录。不得仅展示 test 增益。
6. **SASRec。** E5 称为“共同评估合同下的适配版 SASRec baseline”，不是官方代码逐项复现。四域必须原子齐报，Beauty 的 validation/test 落差必须在正文或 caption 注记。
7. **E7。** frozen transition records 缺 user ID，bootstrap 实跑次数为 0，用户级区间与排序保持率均不可估计。配置中的 1000 次不得表述为已执行。
8. **理论边界。** exact fallback 与 TV bound 只限 proposal、单步 transition-row 及明确实现路径；不得扩张为端到端推荐性能界、训练轨迹等价或多步误差界。
9. **比较边界。** DiffuRec 不进入 confirmatory comparison。测试指标在开发期间被记录，论文不得声称 test 是 untouched final holdout。
10. **r7 发布闸门。** 只有 14/14 active tasks、非空日志、完整 manifests、`RISK-08_EXIT.json` 与 `TERMINAL.json` 一致且出口为 `risk_gated_method` 时，才允许生成 r7 性能表。`audit_only` 或 `submission_stop` 只保全证据。

## Frozen English wording

1. **E1/R12.** We retain the historical hard stop triggered by the initial step-0 trace. After the implementation repair, the designated R12 production trace at revision `0338cc219f9ee983b8e9464b4df85f34471c7d6f` completed 2,986 comparisons with zero failures (marker SHA-256 `040afa9328e05ba6fcfb36b26ae561657236a0d0a033e97e9ceb7c9a40a2924c`). This claim is scoped to the designated Beauty path, operator sequence, and revision; it does not certify every checkpoint, dataset, or auxiliary injection mode.
2. **Three-layer method account.** `U_ds` is a train-only cross-dataset discovery statistic. EPE is `log(q_text(y|h)+1e-12)-log(q_core(y)+1e-12)` and is described as an *observed next-positive exposure proxy*. The production `phi_R` is a preregistered corruption-risk intervention. These quantities are not interchangeable.
3. **Table 1.** We withdraw the phrase “strict 4/4 rank match.” Under both legacy and corrected evaluators, the effect order is Steam, Beauty, ATG, ML1M, whereas increasing `U_ds` orders the domains as Steam, ATG, Beauty, ML1M. The adjacent Beauty/ATG pair is reversed, while the Steam/ML1M endpoints are retained. The `1/24` quantity is only a descriptive permutation fraction under exchangeability, not an empirical p-value or significance test.
4. **c100.** Under the preregistered `phi_R=0`, the selected best-summary on the production training path is byte-identical to the host summary; checkpoints differ because text-side builder state is serialized. We do not attribute this result to a collapse of user-level `u_tilde`.
5. **Beauty disclosure.** Every c0/c60 presentation reports validation and test side by side. The Beauty c0 validation delta is approximately zero while the test delta is a positive single-run observation. Selection uses validation only, and test metrics were logged during development.
6. **SASRec.** E5 is an *adapted common-contract SASRec baseline*, not a line-by-line reproduction of the official implementation. All four domains are reported atomically, including the Beauty validation-to-test drop.
7. **E7 and theory.** User-level uncertainty is not estimable because frozen transition records lack user identifiers and zero bootstrap replicates were run. Exact fallback and TV claims are limited to the proposal/kernel and one-step transition row.
8. **Release gate.** r7 performance is released only after 14/14 active tasks, complete nonempty provenance, consistent RISK-08/terminal markers, and a `risk_gated_method` exit. Other exits preserve evidence without producing a performance table.

## 一次性集成检查

- 摘要先改三层 gate 叙述，再制作图表。
- Table 1 同时报 legacy/corrected 或在 caption 指向仲裁备忘。
- Table 2 不选择性替换数字；若整体换尺，所有方法一起换。
- 所有 single-seed 结果使用 “single-run observation”。
- 禁用 `significant`、`stable`、`statistically equivalent`、`within noise`。
