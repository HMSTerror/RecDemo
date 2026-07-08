# AAAI-27 近 7 天训练-写稿协同执行时间线

日期: 2026-07-09

适用范围:

- closeout 主线: `issues/2026-07-06_evidence-priced-schedule-and-closeout.csv`
- 主稿: `paper/main_v2.tex`
- 当前窗口: 2026-07-09 至 2026-07-20

## 1. 一句话目标

在不等待所有远端实验全部落地的前提下，把当前工作流推进到:

1. `CLOSE-02` 给出足以约束正文与摘要措辞的权威结论，或至少把“仍无新 dated artifact”记录为可审计事实。
2. `CLOSE-05` 在 2026-07-14 准时冻结 Gate-2 出口。
3. `CLOSE-06` 在 2026-07-18 前完成标题与摘要冻结，并在 2026-07-20 前完成 abstract submission。

## 2. 当前硬约束

### 2.1 绝对硬节点

- 2026-07-14: `CLOSE-05` Gate-2 冻结
- 2026-07-18: 标题与摘要冻结
- 2026-07-20: abstract submission
- 2026-07-27: 全文提交
- 2026-07-30: supplementary + reproducibility checklist

### 2.2 当前主 blocker

- `CLOSE-02` 仍是唯一会同时影响:
  - `main_v2.tex` 两处剩余关键 `\pending`
  - Gate-2 能否从 `weak` 升到 `medium-conditional`
  - abstract 中唯一 close02-sensitive 句子是否允许升级

### 2.3 当前必须坚持的写作边界

- 无新 dated close02 artifact:
  - 保持 `Family D`
  - 保持 `weak-default`
  - 不写 `within the measured host noise floor`
- `CLOSE-03/04` 即使进展慢，也不能反过来阻塞 `CLOSE-05/06`

### 2.4 资源边界

- 远端大跑数同时不超过 3 个
- 本地不能把“等待远端结果”当成主要工作
- 一旦等待超过 6 小时，必须切回:
  - 论文回填
  - 证据整理
  - Gate-2/abstract 文案预装

## 3. 三条并行工作流

### 3.1 流 A: 训练与实验监控

只盯这些和投稿主线直接相关的实验:

1. `CLOSE-02`
2. `CLOSE-04`
3. `CLOSE-03` 条件分支

不在 7/20 前主动扩张到新的消融或高成本增强实验。

### 3.2 流 B: 论文与文案冻结

持续围绕:

1. `paper/main_v2.tex`
2. `paper/main_v2_zh.md`
3. `docs/reports/2026-07-09-main-v2-wording-patches-cn.md`
4. `docs/reports/2026-07-09-abstract-freeze-candidate-cn.md`

原则是“预制替换块”，而不是等实验完再临场重写。

### 3.3 流 C: 证据与台账

持续维护:

1. closeout CSV 中 `notes`
2. `docs/reports/data/*` dated artifacts
3. closeout status / gate packet / checklist 类文档

原则是“先把证据落到 dated artifact，再让论文引用它”。

## 4. 每日节奏

### 每 2-3 小时检查一次

最小检查项:

1. `CLOSE-02` 是否出现新的 dated artifact
2. `CLOSE-04` 是否有新的 wrapper-level 结果或 dated table
3. 正文/摘要是否存在可以提前冻结的句子块

### 每个检查周期后的动作

- 若有新 artifact:
  - 先更新 dated report / inventory / wording patch
  - 再更新正文
- 若无新 artifact:
  - 不空等
  - 立即切到 Gate-2 包、abstract freeze、supplement checklist、figure prompt 等写作/整理工作

## 5. 日期级时间线

### 2026-07-09

主目标:

1. 明确 closeout 主线与硬 deadline
2. 把 `CLOSE-02` 的“无新 dated artifact 不升级”规则写死
3. 把 Gate-2 与 abstract 的文案替换块全部预装

今日应完成的交付:

- project understanding 文档
- 本执行时间线文档
- `CLOSE-02` / `CLOSE-05` / `CLOSE-06` 关联关系固定说明

### 2026-07-10

主目标:

1. 对 `CLOSE-03` 做条件分支判定
2. 如果 L20 / GPU 条件不满足，准备 documented-gap 路径
3. 继续追 `CLOSE-02`

必须做的判断:

- `CLOSE-03`:
  - 可跑: 保留 rerun 分支
  - 不可跑: 按 documented-gap 收口，不再让它占用主线注意力

写作动作:

- 保持 robustness 段落显式 scoped
- 不把 `CLOSE-03` 当作 abstract 依赖

### 2026-07-11 至 2026-07-13

主目标:

1. 全力争取 `CLOSE-02` 形成新 dated artifact
2. 若 `CLOSE-04` 继续推进，则只做监控与结果接收
3. 提前把 7/14 Gate-2 冻结所需证据包整理完整

必须准备好的材料:

- Gate-1 读数
- SPRINT-07 control 表
- `CLOSE-02` 最新可用状态
- Family D freeze memo
- `main_v2.tex` 中待替换句位置

止损规则:

- 到 2026-07-13 晚上仍无新 dated close02 artifact:
  - 直接按 `weak-default` 准备 Gate-2 冻结
  - 不再幻想 `medium`

### 2026-07-14

主目标:

1. 完成 `CLOSE-05` Gate-2 冻结
2. 选择且只选择一个出口:
  - `weak`
  - `medium-conditional`
  - 禁止漂移到更强口径

当天必须落地的交付:

- dated Gate-2 决策包
- 与 freeze memo 一致的 claim wording
- 对摘要能否升级的明确判断

### 2026-07-15 至 2026-07-18

主目标:

1. 完成 `CLOSE-06` 标题与摘要冻结
2. 如果 `CLOSE-02` 已落地，则执行对应 wording patch
3. 如果 `CLOSE-02` 仍未落地，则维持保守句，不再拖延冻结

这几天不该做的事:

- 不新增与 abstract 无关的大实验
- 不为 baseline 细节重写 setup 主段
- 不把 figure 占位清零当成摘要冻结前置条件

### 2026-07-19 至 2026-07-20

主目标:

1. 最终核对 OpenReview abstract 版本
2. 确保 abstract 与 `main_v2.tex` 无实质漂移
3. 完成 abstract submission

最终检查:

- frozen 主句一致
- boundary 句一致
- 无 forbidden-list phrasing
- close02 句与 Gate-2 冻结结论一致

### 2026-07-21 之后到全文提交

主目标转为:

1. `CLOSE-07` 占位清零
2. figure 生成与 PDF 编译
3. supplementary 打包
4. `CLOSE-08` 最终审查

## 6. 行动优先级矩阵

| 优先级 | 任务 | 为什么现在做 | 不做的代价 |
| --- | --- | --- | --- |
| P0 | `CLOSE-02` artifact / 状态确认 | 决定正文、Gate-2、摘要 | 7/14 与 7/20 两个节点都会失去确定性 |
| P0 | `CLOSE-05` Gate-2 证据包预装 | 7/14 是硬点，不能当天临时拼 | 冻结结论会拖延或漂移 |
| P0 | `CLOSE-06` abstract freeze 候选维护 | 7/20 很近，只剩一条敏感句需要条件替换 | 到点仍在“继续写”，而不是“可以提交” |
| P1 | `CLOSE-03` 条件判断 | 必须尽快决定它是不是 documented gap | 会持续偷走主线注意力 |
| P1 | `CLOSE-04` baseline 监控 | 有助 setup / appendix，但不阻塞 abstract | 如果过度投入，会挤压 P0 |
| P2 | 额外 baseline / 新消融 | 对 submission 不关键 | 高概率耗尽 GPU 与上下文预算 |

## 7. 切换规则

### 7.1 从“等实验”切到“写稿”

满足任一条件就切:

1. 6 小时内无新 artifact
2. 远端状态无法本地验证
3. 当前 blocker 不在本机可解决范围

切换后优先做:

1. Gate-2 决策包
2. abstract freeze 候选
3. wording patch
4. supplement checklist

### 7.2 从“写稿”切回“结果回填”

满足任一条件就切:

1. `CLOSE-02` 产生新的 dated artifact
2. `CLOSE-04` 产生新的 dated table
3. `CLOSE-03` 分支状态明确

切换顺序:

1. 先落 dated report
2. 再更新 inventory / wording patch
3. 最后改 `main_v2.tex`

## 8. 今日到 7/20 的最小成功标准

到 2026-07-20 前，至少应保证:

1. `CLOSE-05` 已冻结
2. `CLOSE-06` 的标题与摘要已冻结并可提交
3. `CLOSE-02` 要么已有新 dated artifact，要么“仍无新 artifact”的保守路径已被明文接管
4. `CLOSE-03/04` 不再作为 abstract 级 blocker

## 9. 最后的执行提醒

当前最容易犯的错误不是“实验少做一点”，而是:

1. 一边等待远端，一边不提前固化文案分支
2. 把 `CLOSE-03/04` 的价值误判成高于 `CLOSE-02/05/06`
3. 到 7/14 或 7/20 才开始做结论冻结

未来几天的正确姿势是:

- 远端结果来了就吃结果
- 远端结果没来就继续固化 submission path
- 所有文字都默认服务于“按时可投”，而不是“把所有实验都做到理想状态”
