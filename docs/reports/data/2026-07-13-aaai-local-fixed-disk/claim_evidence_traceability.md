# Claim–Evidence Traceability（2026-07-13）

本表的用途不是替论文制造更多主张，而是阻止主张越过证据边界。机器可读版本见 `claim_evidence_traceability.csv`。

| ID | 当前状态 | 可进入正文的最强结论 | 尚缺条件 |
|---|---|---|---|
| C01 | artifact-proven | 四域 train-only `U_ds` 点估计 | 无法推出总体规律 |
| C02 | artifact-proven | E0 完成同尺重评且 verdict 未翻转 | 严格 4/4 从未成立 |
| C03 | scope-limited | 指定 R12 trace 2,986/0 | 不覆盖所有路径 |
| C04 | artifact-backed | EPE/`phi_R` 与 `U_ds` 分层 | 需同步进 Method/摘要 |
| C05 | provenance-limited | r6a 仅为实现快照 | 不可替代 r7 终态 |
| C06 | blocked | r7 进行中 | 14/14 + RISK-08/terminal |
| C07 | single-run | 适配版 SASRec 四域原子结果 | Beauty 异常需并列披露 |
| C08 | not-estimable | 本周期未量化用户级不确定性 | frozen records 缺 user ID |
| C09 | disclosed | validation-only selection；test 开发期记录 | 不得称 untouched holdout |
| C10 | scoped | kernel/one-step row 理论界 | 不得扩张到端到端性能 |

任何表格进入论文前，必须从源工件重新生成或逐行核验 SHA。当前表已回填引用源的 SHA；如果任一源文件继续修改，必须同步刷新对应行。
