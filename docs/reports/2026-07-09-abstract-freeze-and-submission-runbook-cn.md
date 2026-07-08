# CLOSE-06 摘要冻结与提交执行手册

日期: 2026-07-09

用途:

- 服务 `CLOSE-06`
- 覆盖 2026-07-18 标题/摘要冻结与 2026-07-20 abstract submission
- 把“冻结什么、谁来操作、提交后怎么回填”写成固定流程

## 1. 这一步的真实目标

`CLOSE-06` 不是“继续打磨摘要直到更漂亮”，而是:

1. 在 2026-07-18 前冻结标题与摘要
2. 确保冻结文本与 `paper/main_v2.tex` 无实质漂移
3. 在 2026-07-20 前完成 OpenReview abstract submission
4. 把 submission id 与最终文本状态写回台账

## 2. 当前已知边界

### 2.1 已可冻结的部分

根据:

- `paper/main_v2.tex`
- `docs/reports/2026-07-09-abstract-freeze-candidate-cn.md`
- `docs/reports/2026-07-04-family-d-claim-freeze-cn.md`

当前绝大多数 abstract 句子已经可以冻结。

### 2.2 唯一仍受 `CLOSE-02` 影响的部分

只剩一条 close02-sensitive 句子仍需要在三种状态间选一:

1. 维持当前保守句
2. 升级到 within-noise 版本
3. 维持保守但明确 outside-noise

这条句子的选择权不在 abstract 自身，而在:

- `CLOSE-02`
- `CLOSE-05`

### 2.3 用户专属动作

根据 handoff playbook，以下属于用户动作:

1. OpenReview 注册
2. 作者信息填写
3. abstract 最终点击提交
4. Gate-2 出口的最终确认

本地代理能做的是:

1. 准备最终文本
2. 准备 drift 检查
3. 准备提交记录模板
4. 提交后把 submission id 写回 CSV

## 3. 需要打开的文件

### 冻结前

- `paper/main_v2.tex`
- `paper/main_v2_zh.md`
- `docs/reports/2026-07-09-abstract-freeze-candidate-cn.md`
- `docs/reports/2026-07-09-main-v2-wording-patches-cn.md`
- `docs/reports/2026-07-09-close02-artifact-arrival-playbook-cn.md`
- `docs/reports/2026-07-09-gate2-evidence-packet-cn.md`
- `issues/2026-07-06_evidence-priced-schedule-and-closeout.csv`

### 提交记录

- `docs/reports/data/2026-07-20-abstract-submission/abstract_submission_record.template.md`

## 4. 冻结日前的准备顺序

### Step 1: 锁定默认 abstract 文本

从 `paper/main_v2.tex` 抽出当前 abstract，并把它当作默认冻结版本。

### Step 2: 确认 close02-sensitive 句的候选分支

只允许三个状态:

1. `default-safe`
2. `conditional-upgrade`
3. `conditional-negative`

不得临场自由改写。

### Step 3: 做一次漂移检查

检查:

1. abstract 主句是否仍与 freeze memo 一致
2. boundary 句是否仍与 freeze memo 一致
3. 是否出现 forbidden-list phrasing
4. 中文镜像是否仍跟英文主稿对齐

### Step 4: 记录冻结版本

在 2026-07-18 冻结时，至少要记录:

1. 最终标题
2. 最终英文 abstract
3. close02-sensitive 句选择的是哪一支
4. 这份冻结文本对应的主稿路径

## 5. 2026-07-18 冻结日流程

### 情况 A: 没有新 dated `CLOSE-02` 工件

操作:

1. 保持当前保守句
2. 不做 stronger wording 升级
3. 把冻结文本写入 submission record 模板
4. 更新 closeout CSV:
   - `title_abstract_frozen_at:<timestamp>`
   - `abstract_branch:default-safe`

### 情况 B: `CLOSE-02` 工件支持 within-noise

操作:

1. 按 wording patch 把敏感句替换为 within-noise 版本
2. 确认 Gate-2 分支允许这次升级
3. 记录:
   - `abstract_branch:conditional-upgrade`
   - `close02_artifact:<path>`

### 情况 C: `CLOSE-02` 工件支持 outside-noise

操作:

1. 摘要通常保持保守版本
2. 如需更明确，只能沿 `conditional-negative` 句块执行
3. 记录:
   - `abstract_branch:conditional-negative`
   - `close02_artifact:<path>`

## 6. 2026-07-20 提交日流程

### Step 1: 提交前本地核对

必须逐项检查:

- [ ] OpenReview 中准备提交的标题与本地冻结标题一致
- [ ] OpenReview 中准备提交的 abstract 与本地冻结 abstract 一致
- [ ] 没有出现摘要-全文实质漂移
- [ ] close02-sensitive 句与 Gate-2 当下结论一致

### Step 2: 用户执行提交

用户在 OpenReview 上完成:

1. 注册/登录
2. 作者信息确认
3. abstract 粘贴与最终提交
4. 返回 submission id

### Step 3: 本地回填

拿到 submission id 后，立即回填:

- `issues/2026-07-06_evidence-priced-schedule-and-closeout.csv`

至少追加:

- `openreview_id:<id>`
- `abstract_submitted_at:<timestamp>`
- `abstract_branch:<branch>`

必要时也更新:

- `docs/reports/data/2026-07-20-abstract-submission/abstract_submission_record.md`

## 7. 需要回写的对象

### 必改

- `issues/2026-07-06_evidence-priced-schedule-and-closeout.csv`

### 高概率会改

- `paper/main_v2.tex`
- `paper/main_v2_zh.md`
- `docs/reports/data/2026-07-20-abstract-submission/abstract_submission_record.md`

### 仅在分支变化时改

- `docs/reports/2026-07-09-abstract-freeze-candidate-cn.md`
- `docs/reports/2026-07-09-main-v2-wording-patches-cn.md`

## 8. 提交记录里必须出现的字段

1. 冻结标题
2. 冻结 abstract
3. 使用的 abstract 分支
4. close02 工件路径或“none”
5. Gate-2 当下出口
6. OpenReview submission id
7. 提交时间
8. 是否通过 drift check

## 9. 最容易犯的错误

1. 先在 OpenReview 改摘要，再回头改主稿
2. 摘要写得比正文更强
3. 拿用户口头确认代替本地冻结记录
4. 提交后只记了 `submission id`，没记最终文本分支
5. 在没有新 dated `CLOSE-02` 工件时偷写 within-noise

## 10. 最小检查清单

- [ ] 标题已冻结
- [ ] 英文 abstract 已冻结
- [ ] close02-sensitive 句已锁定分支
- [ ] 中文镜像已同步
- [ ] drift check 已通过
- [ ] OpenReview 提交动作已由用户完成
- [ ] submission id 已写回台账

## 11. 一句话结论

`CLOSE-06` 的难点不在于再写一版更好的摘要，而在于把“冻结文本、close02 分支、Gate-2 结论、OpenReview 提交记录”四件事绑成同一条链，避免提交后才发现摘要和主稿已经漂移。
