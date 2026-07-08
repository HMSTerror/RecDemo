# 2026-07-14 Gate-2 冻结当天执行手册

日期: 2026-07-09

用途:

- 服务 `CLOSE-05`
- 在 2026-07-14 当天按固定顺序读取证据、判定出口、更新论文和台账
- 避免临场在 `weak / medium-conditional` 之间反复争论

## 1. 当天的唯一目标

在 2026-07-14 当天，基于 **已有 dated artifact**，从:

- `weak`
- `medium-conditional`

中选择且只选择一个出口，并把选择结果同步到:

1. Gate-2 报告
2. `paper/main_v2.tex`
3. `paper/main_v2_zh.md`
4. closeout CSV

`strong` 不在当天的现实候选范围内。

## 2. 开始前先确认的边界

### 2.1 允许影响 Gate-2 出口的证据

优先级从高到低:

1. `docs/reports/data/2026-07-06-gate1/sprint05_gate1_report_zh.md`
2. 新的 dated `CLOSE-02` noise-floor artifact
3. `docs/reports/data/2026-07-06-sprint07/sprint07_control_report_zh.md`

### 2.2 不允许单独抬升出口的证据

以下最多只作 supporting evidence:

- `CLOSE-03` 腐蚀链结果
- `CLOSE-04` baseline 结果
- `diag rerun`
- handoff note
- 单 seed 晚到读数

### 2.3 冻结规则

- 没有新的 dated `CLOSE-02` artifact:
  - 直接冻结 `weak`
- 有新的 dated `CLOSE-02` artifact 且 `decision_line=within_noise_candidate`:
  - 才允许重检 `medium-conditional`
- 有新的 dated `CLOSE-02` artifact 但 `decision_line=outside_noise_red_flag`:
  - 仍冻结 `weak`

## 3. 当天要打开的文件

### 必开

- `docs/reports/2026-07-09-gate2-evidence-packet-cn.md`
- `docs/reports/2026-07-09-close02-artifact-arrival-playbook-cn.md`
- `docs/reports/2026-07-09-main-v2-wording-patches-cn.md`
- `docs/reports/2026-07-09-abstract-freeze-candidate-cn.md`
- `paper/main_v2.tex`
- `paper/main_v2_zh.md`
- `issues/2026-07-06_evidence-priced-schedule-and-closeout.csv`

### 若有新 close02 工件

- `docs/reports/data/<new-close02-dir>/close02_ml1m_noise_floor_report.json`
- `docs/reports/data/<new-close02-dir>/close02_ml1m_noise_floor_report_zh.md`
- `docs/reports/data/<new-close02-dir>/close02_ml1m_noise_floor_table.csv`

## 4. 当天的顺序

### Step 1: 锁定默认出口

先读 Gate-1 官方案读数，默认记作:

- `default_exit = weak`

当天任何后续动作都应理解为“是否有足够证据离开默认出口”。

### Step 2: 检查是否出现新的 dated `CLOSE-02` 工件

检查项:

1. 是否存在新的 dated close02 目录
2. 是否同时有:
   - report json
   - report zh
   - table csv
3. 是否能从报告里直接读到 `decision_line`

若任一项缺失:

- 直接进入 `weak` 冻结分支

### Step 3: 读取 `decision_line`

只接受三类结果:

1. `within_noise_candidate`
2. `outside_noise_red_flag`
3. 空值 / 无法判定

分支:

- `within_noise_candidate`
  - 进入 `medium-conditional` 复核
- `outside_noise_red_flag`
  - 回到 `weak`
- 空值 / 无法判定
  - 回到 `weak`

### Step 4: 选择正文句块

从 `docs/reports/2026-07-09-main-v2-wording-patches-cn.md` 中按分支选择:

- `default-safe`
- `conditional-upgrade`
- `conditional-negative`

只替换 close02-sensitive 位置，不重写周边段落。

### Step 5: 选择摘要句块

只改 abstract 中唯一 close02-sensitive 句:

- 没有新 dated artifact:
  - 保持当前句
- `within_noise_candidate`:
  - 允许升级到 within-noise 版本
- `outside_noise_red_flag`:
  - 保持保守版本

### Step 6: 生成 Gate-2 报告

使用模板:

- `docs/reports/data/2026-07-14-gate2/gate2_report_zh.template.md`

生成正式文件:

- `docs/reports/data/2026-07-14-gate2/gate2_report_zh.md`

### Step 7: 更新主稿和台账

至少同步:

- `paper/main_v2.tex`
- `paper/main_v2_zh.md`
- `issues/2026-07-06_evidence-priced-schedule-and-closeout.csv`

相关行:

- `CLOSE-02`
- `CLOSE-05`
- `CLOSE-06`
- `CLOSE-07`

### Step 8: 交给用户做最终拍板

当天仍应把最终出口与证据表呈给用户确认。

用户拍板前:

- 可以准备所有文本
- 可以更新报告与台账草案
- 不应把未经用户确认的升级出口写成既成事实

## 5. 分支动作表

| 分支 | Gate-2 出口 | 正文 | 摘要 | 台账 |
| --- | --- | --- | --- | --- |
| 无新 dated artifact | `weak` | `default-safe` | 保持当前句 | 记录“仍无新 dated artifact” |
| `within_noise_candidate` | 可讨论 `medium-conditional` | `conditional-upgrade` | 升级敏感句 | 记录“artifact 支持 within-noise 候选” |
| `outside_noise_red_flag` | `weak` | `conditional-negative` | 保守句 | 记录“artifact 显示仍在噪声外” |

## 6. 当天应避免的错误

1. 把单 seed 晚到读数当成正式 close02 dated artifact
2. 在没有 `decision_line` 的情况下自行解释噪声地板
3. 因为 `CLOSE-03/04` 有进展，就越级抬升 `weak`
4. 在摘要里写得比正文更强
5. 先改论文，再补 Gate-2 报告和台账

## 7. 最小检查清单

- [ ] Gate-1 默认出口已明确为 `weak`
- [ ] 新 close02 artifact 是否存在，已被明确回答
- [ ] `decision_line` 已读取
- [ ] 正文句块已按分支选择
- [ ] 摘要敏感句已按分支选择
- [ ] Gate-2 报告已生成
- [ ] 主稿与中文镜像已同步
- [ ] closeout CSV 已同步
- [ ] 最终出口已呈给用户确认

## 8. 一句话结论

2026-07-14 当天最重要的不是“临场判断论文该怎么写”，而是按固定顺序把 `CLOSE-02` 的新旧状态映射到现成分支，再把分支结果写回报告、正文、摘要和台账。
