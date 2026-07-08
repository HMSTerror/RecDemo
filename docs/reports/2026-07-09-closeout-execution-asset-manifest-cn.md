# Closeout 执行资产清单

日期: 2026-07-09

对应机器可读清单:

- `docs/reports/data/2026-07-09-closeout-execution-asset-manifest.csv`

## 1. 这份清单解决什么问题

到 2026-07-09 为止，项目里已经有一批直接服务 `CLOSE-02/05/06/07/08` 的执行资产，但它们分散在:

- `docs/reports/`
- `docs/reports/data/`
- `issues/*.csv`

这份清单的作用不是再解释业务逻辑，而是把“哪份文档在什么时候用、服务哪条 closeout 行”压缩成一眼能扫完的目录。

## 2. 使用方式

### 人工接手

按下面顺序:

1. `project_map`
2. `execution_timeline`
3. 对应 closeout 行的专属 runbook / template

### 会话恢复

优先看:

1. closeout 总台账
2. 本清单 csv
3. 当前所处日期节点对应的 runbook

## 3. 当前最重要的资产

### A. 总览层

| artifact_id | 用途 |
| --- | --- |
| `project_map` | 解释“项目现在到底是什么、卡在哪里” |
| `execution_timeline` | 解释 7/9-7/20 应该怎么推进 |

### B. `CLOSE-02` 联动层

| artifact_id | 用途 |
| --- | --- |
| `close02_arrival_playbook` | 新 dated close02 工件一落地，就告诉你该改哪一支 |
| `wording_patches` | 具体英文句块库 |

### C. `CLOSE-05` Gate-2 层

| artifact_id | 用途 |
| --- | --- |
| `gate2_packet` | 说明哪些证据有资格影响 Gate-2 |
| `gate2_day_runbook` | 7/14 当天的固定顺序 |
| `gate2_report_template` | 最终 dated Gate-2 报告骨架 |

### D. `CLOSE-06` 摘要层

| artifact_id | 用途 |
| --- | --- |
| `abstract_freeze_candidate` | 当前摘要冻结候选 |
| `abstract_day_runbook` | 7/18-7/20 冻结与提交顺序 |
| `abstract_submission_template` | 记录 submission id 与冻结文本 |

### E. `CLOSE-07` 回填层

| artifact_id | 用途 |
| --- | --- |
| `placeholder_inventory` | 剩余占位都在哪 |
| `wording_audit` | 当前 wording 是否还在 Family D 边界内 |
| `numeric_provenance_audit` | 已填数字是否有 dated artifact 来源 |
| `dataset_stats_audit` | setup 统计表的来源与限制 |
| `supplement_checklist` | 补充材料还缺什么 |

### F. `CLOSE-08` 终审层

| artifact_id | 用途 |
| --- | --- |
| `close08_runbook` | 投稿前终审的五项正式检查 |
| `close08_log_template` | same-model review log 骨架 |

## 4. 当前最短接手路径

如果今天只想最快进入执行态，读这 5 个就够:

1. `issues/2026-07-06_evidence-priced-schedule-and-closeout.csv`
2. `docs/reports/2026-07-09-project-understanding-and-priority-map-cn.md`
3. `docs/reports/2026-07-09-7day-training-writing-execution-timeline-cn.md`
4. `docs/reports/2026-07-09-close02-artifact-arrival-playbook-cn.md`
5. 按当前日期节点选择:
   - 7/14 前看 `gate2_day_runbook`
   - 7/18-7/20 看 `abstract_day_runbook`
   - 7/26 前看 `close08_runbook`

## 5. 一句话结论

这份清单不是新增流程，而是把已经形成的 closeout 执行资产压成一个集中入口，避免后面继续靠上下文记忆“哪份文档服务哪一条 CLOSE 行”。
