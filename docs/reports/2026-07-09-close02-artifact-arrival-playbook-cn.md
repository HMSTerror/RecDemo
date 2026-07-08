# CLOSE-02 工件落地后的联动更新手册

日期: 2026-07-09

适用对象:

- `CLOSE-02`
- `CLOSE-05`
- `CLOSE-06`
- `CLOSE-07`

目的:

当新的 dated `CLOSE-02` noise-floor artifact 同步到本地后，不临场重想“要改哪”。这份手册只回答三件事:

1. 如何判定新工件是否足够权威
2. 它会把论文与台账推向哪条分支
3. 每条分支需要按什么顺序改哪些文件

## 1. 新工件必须满足什么条件

只有同时满足下面几项，才把它视为可触发正文升级的正式 `CLOSE-02` 工件:

1. 位于 `docs/reports/data/<dated-close02-dir>/`
2. 至少包含:
   - `close02_ml1m_noise_floor_report.json`
   - `close02_ml1m_noise_floor_report_zh.md`
   - `close02_ml1m_noise_floor_table.csv`
3. 内容来自 2-3 个 core seed 的正式 readout，而不是 handoff note 或晚到口头读数
4. 报告中能直接读出:
   - per-seed test `p2 ndcg10`
   - `max pairwise abs delta`
   - builder 给出的 `decision_line`

如果缺少任何一项，就仍按“无新 dated artifact”处理。

## 2. 工件落地后先看哪个字段

最先看的不是 prose，而是 `decision_line`。

只允许三类结论:

1. `within_noise_candidate`
2. `outside_noise_red_flag`
3. 空值/不明确

对应处理:

| `decision_line` | 论文分支 | Gate-2 分支 | 摘要分支 |
| --- | --- | --- | --- |
| `within_noise_candidate` | 可用 `conditional-upgrade` 句块 | 允许重检 `medium-conditional` | 允许把 close02-sensitive 句升到 within-noise 口径 |
| `outside_noise_red_flag` | 用 `conditional-negative` 句块 | 仍冻结 `weak` | 摘要保持保守，不升 stronger claim |
| 空值/不明确 | 仍视为无新 artifact | 仍冻结 `weak` | 摘要保持当前句 |

## 3. 三条分支

### 3.1 分支 A: 仍无新 dated artifact

这是默认分支。

不要改:

- `paper/main_v2.tex` 两处 `\pending` 的强口径
- Gate-2 出口
- abstract 中 close02-sensitive 句的强度

只允许做:

- 更新 sync note
- 更新 closeout CSV 的状态说明
- 继续维持 `weak-default`

### 3.2 分支 B: 新工件支持 `within_noise_candidate`

这时允许触发的变化是“条件升级”，不是无限制升级。

可做:

1. 正文中把 ML1M/ATG 红旗归因从 `default-safe` 换成 `conditional-upgrade`
2. limitations 中对应句换成 `conditional-upgrade`
3. Gate-2 当天允许重检是否进入 `medium-conditional`
4. abstract 中唯一 close02-sensitive 句可升级到 within-noise 版本

仍不能做:

- 直接写 `strong`
- 写超出 freeze memo 的“全面平价已被端到端证明”

### 3.3 分支 C: 新工件支持 `outside_noise_red_flag`

这时不是“没用”，而是把红旗从“待定”变成“已测得仍在噪声外”。

应做:

1. 正文改成 `conditional-negative`
2. limitations 改成 `conditional-negative`
3. Gate-2 直接维持 `weak`
4. 摘要保持保守句，最多把“open implementation question”说得更明确，但不升格为 stronger theorem claim

## 4. 修改顺序

任何分支都按这个顺序改，避免口径不同步。

### Step 1: 先落数据证据

先更新:

- `docs/reports/data/<dated-close02-dir>/...`
- 如有需要，补一份新的本地 audit / sync note

目标:

- 让 dated artifact 先成为论文之外的独立证据源

### Step 2: 再更新措辞辅助文档

更新:

- `docs/reports/2026-07-09-main-v2-wording-patches-cn.md`
- `docs/reports/2026-07-09-abstract-freeze-candidate-cn.md`
- `docs/reports/2026-07-09-gate2-evidence-packet-cn.md`

目标:

- 先把“该换哪一句”写清楚，再动正文

### Step 3: 再改主稿

更新:

- `paper/main_v2.tex`
- `paper/main_v2_zh.md`

只改 close02-sensitive 位置，不顺手扩写别的段落。

### Step 4: 最后改台账

更新:

- `issues/2026-07-06_evidence-priced-schedule-and-closeout.csv`

至少同步:

- `CLOSE-02`
- `CLOSE-05`
- `CLOSE-06`
- `CLOSE-07`

## 5. 需要触碰的文件清单

### 必改

- `paper/main_v2.tex`
- `issues/2026-07-06_evidence-priced-schedule-and-closeout.csv`

### 视分支大概率会改

- `paper/main_v2_zh.md`
- `docs/reports/2026-07-09-main-v2-wording-patches-cn.md`
- `docs/reports/2026-07-09-abstract-freeze-candidate-cn.md`
- `docs/reports/2026-07-09-gate2-evidence-packet-cn.md`

### 视需要补强

- `docs/reports/data/2026-07-09-close02-ml1m-noise-floor-sync-note.md`
- 新 dated close02 audit / decision memo

## 6. 论文中的实际改点

### `paper/main_v2.tex`

当前已知最关键的 close02-sensitive 位置:

- `line 659`
- `line 867`

另外 close02 还会影响:

- abstract 中唯一敏感句
- Gate-2 是否允许启用 upgrade-only 句

### `paper/main_v2_zh.md`

需要同步的是语义，不一定是一字一句直译，但不能出现:

- 英文升格
- 中文仍停留在旧保守版

## 7. Gate-2 联动规则

`CLOSE-02` 落地后，不代表 `CLOSE-05` 自动完成。

正确顺序是:

1. `CLOSE-02` 给出 dated artifact
2. 判断 `decision_line`
3. 把它带入 `CLOSE-05`
4. 由 Gate-2 在 2026-07-14 选择最终出口

所以:

- `within_noise_candidate` 只是让 `medium-conditional` 变得可讨论
- 不是自动批准 `medium`

## 8. 摘要联动规则

摘要只受一条 close02-sensitive 句影响。

因此:

- `within_noise_candidate`
  - 允许替换这 1 句
- `outside_noise_red_flag`
  - 摘要大概率维持现句
- 无新 artifact
  - 摘要必须维持现句

不要在摘要里做比正文更强的升级。

## 9. 最终检查清单

工件落地并完成回填后，至少检查:

- [ ] 新 close02 目录是 dated artifact，而不是 sync note
- [ ] `decision_line` 已被明确读取
- [ ] wording patch 文档已同步到正确分支
- [ ] `main_v2.tex` 与 `main_v2_zh.md` 口径一致
- [ ] Gate-2 证据包已更新到对应分支
- [ ] closeout CSV 已记录新的本地证据路径与分支结论
- [ ] 没有在无证据处偷写 `within the measured host noise floor`

## 10. 一句话结论

`CLOSE-02` 一旦真正落地，最危险的不是“没有句子可写”，而是“同时改正文、摘要、Gate-2、台账时发生分支错位”。这份手册的作用，就是把那次更新压缩成一套固定顺序的联动动作。
