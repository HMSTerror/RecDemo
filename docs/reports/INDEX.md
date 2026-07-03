# 试验文档索引(按任务脉络)

- 更新日期:2026-07-04
- 用途:从任务视角快速定位权威文档。每个主题只列"当前作准"的文档;过程性序列报告已移入 `archive/`,数据产物一律在 `data/`。

## 1. 设计与任务账本

| 内容 | 权威文档 |
| --- | --- |
| 原始设计(Text-Side USDPD,含命题 1–5) | `docs/superpowers/specs/2026-06-24-usdpd-text-side-kernel-design.md` |
| AAAI-27 冲刺设计(v2 核 + §7 效用门控修订 + §8 验证跑授权与 Family D 基线) | `docs/superpowers/specs/2026-07-02-aaai27-fallback-safe-kernel-sprint-design.md` |
| 冲刺执行账本(SPRINT-01..13 / FOLLOWUP-01..10 / REVIEW-01) | `issues/2026-07-02_17-06-23-aaai27-fallback-safe-kernel.csv` |
| 历史账本(rawdata 主线、模态补全,已被冲刺账本接续) | `issues/2026-06-25_20-06-08-usdpd-text-side-rawdata.csv`,`issues/2026-06-24_03-36-17-rec-equiv-modality-completion.csv` |

## 2. Gate 0 证据链(2026-07-02 起,全部在 `data/2026-07-02-gate0/`)

按发生顺序:

1. `gate0_u_tilde_report.md` — Gate 0 首跑 FAIL(ML1M ũ=1.43 最高,判据反序)
2. `gate0_failure_diagnostic_zh.md` — 失败归因
3. `gate0_calibration_repair_audit_zh.md` — 96 个全局修复候选 0 通过,关闭简单修复路径
4. `gate0_original_design_return_assessment_zh.md` — 主路径边界冻结
5. `gate0_deeper_repair_design_zh.md` — 四修复家族设计(Family A 推荐,后被构念分析否决)
6. `gate0_text_utility_report_zh.md` / `gate0_text_utility_summary.csv` — 生产 U_ds(ML1M 0.754 / Beauty 0.712 / ATG 0.688 / Steam 0.570,与 v1 结果 4/4 完美逆序)
7. `gate0_v2_frozen_verdict.md` — Gate 0-v2 按冻结判据 FAIL(仅 Steam 开门)
8. `gate0_v2_family_d_downgrade_memo_zh.md` + `followup07_frozen_verdict_timing_note_zh.md` — Family D 路径确立与裁决时间说明

当前状态:按 spec §8,Family D 为承诺基线(FOLLOWUP-08,期限 7/7);SPRINT-05 经用户授权转为冻结配置验证跑(预注册预测见 spec §8.2)。

## 3. 主表冻结基线(2026-07-01/02)

| 内容 | 权威文档 |
| --- | --- |
| 四数据集 vs core 对照冻结 | `data/2026-07-01-text-side-vs-core-main-table-remote-v77.csv` |
| 运行状态冻结 | `data/2026-07-01-text-side-main-table-run-status-remote-v80.csv` |
| 主张冻结 | `2026-07-02-main-path-claim-freeze-cn.md` |
| 写作包(safe claim 措辞) | `2026-07-02-main-path-paper-writing-pack-cn.md` |
| 发布候选稿 | `2026-07-02-main-path-release-candidate-cn.md`(md/html/pdf 三层) |
| 收口清单 | `2026-07-02-main-path-submission-readiness-cn.md` |
| 交付包 | `packages/2026-07-02-main-path-package-v1/`(54 artifacts,勿改) |
| 主路径回归判断 | `2026-07-02-original-design-main-path-return-assessment-v10-cn.md` |

## 4. Beauty 机制证据链(2026-06-28,v1 时代,机制结论仍作准)

| 内容 | 权威文档 |
| --- | --- |
| 最终对照评估(机制成立、full_u 未全面胜出) | `2026-06-28-beauty-idea-assessment-final.md` |
| 汇总版 | `2026-06-28-beauty-idea-assessment-consolidated.md` |
| 控制组结果(global_p / u_shuffle 崩、anchor 强) | `2026-06-28-beauty-token-dropout-control-results.md` |
| u 组成消融(agreement-centered 是稳核) | `2026-06-28-beauty-token-dropout-u-components-results.md` |
| corruption 端到端 | `2026-06-28-beauty-token-dropout-end-to-end.md` |
| 诊断解读 | `2026-06-28-beauty-diagnostics-interpretation.md` |

## 5. 数据协议与复现

| 内容 | 权威文档 |
| --- | --- |
| raw-data-first 协议(科学主协议) | `2026-06-24-raw-data-protocol-recommendation.md` |
| ML1M / Steam 复现 | `2026-06-24-ml1m-reproduction-report.md`,`2026-06-24-steam-reproduction-report.md` |
| README 早停跑法 | `2026-06-24-remote-readme-early-stop-runbook.md`,`2026-06-25-remote-readme-earlystop-results.md` |

## 6. 论文

- `paper/main.tex` — AAAI-27 草稿(59 个红色占位符,仅可用 `data/` 带日期产物回填;Gate-2 出口决定措辞档位)
- `paper/references.bib` — `%% VERIFY` 条目投稿前必须核实
- `paper/README.md` — 编译与写作纪律

## 7. 归档与清理记录

- `archive/main-path-refresh-serial/`(39 篇)— 2026-07-01/02 主路径 watcher 刷新序列,已被冻结基线取代
- `archive/beauty-token-dropout-serial/`(75 篇)— 2026-06-28 dropout 参数二分的 launch/progress 序列,结论已并入第 4 节文档
- `_desktop_archive/` — 桌面文档收束历史
- 2026-07-04 清理:删除仓库根部全部 `tmp_*` 临时文件(siglip tar 297M、steam raw 调试转储 4×~60M、ml1m paper-like 副本 45M、movielens 抓取残留等,约 540MB;g0 报告已确认在 `data/` 有正式副本后删除其 tmp 版)与三处 `__pycache__`。`tmp/` 目录保留(含账本引用的 `check_text_utility_legacy.py` 与 ag40 分析快照)。
