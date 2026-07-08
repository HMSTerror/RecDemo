# CLOSE-02 本地证据同步说明

_日期：2026-07-09_
_用途：记录本地工作区里关于 `CLOSE-02` 的最新可见证据、dated artifact 缺口，以及对 `paper/main_v2.tex` 的直接写作约束_

---

## 📝 一句话结论

截至 2026-07-09，本地工作区能看到的 **dated close02 报告工件** 仍只到 2026-07-07；但本地仓库中已经存在更晚的 **操作级证据**，明确记录了 `seed100` 的最终读数与对 Gate-2 的潜在影响。因为这些更晚证据尚未以新的 dated `close02` 报告形式落地，所以它们**可以指导规划与收口判断，但还不能直接升级 `paper/main_v2.tex` 中关于 ML1M 红灯归因的正文措辞**。

## 📍 已确认的本地证据层级

| 证据类型 | 本地路径 | 时间 | 可用于什么 | 不能用于什么 |
| --- | --- | --- | --- | --- |
| dated close02 报告目录 | `docs/reports/data/2026-07-06-close02-ml1m-noise-floor/` | 2026-07-06 | 早期快照 | 不能代表最终噪声地板 |
| dated close02 报告目录 | `docs/reports/data/2026-07-07-close02-ml1m-noise-floor/` | 2026-07-07 | 较晚但仍是 live 早期快照 | 不能代表最终噪声地板 |
| close02 retry 日志 | `logs/close02_only_retry_2026-07-07_00-41-15.log` | 2026-07-07 | 证明本地 watcher 曾持续轮询 close02 进度 | 不能直接作为最终指标工件 |
| closeout 账本备注 | `issues/2026-07-06_evidence-priced-schedule-and-closeout.csv` 的 `CLOSE-02` 行 | 2026-07-08 更新 | 记录 seed100 final 与运行解释 | 不是 dated report |
| handoff playbook | `docs/reports/2026-07-07-aaai27-handoff-playbook.md` | 2026-07-07 编写，含 7/8 新证据 | 记录更晚期操作结论与后续动作 | 不是 noise-floor builder 产出的正式 close02 报告 |

## 🔍 本地能确认的更晚期 close02 信息

### 1. `seed100` 最终读数已经被本地文本工件记录

两处本地文本证据一致指向同一组核心数字：

- `best_step = 536000`
- `val_p5 = 0.12469`
- `test_p2_ndcg10 = 0.10579`
- `test_p5_ndcg10 = 0.11352`

来源：

1. `issues/2026-07-06_evidence-priced-schedule-and-closeout.csv` 中 `CLOSE-02` 的 `notes`
2. `docs/reports/2026-07-07-aaai27-handoff-playbook.md`

后者还明确写出：

> `seed100` 最终 `test p2 NDCG@10 = 0.10579`，与官方宿主 `0.0910` 同种子同协议差 `+0.0148`，与 Gate-1 红灯缺口 `0.0151` 同量级。

### 2. 当前本地仍然缺少新的 dated close02 报告目录

本地 `docs/reports/data/` 下能看到的 close02 目录只有：

- `2026-07-06-close02-ml1m-noise-floor`
- `2026-07-07-close02-ml1m-noise-floor`

没有晚于 2026-07-07 的新目录，也没有包含 `seed100_final` 的本地 builder 输出文件被同步回来。

### 3. 这意味着“规划证据”和“可引用工件”仍然分离

当前我们已经知道：

- `seed100` 最终值很高
- 它和官方宿主之间的差值与 Gate-1 红灯量级非常接近
- 这提高了 `medium` 出口的现实可能性

但我们**还不知道**：

- `seed101` 和 `seed102` 的最终值
- 三种子之间的 `max pairwise abs delta`
- `build_close02_ml1m_noise_floor_report.py` 最终会给出怎样的 `decision_line`

而这三项恰恰是 `CLOSE-02` acceptance criteria 需要的正式交付物。

## ⚠ 对 `main_v2.tex` 的直接约束

在新的 dated close02 artifact 落地前：

1. `paper/main_v2.tex:659` 仍只能保留 “host noise floor pending / under investigation” 一类保守写法。
2. `paper/main_v2.tex:867` 的 limitations 也不能写成 “within the measured host noise floor”。
3. `paper/main_v2.tex:646-649` 一带的 Gate-2 upgrade-only 注释只能继续作为注释保留，不能提前抬入正文。

可直接配套使用的措辞补丁见：

- `docs/reports/2026-07-09-main-v2-wording-patches-cn.md`

## ✅ 当前最合理的 closeout 读法

- **对规划与排程：** 可以把 `seed100_final` 视为重要积极信号，说明 `CLOSE-02` 仍然值得优先等待。
- **对账本与协作：** 可以把 handoff playbook 和账本备注当作“较新但未正式封装”的中间证据。
- **对论文与投稿：** 不能把这些中间证据当作正式 dated noise-floor artifact 使用。

## 🔆 下一步

一旦新的 dated close02 工件同步到本地，应立即完成三件事：

1. 用新 artifact 更新 `CLOSE-02` 的 `decision_line`
2. 依据结果在 `paper/main_v2.tex` 中二选一替换：
   - `within-noise`
   - `implementation red flag remains`
3. 将 Gate-2 冻结包中的 ML1M 红灯归因从 “pending” 更新为 “dated evidence cited”

## 🧭 Artifact 落地后的最短执行链

这部分直接提炼自本地 handoff playbook 与 operations runbook，目标是让后续收口不必重新翻长文档。

### 1. 先拿到新的 close02 报告

playbook 中给出的目标路径是：

- 远端输出目录：
  - `/data/Zijian/goal/RecDemo_clean_closeout_chain/docs/reports/data/2026-07-07-close02-ml1m-noise-floor`
- 本地同步目录：
  - `docs/reports/data/2026-07-07-close02-ml1m-noise-floor/`

真正要看的三个文件是：

- `close02_ml1m_noise_floor_table.csv`
- `close02_ml1m_noise_floor_report.json`
- `close02_ml1m_noise_floor_report_zh.md`

### 2. 判定 `CLOSE-02` 是否可改写主稿

按 handoff playbook 的冻结规则，真正能支持 `medium` 出口升级的合法路径只有一条：

> `CLOSE-02` 显示 ML1M 的 `|-0.0151|` 缺口落在宿主噪声地板内。

也就是说，必须至少看到：

- 2-3 个宿主 core seeds 的最终值
- `max pairwise abs delta`
- report builder 产出的 `decision_line`

而不能只凭：

- `seed100_final`
- 单次 diag rerun
- live 日志中的测试指标

### 3. 改 CSV，再改论文

一旦 dated report 落地，推荐顺序是：

1. 先在 `issues/2026-07-06_evidence-priced-schedule-and-closeout.csv` 的 `CLOSE-02` `notes` 中追加：
   - `noise_floor:<value>`
   - `decision_line:<value>`
2. 再按 `docs/reports/2026-07-09-main-v2-wording-patches-cn.md` 替换：
   - `paper/main_v2.tex:659`
   - `paper/main_v2.tex:867`
3. 若 `decision_line` 支持升级，再把 Gate-2 冻结包从 `weak-default` 推到可讨论 `medium-conditional`

### 4. 仍然禁止的事

即使有新的操作日志，只要没有新的 dated close02 report builder 输出，仍然禁止：

- 把正文改成 “within the measured host noise floor”
- 在 Gate-2 前把 `medium` 当成既成事实
- 把 diag rerun 结果单独当成 `CLOSE-02` 的正式替代品
