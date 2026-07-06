# SPRINT-05 / Gate 1 官方读数

- 生成时间: `2026-07-06T13:49:01+08:00`
- 官方状态表来源: `/data/Zijian/goal/RecDemo_clean_main/docs/reports/data/2026-07-05-sprint05/text-side-main-table-run-status.csv`
- 官方比较表来源: `/data/Zijian/goal/RecDemo_clean_main/docs/reports/data/2026-07-05-sprint05/text-side-vs-core-main-table.csv`
- 规格锚点: `docs/superpowers/specs/2026-07-02-aaai27-fallback-safe-kernel-sprint-design.md`

## SPRINT-05 结论

- 官方四数据集是否全部完成: `true`
- 总结: All four datasets finished under clean-root manifests; Beauty hit parity, Steam kept the positive sign but missed the reference magnitude, while ML1M and ATG missed parity.
- 命中数据集: `Beauty`
- 部分命中数据集: `Steam`
- 未命中数据集: `ML1M, ATG`

## 四数据集官方结果

| 数据集 | 预注册预测 | 实际判定 | delta_test_p2@10 | 备注 |
| --- | --- | --- | ---: | --- |
| Steam | delta_test_p2_ndcg10 > 0 | directional_hit_reference_miss | 0.002015 | Steam kept the positive sign but stayed below the >= +0.003 reference magnitude. reference_magnitude_outcome=miss |
| ML1M | abs(delta_test_p2_ndcg10) < 0.01 | miss | -0.015133 | ML1M missed its pre-registered parity-style prediction. |
| Beauty | abs(delta_test_p2_ndcg10) < 0.01 | hit | -0.003859 | Beauty satisfied its pre-registered parity-style prediction. |
| ATG | abs(delta_test_p2_ndcg10) < 0.01 | miss | -0.011410 | ATG missed its pre-registered parity-style prediction. |

## Manifest 审计

| 数据集 | clean-root | 冻结配置 | hash 记录 | 结论 |
| --- | --- | --- | --- | --- |
| Steam | pass | pass | pass | pass |
| ML1M | pass | pass | pass | pass |
| Beauty | pass | pass | pass | pass |
| ATG | pass | pass | pass | pass |

## Gate 1 判定

- ML1M 官方 `delta_test_p2_ndcg10 = -0.015133`; 通过阈值是 `> -0.01`，单次诊断迭代触发阈值是 `<= -0.03`。
- Gate 1 verdict: `fail_no_diagnostic`
- 解释: ML1M missed the no-loss threshold, but not badly enough to open the single frozen diagnostic iteration.
- 与通过线的差距: `-0.005133`
- 与诊断触发线的差距: `0.014867`
- 命题 6 经验主张是否暂停: `true`

## Gate 2 仍可达出口

- `strong`: `not_reachable`; Needs all four pre-registered outcomes to land cleanly, including Steam reaching the reference magnitude. The current official table does not satisfy that.
- `medium`: `not_reachable`; Needs the no-loss main line to hold on the Gate 1 path. The official ML1M delta is -0.015133, which stays below the -0.01 pass threshold.
- `weak`: `reachable`; The Family D baseline wording was already frozen in FOLLOWUP-08, so the weak exit remains available even when Gate 1 does not clear.

## 直接结论

本次 `SPRINT-05` 官方四数据集重跑已经完成，且 manifest 证明它们来自 clean-root 冻结配置。
但 `SPRINT-06` 所关心的 ML1M Gate 1 仍未过线：它没有差到允许那次冻结诊断的程度，却也没有达到 no-loss 门槛。
因此这里最诚实的状态是：`SPRINT-05` 可以关账，`SPRINT-06` 应记录为 Gate 1 未通过且当前只剩弱出口随时可用。
