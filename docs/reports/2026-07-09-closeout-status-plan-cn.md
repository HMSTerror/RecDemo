# AAAI-27 Closeout 状态与执行计划

_项目状态报告，基于 2026-07-09 当前工作区、closeout 账本、论文草稿与已落地 artifact 整理_

---

## TL;DR

- 当前主线仍然是 `issues/2026-07-06_evidence-priced-schedule-and-closeout.csv` 这条 closeout 账本，而不是更早的 sprint 文档。
- `CLOSE-02` 仍是第一优先级，但状态已从“本地没有新工件”推进到“本地已有 `2026-07-09` partial dated artifact，仍待 `seed102` 收口”。
- `paper/main_v2.tex` 当前真实待填只剩 2 处，全部与 `CLOSE-02` 的 ML1M host noise floor 归因有关。
- 在 `seed102` 完成、或明确接受 `2/3` provisional readout 前，论文与摘要都必须继续按 `Family D / weak-default` 口径推进。

## 2026-07-09 傍晚更新（实况快照）

本节记录 2026-07-09 傍晚一次远端实况核对后的三个新事实，供下次接手直接读取，避免重复踩过时数字。

### 1. close02 seed102 仍在训练，且 provisional 已大幅爬升（推翻旧读数）

- 服务器实况（约 18:30）：`seed102` 进程 `1811976` 存活，`last step = 391000`，`best_step=390000`，**provisional `test_p2_ndcg10 = 0.09798`，仍无 completion marker**。
- 这**推翻**了账本早前误记的 `seed102_final:0.07673 @194000`（那是 step 194000 的过早读数被误当成完成，与 7/7 seed100 事故同型，已在 CLOSE-02 notes 留更正记录）。
- seed102 一天内的 provisional 轨迹：`0.0767(194k) → 0.0826(225k) → 0.09399(330k) → 0.09798(391k)`，一路爬升未早停（seed100/101 分别到 536k/464k 才早停）。
- **对噪声地板的影响是决定性的**：max pairwise = |seed100 0.10579 − seed102|。若 seed102 停在当前 0.098，地板 ≈ **0.0078 < 0.0151**，medium 出口被锁回 weak；越往后跑地板越小。**当前证据趋势是 Gate-2 大概率维持 weak-default。**
- 纪律判定：无 completion marker → 无 final artifact → **仍是分支 A**：不重建最终 report、不动 `main_v2.tex` 两处 `\pending`、不升 medium。

### 2. CLOSE-04 DiffuRec 四数据集全部完成

远端 `close04_session.log` 已出现 Steam/ML1M/Beauty/ATG 四个 `FINISH`，对比表已生成并同步回本地。DiffuRec vs host vs ours（test NDCG@10）：

| 数据集 | DiffuRec | host | ours |
| --- | ---: | ---: | ---: |
| Steam | 0.07382 | 0.01290 | 0.01491 |
| ML1M | 0.14116 | 0.09102 | 0.07589 |
| Beauty | 0.04349 | 0.03329 | 0.02944 |
| ATG | 0.03693 | 0.04188 | 0.03047 |

- DiffuRec 在 Steam/ML1M/Beauty 明显高于 host 与 ours；ATG 上 host 反而最高。
- 论文处理（用户已同意的纪律）：全量诚实报告 + Setup 正交性说明句（宿主绝对竞争力与 within-host 主张正交），主张零改动。
- 本地工件：`docs/reports/data/2026-07-07-close04-diffurec/close04_diffurec_comparison.{csv,md}`。

### 3. CLOSE-10 ATG 噪声地板脚本已就绪（尚未发射）

- 已交付并测试通过（本地零远端风险）：
  - `scripts/launch_close10_atg_noise_floor_tmux.py`（close02 的 dataset-swap 克隆，ATG host 臂 npr=0.2/lr=1e-3/score_flag=True，hybrid/gamma=0.9999/p5，2 seeds 100/101）
  - `scripts/build_close10_atg_noise_floor_report.py`（gate1 改读 ATG delta −0.01141）
  - 对应测试 `tests/test_launch_close10_atg_noise_floor_tmux.py`、`tests/test_build_close10_atg_noise_floor_report.py`，CLOSE-10 共 14 测试通过，close02 原 9 测试回归通过。
- **尚未发射**：按用户指示，等 GPU 真正空出、双发风险处理完后再决定挂载时机与优先级。
- 资源冲突提醒：GPU1 已有 `close03_deblocked_queue` → `close11_steam_orig` 两个等待器排队；CLOSE-10 按手册 §11 优先级高于二者（喂 Gate-2，7/13 硬线），发射时需协调插队顺序。

### 双发风险与链状态（未变，仍需盯）

`closeout_run_chain`（老）与 `close03_deblocked_queue`（新）都存活，都会在 close02 会话退出时尝试发射 close03。seed102 早停、会话退出那一刻必须人工核验只有一个 close03 在跑。

---

## 恢复上下文

- 恢复源：`issues/2026-07-06_evidence-priced-schedule-and-closeout.csv`
- 当前恢复点：`CLOSE-02`
- 论文边界：`docs/reports/2026-07-04-family-d-claim-freeze-cn.md`
- 当前 closeout 配套文档：
  - `docs/reports/2026-07-09-project-understanding-and-priority-map-cn.md`
  - `docs/reports/2026-07-09-gate2-evidence-packet-cn.md`
  - `docs/reports/data/2026-07-09-close02-ml1m-noise-floor-sync-note.md`

## 当前状态

| 模块 | 当前状态 | 证据 | 对投稿的影响 |
| --- | --- | --- | --- |
| Gate-1 官方案读数 | 已完成，默认只支持 `weak` | `docs/reports/data/2026-07-06-gate1/sprint05_gate1_report_zh.md` | 是 7/14 Gate-2 的默认基线 |
| SPRINT-07 v2 controls | 已完成 | `docs/reports/data/2026-07-06-sprint07/sprint07_control_report_zh.md` | 支撑 control paragraph，不再是 blocker |
| CLOSE-02 host noise floor | 本地已同步 `2026-07-09` partial dated artifact：`seed100/101` completed、`seed102` running、当前 `decision_line=outside_noise_red_flag`；刷新后的 partial report 已把 `seed102 last_logged_step` 推到 `121000`，而且远端只读探针还读到了 `seed102` 的 provisional host summary（`best_step=174000`，`test_p2_ndcg10=0.07339`）；同时 `diag` 复跑已写出 provisional best summary（`best_step=141000`，`test_p2_ndcg10=0.05612`），但两条 run 都未完成 | `docs/reports/data/2026-07-09-close02-ml1m-noise-floor/close02_ml1m_noise_floor_report_zh.md`；sync note | 仍是最关键 P0；已有最新本地权威状态，但还不够安全升级正文结论 |
| CLOSE-03 Beauty corruption rerun | deblocked queue 已就绪，但仍在等 GPU1 被 `CLOSE-02 seed102` 释放 | closeout CSV `CLOSE-03` 备注 | 对 abstract 不是 blocker，对正文 robustness 叙事有帮助 |
| CLOSE-04 external baseline | **四数据集全部 FINISH（2026-07-09 傍晚）**：Steam/ML1M/Beauty/ATG 的 DiffuRec 臂都已完成，远端对比表已生成，`comparison.csv/md` 已同步回本地 `docs/reports/data/2026-07-07-close04-diffurec/`；关键读数见下方“2026-07-09 傍晚更新”节 | `docs/reports/data/2026-07-07-close04-diffurec/close04_diffurec_comparison.md`（本地已同步）；closeout CSV `CLOSE-04` 备注 | 对 setup/appendix 有价值；DiffuRec 在 Steam/ML1M 明显高于 host/ours，需按已约定纪律做“全量报告 + 正交性说明”，但不是 7/20 abstract blocker |
| CLOSE-06 abstract freeze | 初审已完成，OpenReview 提交仍 pending | closeout CSV `CLOSE-06`；`paper/main_v2.tex` | 2026-07-18 前必须冻结，2026-07-20 提交 |
| 主稿 `main_v2` | 草稿骨架完整，剩余 `\pending{}` 只剩 2 处 | `paper/main_v2.tex`；`docs/reports/2026-07-09-main-v2-placeholder-inventory-cn.md` | 可并行润色，但还不能宣称 submission-ready |

## 优先级

### 1. CLOSE-02

为什么仍是第一优先级：

- 它决定 `Gate-1 ML1M delta=-0.015133` 能否被改写为 host-noise-floor 解释。
- 它直接影响 `CLOSE-05` 在 2026-07-14 是否只能冻结 `weak`，还是存在 `medium-conditional` 讨论空间。
- `paper/main_v2.tex` 的两处最后红灯句都显式依赖它。

今天的目标交付：

- 把已经同步回本地的 `2026-07-09` partial `close02` 表/JSON/中文报告正式写进 closeout 文档与账本。
- 明确写出：当前 partial 工件只支持“继续保持 conservative branch”，不支持提前升级正文。

### 2. CLOSE-05

- 继续按 `weak-default / medium-conditional` 准备 7/14 Gate-2 冻结包。
- 7/9 partial `close02` 工件现在可以进入证据包，但它当前支持的是“继续冻结 weak”，而不是“允许 medium”。

### 3. CLOSE-06

- abstract freeze 继续并行推进。
- 当前真正等待 `CLOSE-02` 的，只剩 abstract 中那条 ML1M 红灯归因敏感句。

### 4. CLOSE-03 / CLOSE-04

- `CLOSE-03` 继续视为条件分支，不得反向阻塞摘要与 Gate-2。
- `CLOSE-04` 继续监控，但不让它挤占 `CLOSE-02` 和 `CLOSE-06` 的注意力。

## 风险

| 风险 | 级别 | 当前表现 | 缓解动作 |
| --- | --- | --- | --- |
| `CLOSE-02` 仍未 final-freeze | 高 | 已有 7/9 partial artifact，但只完成了 `2/3` seeds；更重要的是，`seed102` 已出现一个很低的 provisional host summary，最终 noise floor 仍可能大幅翻转 | closeout 文档和 Gate-2 包可引用 partial 状态；论文正文仍不能写成 resolved |
| L20 / GPU 外部状态不可直接由本地证明 | 高 | `CLOSE-03/04` 仍依赖远端 runtime | 保留 conditional / documented-gap 分支，不让其卡死摘要主线 |
| `main_v2.tex` 仍有 2 个 artifact-sensitive 红灯位点 | 高 | 位置为 `659, 867` | 继续把它们严格绑定到 `CLOSE-02` 最终工件 |
| Gate-2 默认只能 weak | 中 | 7/9 partial 工件仍不支持升级 | 先准备 weak-default 文案，等待 `seed102` 最终完成 |

## 下一步清单

- [ ] 持续监控 `seed102`，在完成后用同一 builder 重新生成最终 `CLOSE-02` report。
- [ ] 在此之前，按 `2026-07-09` partial artifact 更新 closeout 文档、账本与 Gate-2 证据包，但保持 `main_v2.tex` 的 `weak-default` 文案不动。
- [ ] 在 2026-07-10 前对 `CLOSE-03` 做一次条件判断：继续跑，还是 documented gap 收口。
- [ ] 继续保留 `CLOSE-04` 的 `DiffuRec` 监控，但不让它影响 2026-07-14 Gate-2 和 2026-07-20 abstract 节点。

## 今日结论

截至 2026-07-09，项目已经从“方法是否成立”转入“如何在 dated artifact 约束下把投稿主线稳稳收口”。当前真正的关键不是再扩展新实验面，而是把 `CLOSE-02` 从“已有 partial local artifact”推进到“可最终冻结的 noise-floor 结论”；在 `seed102` 完成或明确接受 `2/3` provisional readout 之前，所有论文措辞都应继续服从 Family D 的保守边界。
