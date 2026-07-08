# CLOSE-08 投稿前终审执行手册

日期: 2026-07-09

用途:

- 服务 `CLOSE-08`
- 在 2026-07-26 前后按固定流程执行 pre-submission vision review
- 把 review 输入、检查项、日志产物和 follow-up 追加方式提前定死

## 1. 这一步的目标

`CLOSE-08` 要回答的不是“论文看起来差不多了吗”，而是:

1. 当前 `main_v2` 版本是否仍受 Family D freeze discipline 约束
2. Gate-2 出口是否与正文/摘要/limitations 完全一致
3. `g==0` 等价证据、各 Gate verdict、Prop-6 暂停、占位符清零、摘要-全文漂移，这五类风险是否都被逐项检查
4. 若发现 gap，是否能立刻追加 follow-up issue，而不是含糊通过

## 2. 触发前提

只有在下面条件满足后才正式执行:

1. `CLOSE-02` 已闭环或其缺口已被诚实记录成最终状态
2. `CLOSE-05` 已冻结 Gate-2 出口
3. `CLOSE-06` 已完成 abstract 提交并记录 submission id
4. 除 `CLOSE-07` 外，其余 CLOSE 行均已 closed 或 documented-gap

如果上述条件不满足:

- 不启动正式 `CLOSE-08`
- 只允许更新 preflight 状态说明

## 3. 需要打开的文件

### 必开

- `issues/2026-07-06_evidence-priced-schedule-and-closeout.csv`
- `docs/reports/2026-07-04-family-d-claim-freeze-cn.md`
- `docs/reports/2026-07-09-gate2-evidence-packet-cn.md`
- `docs/reports/2026-07-09-close02-artifact-arrival-playbook-cn.md`
- `docs/reports/2026-07-09-abstract-freeze-and-submission-runbook-cn.md`
- `docs/reports/data/2026-07-09-main-v2-regression-wording-audit.md`
- `docs/reports/2026-07-09-main-v2-placeholder-inventory-cn.md`
- `paper/main_v2.tex`
- `paper/main_v2_zh.md`

### 如已存在则一起打开

- `docs/reports/data/2026-07-14-gate2/gate2_report_zh.md`
- `docs/reports/data/2026-07-20-abstract-submission/abstract_submission_record.md`

## 4. 审查输入边界

### 允许作为审查输入的材料

1. dated artifact
2. closeout CSV 当前状态
3. 当前主稿与中文镜像
4. Gate-2 报告
5. abstract submission record
6. 已有 audit 文档

### 不允许作为唯一依据的材料

1. 口头结论
2. handoff note 中未 dated 的判断
3. “应该已经提交了”这类状态推断

## 5. 五项正式检查

### Check 1: `g==0` 等价证据是否是 numeric against real core path

要检查:

1. 是否存在真实数值证据
2. 是否不是只靠注释、推理或设计意图
3. 证据是否来自真实 core path，而不是替代路径

### Check 2: Gate 0 / 0-v2 / 1 / 2 verdict 是否都引用 dated artifact，且 claim strength 与 Gate-2 出口一致

要检查:

1. 每个 Gate verdict 是否有 dated artifact
2. 正文 claims 是否没有超过 Gate-2 冻结出口
3. 是否出现“Gate-2 已弱冻结，但正文局部写成中强口径”

### Check 3: Prop-6 empirical wording 是否仍暂停，除非 `CLOSE-02` 已书面解除红旗

要检查:

1. 若 `CLOSE-02` 未给出升级依据，正文是否仍保持暂停口径
2. 是否有偷渡进正文的 stronger empirical reduction claim

### Check 4: 论文是否无 pending 宏，且 respects forbidden-claim list

要检查:

1. `\pending`
2. `\pnum`
3. `\pfig`
4. Family D forbidden phrases

### Check 5: submitted abstract 与 full paper 是否无实质漂移

要检查:

1. 冻结摘要与 OpenReview 提交摘要一致
2. 提交摘要与 `main_v2.tex` 当前摘要一致
3. 没有“摘要更强 / 正文更弱”或反过来的 qualitative drift

## 6. 执行顺序

### Step 1: 先检查触发前提

若不满足，记录:

- `review_not_started_reason:<...>`

并退出正式 review。

### Step 2: 收集固定输入

把:

- Gate-2 报告
- abstract submission record
- 最新主稿
- latest audit docs

放到同一批检查输入里。

### Step 3: 发起 same-model sub-agent review

目标不是让 sub-agent 自由发挥，而是让它严格围绕五项检查给:

- pass / fail
- artifact citation
- follow-up recommendation

### Step 4: 回写 review log

统一写入:

- `docs/reports/data/2026-07-26-close08/close08_review_log.md`

### Step 5: 若发现 gap，追加 follow-up issue

原则:

1. gap 必须变成可执行 issue
2. 当前 `CLOSE-08` 不得因为发现 gap 而含糊通过
3. follow-up issue 之后应追加新的 review 行

## 7. 输出产物

### 必产

- `docs/reports/data/2026-07-26-close08/close08_review_log.md`

### 可选辅助产物

- 新增的 follow-up issue
- 新的 drift / placeholder / wording audit

## 8. 发现 gap 时的处理规则

如果某项 fail:

1. 记录哪一项 fail
2. 给出证据路径
3. 指定影响面:
   - 正文
   - 摘要
   - Gate-2
   - supplementary
4. 追加 follow-up issue
5. 不把 `CLOSE-08` 标成通过

## 9. 最小检查清单

- [ ] 触发前提已满足
- [ ] 五项检查都执行
- [ ] 每项都有 artifact citation
- [ ] review log 已生成
- [ ] 如有 fail，已追加 follow-up issue
- [ ] closeout CSV 已同步 review 结果

## 10. 一句话结论

`CLOSE-08` 的价值不是“再看一遍论文”，而是用一套固定的五项审查把冻结 discipline、Gate-2 出口、摘要-全文一致性和占位符清零一起做最终闭环。
