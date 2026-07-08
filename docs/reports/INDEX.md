# 试验文档索引

- 更新日期: 2026-07-09
- 用途: 从任务视角快速定位当前仍有效、仍作为权威依据的文档。过程性长序列已尽量移入 `archive/`，dated 数据产物统一放在 `data/`。

## 1. 设计与任务账本

| 内容 | 权威文档 |
| --- | --- |
| 原始 Text-Side / USDPD 设计 | `docs/superpowers/specs/2026-06-24-usdpd-text-side-kernel-design.md` |
| AAAI-27 fallback-safe 设计 | `docs/superpowers/specs/2026-07-02-aaai27-fallback-safe-kernel-sprint-design.md` |
| 当前 closeout 设计 | `docs/superpowers/specs/2026-07-06-evidence-priced-schedule-design.md` |
| 历史 AAAI-27 冲刺账本 | `../issues/2026-07-02_17-06-23-aaai27-fallback-safe-kernel.csv` |
| 当前 closeout 总台账 | `../issues/2026-07-06_evidence-priced-schedule-and-closeout.csv` |
| 更早历史账本 | `../issues/2026-06-25_20-06-08-usdpd-text-side-rawdata.csv`,`../issues/2026-06-24_03-36-17-rec-equiv-modality-completion.csv` |

## 2. Gate 0 证据链

当前 Gate 0 / Family D 起点统一看 `data/2026-07-02-gate0/` 下工件，核心入口:

1. `data/2026-07-02-gate0/gate0_text_utility_report_zh.md`
2. `data/2026-07-02-gate0/gate0_text_utility_summary.csv`
3. `data/2026-07-02-gate0/gate0_v2_frozen_verdict.md`
4. `data/2026-07-02-gate0/gate0_v2_family_d_downgrade_memo_zh.md`
5. `2026-07-04-family-d-claim-freeze-cn.md`

## 3. 主表与 safe main-path 冻结基线

| 内容 | 权威文档 |
| --- | --- |
| 四数据集 vs core 冻结对照 | `data/2026-07-01-text-side-vs-core-main-table-remote-v77.csv` |
| 主张冻结 | `2026-07-02-main-path-claim-freeze-cn.md` |
| 写作包 | `2026-07-02-main-path-paper-writing-pack-cn.md` |
| 发布候选 | `2026-07-02-main-path-release-candidate-cn.md` |
| 收口清单 | `2026-07-02-main-path-submission-readiness-cn.md` |
| 交付包 | `packages/2026-07-02-main-path-package-v1/` |

## 4. Beauty 机制证据链

| 内容 | 权威文档 |
| --- | --- |
| 最终机制评估 | `2026-06-28-beauty-idea-assessment-final.md` |
| 汇总版 | `2026-06-28-beauty-idea-assessment-consolidated.md` |
| 控制组结果 | `2026-06-28-beauty-token-dropout-control-results.md` |
| u 组成消融 | `2026-06-28-beauty-token-dropout-u-components-results.md` |
| corruption 端到端 | `2026-06-28-beauty-token-dropout-end-to-end.md` |
| 诊断解读 | `2026-06-28-beauty-diagnostics-interpretation.md` |

## 5. 数据协议与复现

| 内容 | 权威文档 |
| --- | --- |
| raw-data-first 协议 | `2026-06-24-raw-data-protocol-recommendation.md` |
| ML1M / Steam 复现 | `2026-06-24-ml1m-reproduction-report.md`,`2026-06-24-steam-reproduction-report.md` |
| README 早停跑法 | `2026-06-24-remote-readme-early-stop-runbook.md`,`2026-06-25-remote-readme-earlystop-results.md` |

## 6. 当前 closeout 主线

| 内容 | 权威文档 |
| --- | --- |
| closeout 执行资产清单 | `2026-07-09-closeout-execution-asset-manifest-cn.md`,`data/2026-07-09-closeout-execution-asset-manifest.csv` |
| 用户动作清单 | `2026-07-09-user-action-checklist-cn.md` |
| 项目深度理解与优先级地图 | `2026-07-09-project-understanding-and-priority-map-cn.md` |
| 近 7 天训练-写稿协同时间线 | `2026-07-09-7day-training-writing-execution-timeline-cn.md` |
| `CLOSE-02` 工件落地联动手册 | `2026-07-09-close02-artifact-arrival-playbook-cn.md` |
| Gate-2 证据包 | `2026-07-09-gate2-evidence-packet-cn.md` |
| Gate-2 冻结当天执行手册 | `2026-07-09-gate2-freeze-day-runbook-cn.md` |
| Gate-2 报告模板 | `data/2026-07-14-gate2/gate2_report_zh.template.md` |
| 摘要冻结候选 | `2026-07-09-abstract-freeze-candidate-cn.md` |
| 摘要冻结与提交执行手册 | `2026-07-09-abstract-freeze-and-submission-runbook-cn.md` |
| 摘要提交记录模板 | `data/2026-07-20-abstract-submission/abstract_submission_record.template.md` |
| 投稿前终审执行手册 | `2026-07-09-close08-pre-submission-review-runbook-cn.md` |
| `CLOSE-08` review log 模板 | `data/2026-07-26-close08/close08_review_log.template.md` |
| closeout 资产可达性审计 | `2026-07-09-closeout-asset-link-audit-cn.md`,`data/2026-07-09-closeout-asset-link-audit.csv` |
| `main_v2` 占位符盘点 | `2026-07-09-main-v2-placeholder-inventory-cn.md` |
| `main_v2` 措辞补丁 | `2026-07-09-main-v2-wording-patches-cn.md` |
| supplementary 打包清单 | `2026-07-09-supplement-bundle-checklist-cn.md` |
| wording 回归审计 | `data/2026-07-09-main-v2-regression-wording-audit.md` |
| 数字 provenance 审计 | `data/2026-07-09-main-v2-numeric-provenance-audit.md` |
| 数据集统计来源审计 | `data/2026-07-09-dataset-stats-source-audit.md` |
| `CLOSE-02` 本地同步说明 | `data/2026-07-09-close02-ml1m-noise-floor-sync-note.md` |

## 7. 论文

- `paper/main_v2.tex` — 当前 AAAI-27 投稿主稿
- `paper/main_v2_zh.md` — 中文镜像与作者审阅导览
- `paper/main.tex` — 冻结历史稿，用于对照和 appendix 回取
- `paper/references.bib` — 参考文献数据库
- `paper/README.md` — 编译与写作纪律

## 8. 归档与清理记录

- `archive/main-path-refresh-serial/` — 2026-07-01/02 主路径 watcher 刷新序列
- `archive/` — 已归档的历史中间态文档
- `_desktop_archive/` — 桌面捕获与临时整理历史
