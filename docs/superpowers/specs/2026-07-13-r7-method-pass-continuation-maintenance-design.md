# r7 后置 method-pass 自动续跑与维护窗口设计

**日期：** 2026-07-13

**状态：** 用户已批准方案 A，等待书面 spec 复核后进入实施计划

**适用服务器：** `zijian@172.18.0.40`（l20）

**维护约束：** 服务器计划于 2026-07-17 升级关闭；保守维护截止点为 2026-07-16 12:00（Asia/Shanghai）

**备份边界：** 用户明确要求暂不执行备份；本设计不创建、复制或删除备份文件

## 1. 目标

在不修改 r7 immutable manifest、不绕过原始 RISK-08 决策、不覆盖任何 frozen artifact 的前提下，为 r7 增加一个独立的 method-pass continuation queue。该队列必须在 r7 正常完成后读取原始 `RISK-08_EXIT.json`，并且仅在出口精确为 `risk_gated_method` 时自动启动 seed=100 后续实验。

设计同时解决服务器计划维护带来的运行中断风险。任何预计无法在维护截止前安全完成的任务不得在截止点之后启动；已完成任务必须可在升级后按同一 manifest、同一 source revision 和同一证据合同恢复，且不得重复运行。

## 2. 不可变上游绑定

continuation queue 不附加到 r7 的 22-task manifest，也不修改 r7 的 task records。它是独立 dated queue root，至少绑定以下上游对象：

| 对象 | 冻结值或路径 |
| --- | --- |
| r7 queue root | `/data/Zijian/goal/aaai27_queue/2026-07-12-risk0607-987eb19-r7` |
| r7 manifest | `queue/queue_seed100.json` |
| r7 manifest SHA-256 | `387636c8c5dc5b09bb9c509db26b0f335ecac3ed1525e3c4bee3289612bb966e` |
| r7 immutable source | `/data/Zijian/goal/RecDemo_aaai27_risk0607_987eb19_r7` |
| r7 finalizer config | `protocol/r7_finalizer_config.json` |
| RISK-08 出口 | `markers/RISK-08_EXIT.json` |
| r7 terminal | `state/TERMINAL.json` |

continuation preflight 必须重新计算并核对上述文件 hash。缺失、损坏、hash 不一致、路径越界、终态矛盾或未知出口都必须 fail closed，后续 GPU 训练数保持为零。

## 3. 解锁状态机

```text
r7 controller running/waiting
        |
        v
r7 active branch 14/14 terminal-pass
        |
        v
original RISK-08 finalizer writes one immutable exit
        |
        +-- risk_gated_method --> validate continuation manifest --> method_pass tasks
        |
        +-- audit_only --------> terminal preserve-only; zero downstream training
        |
        +-- submission_stop ---> terminal preserve-only; zero downstream training
        |
        +-- task_failure ------> terminal preserve-only; zero downstream training
        |
        +-- missing/unknown/hash mismatch --> fail-closed; zero downstream training
```

continuation controller 不得自行重新计算、修改或替代 RISK-08。它只能验证并消费原始 dated exit。任何人工创建的“pass”文本、手工 metrics 汇总或从日志复制的数字都不能解锁下游训练。

## 4. 自动续跑范围与顺序

自动续跑沿用已批准的 Stage D，所有训练随机种子固定为 100。seed 101/102、DiffuRec、BERT4Rec、rescue tuning 和 attempt retry 均不在本队列内。

### 4.1 RISK-13 seed=100 partial wave

第一优先级是四域 host/full matched pairs：

| 数据集 | 臂 | seed | 任务数 |
| --- | --- | ---: | ---: |
| Steam | host、risk-gated full | 100 | 2 |
| ML1M | host、risk-gated full | 100 | 2 |
| Beauty | host、risk-gated full | 100 | 2 |
| ATG | host、risk-gated full | 100 | 2 |

共八个任务。每对必须共享冻结的 split、item mapping、ordered-loader policy、初始化策略、selector、evaluator、bank/hash 和 checkpoint retention contract。该 wave 只能标注为 `seed-100 partial wave`，不能关闭完整三 seed ledger row，也不能产生稳定性或显著性措辞。

如果某数据集已有满足完全相同合同的可复用 seed=100 host/full 工件，continuation 必须先进行 identity audit。只有 split、mapping、revision、配置、selector、evaluator、初始化、bank 和 artifact schema 全部相同才可标为 `artifact_reused`；任一字段不明即重新运行完整 matched pair，禁止选择性复用单臂。

### 4.2 RISK-14 seed=100 mechanism controls

第二优先级为冻结的一个高风险条件和一个低风险条件。条件选择只能由 train-only risk 工件决定，不能读取 validation/test 性能后再挑选。

每个条件的 seed=100 臂为：

1. host；
2. text-anchor-only；
3. global-p；
4. dataset-gate-only；
5. risk-gated full；
6. u-shuffle。

选择记录必须在训练前写成 dated manifest，并包含输入工件路径、hash、排序规则和最终两个条件。任一 arm 缺失时，该条件的机制组标为 incomplete，不得只报告有利子集。

### 4.3 RISK-10 classic baselines

第三优先级为 SASRec、Caser 和 GRURec 的四域 atomic groups。

- SASRec 已有 E5 四域 seed=100 工件。continuation 首先做只读 identity/protocol audit；合同完全一致时消费 E5，不重复训练。
- Caser 和 GRURec 只有在真实生产 adapter 通过 protocol tests 后才能进入 ready 状态。
- 测试用 `fake_train.py`、build-only manifest 或无真实 checkpoint/selector/evaluator 的入口不能被视为 production adapter。
- 任一模型一旦启动，Steam、ML1M、Beauty、ATG 四域必须全部完成或整组标为 incomplete。
- 不允许 native resplit、方法专属 evaluator、超参数 sweep、第二 seed 或 favorable-only reporting。

### 4.4 RISK-11 DiffRec

第四优先级是 DiffRec，而不是 DiffuRec。训练前必须完成：

1. 官方代码库和 immutable revision 身份核验；
2. 模型家族核验，证明不是 DiffuRec；
3. `paper_raw_v1` split/mapping 适配审计；
4. common validation selector 和 full-catalog evaluator 审计；
5. 单卡 L20 显存可行性审计；
6. 四域 atomic launch manifest。

任一审计失败时，RISK-11 记录为 documented gap 并停止，不得用 DiffuRec、论文抄录数字或部分数据集替代。

## 5. Adapter gate

任务的状态集合增加 `blocked_adapter`，但该状态只表示“尚未具备可信生产入口”，不能伪装为 queued-ready。满足下列条件后才能从 `blocked_adapter` 变为 ready：

- argv 为数组，不经 shell 字符串求值；
- cwd 位于 immutable source bundle；
- seed 明确为 100；
- dataset、arm、run directory 唯一且在 dated queue root 下；
- 输入 split、mapping、bank、checkpoint、selector 和 evaluator hash 已绑定；
- 日志路径非空且启动后必须产生内容；
- summary、manifest、best/latest checkpoints 和 row provenance 有独立 artifact validator；
- toy contract test 和 production-contract dry-run 均通过；
- 不存在 destructive overwrite flag；
- 一张物理 GPU 同时最多一个训练进程。

Adapter 构建和 CPU 审计可以在 RISK-08 前完成；GPU 训练不得在 `risk_gated_method` 之前启动。

## 6. 维护窗口调度

### 6.1 时间定义

- 暂定维护截止：`2026-07-16T12:00:00+08:00`。
- 该时间不是强杀时间，而是保守的“禁止新增长任务启动”时间。
- 如果管理员提供具体关机时间，operator 可签发一份只改维护时间、不改科学任务和结果判据的 dated operations amendment；新截止必须至少早于计划关机 18 小时。

### 6.2 Latest-safe-start

每个任务冻结 `gpu_hours_high` 和 `maintenance_buffer_hours`。调度器仅在下式成立时启动任务：

```text
current_time
+ gpu_hours_high
+ maintenance_buffer_hours
<= planned_shutdown_time
```

如果管理员尚未给出计划关机时刻，则以 2026-07-17 00:00（Asia/Shanghai）作为最保守关机时间。当前默认 buffer 为 3 小时，因此默认 latest-safe-start 使用：

```text
2026-07-17 00:00
- task.gpu_hours_high
- 3 hours
```

此外，2026-07-16 12:00 后一律不启动预计超过剩余安全窗口的训练。被挡住的任务标为 `blocked_maintenance`，不是 failed，也不创建科学终态；升级后重新验证环境和 hash 后才恢复为 ready。

### 6.3 禁止的暂停方式

- 不得为维护创建 r7 的 `STOP_AFTER_CURRENT`，因为它会写 `outcome=stop_requested` 和 `no_rescue=true`。
- 不得在训练子进程运行时关闭服务器。
- 不得对运行中的训练发送 SIGTERM、SIGKILL 或以重试覆盖 attempt-once 合同。
- 不得通过删除 task record 让中断任务重新变成未开始。

### 6.4 升级前安全状态

升级前必须满足：

- r7 与 continuation 都没有 scientific child PID；
- 所有 `running` task record 都已由 supervisor 结算；
- 未出现 `interrupted_unverified`；
- controller 状态可为正常 terminal，或在无 child 时通过前台 `Ctrl-C` 进入 `status=stopped`；
- continuation manifest、source hash 和 passed records 保持不变。

## 7. 资源与并发

- GPU0、GPU1 各最多一个训练进程；未知 PID 占卡时只等待，不杀进程。
- 两张卡都可运行同一优先级 wave 的不同任务，但 matched pair 的完整性约束不变。
- `/data` 新 wave 启动阈值保持 40 GiB；当前核验可用空间为 67 GiB。
- continuation 总 GPU 预算沿用批准的七 GPU-day 上限，即 168 GPU-hours；任何候选任务的冻结 high estimate 会使累计预算超过 168 GPU-hours时，任务保持 `blocked_budget`。
- 已完成 E5 SASRec 工件的只读复用不计新增 GPU-hours。

## 8. 文件与证据布局

continuation 使用新的 dated root，例如：

```text
/data/Zijian/goal/aaai27_queue/2026-07-13-method-pass-continuation-<revision>/
  queue/
    queue_seed100_continuation.json
    queue_manifest_meta.json
  protocol/
    upstream_binding.json
    maintenance_window.json
    adapter_contracts/
  markers/
  state/
    controller.json
    tasks/
  logs/
    controller.log
    events.jsonl
    tasks/
  runs/
  artifacts/
```

服务器生产 bundle 必须是新的 immutable source 目录。不得在当前 r7 bundle 内就地修改脚本，也不得把 continuation 输出写入 r7、r6a、E5 或 frozen paper artifact 目录。

## 9. 错误处理

| 条件 | 行为 |
| --- | --- |
| r7 尚未完成 | 等待，不启动下游 |
| `risk_gated_method` | 验证 continuation manifest 后允许调度 |
| `audit_only` / `submission_stop` | 写 preserve-only 终态，训练数为零 |
| r7 task failure / `interrupted_unverified` | fail closed |
| 上游 hash 不一致 | fail closed |
| adapter 不合格 | `blocked_adapter`，不启动该模型 |
| GPU 被未知进程占用 | 等待，不杀进程 |
| 磁盘低于 40 GiB | `blocked_disk`，不启动新任务 |
| 超过 168 GPU-hours | `blocked_budget` |
| 超过 latest-safe-start | `blocked_maintenance` |
| 空日志、summary 缺失、manifest 不合格 | 当前任务 failed，禁止选择性补录 |
| controller 重启发现 orphaned running record | `interrupted_unverified`，不得自动重试 |

## 10. 测试要求

实施采用测试先行。至少覆盖：

1. r7 未终态时 continuation 启动零任务；
2. `risk_gated_method` 且所有 hash 正确时才解锁；
3. `audit_only`、`submission_stop`、task failure 均启动零任务；
4. 未知出口、双 marker、缺失 marker、hash mismatch 全部 fail closed；
5. r7 manifest 保持字节级不变；
6. seed 101/102、DiffuRec、BERT4Rec、retry manifest 被 validator 拒绝；
7. E5 SASRec 只有 identity 完全一致时才复用；
8. Caser/GRURec/DiffRec 未通过 adapter audit 时保持 `blocked_adapter`；
9. 维护截止后长任务进入 `blocked_maintenance`；
10. 维护截止前且预计可完成的短任务仍可调度；
11. GPU 双占用被拒绝；
12. `/data < 40 GiB` 阻止新 wave；
13. GPU 预算超过 168 小时阻止候选任务；
14. 空日志和缺失 artifact 使任务 fail closed；
15. controller 无 child 安全停止后重启，不重跑 passed task；
16. orphaned running record 变为 `interrupted_unverified` 且不重试；
17. dry-run 使用 fake worker 只验证控制逻辑，不被记录为科研完成；
18. production manifest 每项都能追溯到 RISK ledger row。

## 11. 部署验收

只有以下条件全部成立才允许在服务器启动 detached continuation controller：

- 本地测试全部通过；
- Linux production-contract 测试全部通过；
- manifest validator 输出 0 个错误；
- source bundle、manifest、上游绑定和维护窗口均有 SHA-256；
- dry-run 证明 r7 尚未完成时 0 个训练任务 ready；
- dry-run 证明非 method-pass 出口 0 个训练任务 ready；
- dry-run 证明维护时间会阻止越窗任务；
- tmux/controller PID、日志、状态 JSON 和恢复命令均记录；
- 部署前后 r7 manifest SHA-256 保持不变；
- 不触碰用户暂缓的备份操作。

## 12. 预期行为

若 GPU 在维护安全窗口内释放，r7 先完成剩余六个 Steam 任务并产生原始 RISK-08 决策。只有 `risk_gated_method` 会使 continuation controller 开始 seed=100 Stage D。能够在维护前安全完成的任务立即使用空闲 GPU；无法安全完成的任务保留为 `blocked_maintenance`，升级后在环境与 hash 复核通过后继续。

该设计保证“r7 完成后自动续跑”不等于“无视科学闸门和维护风险地启动所有训练”，同时保持现有 attempt-once、fail-closed、单卡单进程、四域原子报告和不覆盖 frozen artifact 的纪律。
