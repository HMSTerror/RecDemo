# 用户动作清单

日期: 2026-07-09

用途:

- 把 closeout 主线里必须由用户亲自完成的动作单独抽出来
- 明确每个动作的 deadline、前置输入、用户输出、以及完成后需要回填到哪里

## 1. 一句话目标

把“只有用户能做的事”从各份 runbook 中分离出来，避免:

1. 到 deadline 前才发现某一步必须登录 OpenReview
2. agent 已经准备好材料，但用户不知道下一步该点什么
3. 用户完成动作后，没有把关键结果回填到台账

## 2. 总原则

### 2.1 用户必须亲自完成的动作

1. Gate-2 最终出口拍板
2. OpenReview 注册/登录/作者信息填写
3. abstract 最终点击提交
4. full paper 最终点击提交
5. supplementary / checklist 最终上传
6. 对外邮件发送

### 2.2 agent 负责先准备好的内容

1. 证据包
2. 文案冻结版本
3. 报告模板
4. drift check / wording check / placeholder check
5. 台账回填位置

### 2.3 用户完成动作后必须回传的信息

最关键的只有三类:

1. 你拍板的最终结论
2. 平台生成的 submission id
3. 实际提交时间

## 3. 时间线清单

### A. 2026-07-14: Gate-2 最终出口确认

#### 用户要做什么

1. 阅读 agent 准备好的 Gate-2 证据表与推荐出口
2. 在 `weak` 与 `medium-conditional` 之间做最终拍板

#### agent 事先要准备什么

1. `docs/reports/2026-07-09-gate2-evidence-packet-cn.md`
2. `docs/reports/2026-07-09-gate2-freeze-day-runbook-cn.md`
3. `docs/reports/data/2026-07-14-gate2/gate2_report_zh.md` 或其模板填充版

#### 你需要回传什么

1. 最终出口:
   - `weak`
   - `medium-conditional`
2. 如与默认建议不同，说明“按哪条偏离理由拍板”

#### 完成后要回填到哪里

- `issues/2026-07-06_evidence-priced-schedule-and-closeout.csv`
  - `CLOSE-05 notes`

### B. 2026-07-18: 标题与摘要冻结确认

#### 用户要做什么

1. 确认最终标题
2. 确认最终英文 abstract
3. 确认 close02-sensitive 句分支

#### agent 事先要准备什么

1. `docs/reports/2026-07-09-abstract-freeze-candidate-cn.md`
2. `docs/reports/2026-07-09-abstract-freeze-and-submission-runbook-cn.md`
3. 经过 drift check 的最终 freeze 文本

#### 你需要回传什么

1. “标题确认通过”
2. “摘要确认通过”
3. 若改了标题或摘要，给出最终版本文本

#### 完成后要回填到哪里

- `CLOSE-06 notes`

### C. 2026-07-20: OpenReview abstract submission

#### 用户要做什么

1. 登录 OpenReview
2. 填写/确认作者信息
3. 粘贴已冻结标题与 abstract
4. 点击提交

#### agent 事先要准备什么

1. 冻结标题
2. 冻结 abstract
3. `docs/reports/data/2026-07-20-abstract-submission/abstract_submission_record.template.md`
4. 提交前 drift check 结果

#### 你需要回传什么

1. `submission_id`
2. 实际提交时间
3. 如果平台上最终文本和本地冻结文本有任何差异，要把最终平台版本发回来

#### 完成后要回填到哪里

- `CLOSE-06 notes`
- 如需要，填入 `abstract_submission_record.md`

### D. 2026-07-27: full paper submission

#### 用户要做什么

1. 登录投稿平台
2. 上传最终匿名 PDF
3. 确认元数据、标题、摘要、作者信息
4. 点击提交

#### agent 事先要准备什么

1. 最终匿名 PDF
2. page-limit / anonymity / forbidden-claim / placeholder 清零检查结果
3. 如已完成，`CLOSE-08` 终审结论

#### 你需要回传什么

1. `full_paper_submission_id` 或平台记录编号
2. 实际提交时间
3. 若平台提示任何格式问题，原样贴回

#### 完成后要回填到哪里

- `CLOSE-07 notes`

### E. 2026-07-30: supplementary + reproducibility checklist 上传

#### 用户要做什么

1. 上传 supplementary bundle
2. 上传 reproducibility checklist
3. 确认与正文提交版本匹配

#### agent 事先要准备什么

1. supplementary bundle checklist
2. 最终打包目录或压缩包
3. checklist 完整版本

#### 你需要回传什么

1. 上传完成时间
2. 若平台有附件编号，也一并返回
3. 若平台提示缺文件或命名错误，原样贴回

#### 完成后要回填到哪里

- `CLOSE-07 notes`

### F. 对外邮件 / 申请材料发送

#### 用户要做什么

1. 实际发送邮件
2. 确认收件人、附件和最终版本

#### agent 事先要准备什么

1. 最终文案
2. 附件路径
3. 版本说明

#### 你需要回传什么

1. 发送时间
2. 实际使用的版本名称

#### 完成后要回填到哪里

- 对应 future_work 或 BRIDGE 行 notes

## 4. 极简回传模板

你完成任一用户动作后，只要回一条这样的消息就够:

```text
动作: <Gate-2确认 / abstract提交 / full paper提交 / supplementary上传 / 邮件发送>
时间: <timestamp>
结果: <出口 or submission_id or 平台编号>
备注: <若无则写 none>
```

## 5. 现在最应该留意的三件事

1. `2026-07-14` 的 Gate-2 拍板
2. `2026-07-18` 的标题与摘要冻结确认
3. `2026-07-20` 的 OpenReview abstract 提交

这三件事是当前最靠前、最容易因为“以为 agent 能代做”而耽误的动作。

## 6. 一句话结论

如果把 closeout 主线看成一条人机协同链，那么这份清单就是专门给“你必须亲自点的按钮”做的总入口。
