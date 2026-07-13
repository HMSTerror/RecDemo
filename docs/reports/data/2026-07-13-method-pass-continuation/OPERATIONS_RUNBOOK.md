# r7 method-pass continuation 操作手册

## 1. 目的与边界

本控制器在独立 queue root 中等待 r7 的原始 RISK-08 终态。只有经过 hash 绑定且 14/14 active tasks 全部 `passed`、原始出口精确为 `risk_gated_method` 时，才允许 seed=100 Stage D 调度。`audit_only`、`submission_stop`、task failure、`interrupted_unverified`、缺失/矛盾 marker 或 hash mismatch 均启动零个后续训练。

本任务没有执行备份，不修改 r7 manifest、r7 task records、E5 工件或任何 frozen paper artifact。

## 2. 固定上游

```text
r7 root:
/data/Zijian/goal/aaai27_queue/2026-07-12-risk0607-987eb19-r7

r7 manifest SHA-256:
387636c8c5dc5b09bb9c509db26b0f335ecac3ed1525e3c4bee3289612bb966e

E5 SASRec root:
/data/Zijian/goal/aaai27_queue/2026-07-12-e05-sasrec-seed100-gpu0-c5c9280

deployed source root:
/data/Zijian/goal/RecDemo_aaai27_continuation_e70d948

continuation queue root:
/data/Zijian/goal/aaai27_queue/2026-07-13-method-pass-continuation-e70d948

continuation manifest SHA-256:
79010b193eecad7dee59d2f6d86c764f7169f55b7bd08ba70f1e7999f2e8ec5e
```

## 3. 续跑矩阵

| 账本 | 内容 | 数量 | 当前 adapter 策略 |
| --- | --- | ---: | --- |
| RISK-13 | 四域 host/full seed=100 partial wave | 8 | 每个数据集独立 marker；只允许同方法合同的数据集解锁 |
| RISK-14 | 高/低风险各六臂 | 12 | `risk14/PASS.json` 缺失时全部 blocked_adapter |
| RISK-10 | SASRec/Caser/GRURec 四域 | 12 | SASRec 只读复用 E5；Caser/GRURec 等待真实 adapter |
| RISK-11 | DiffRec 四域 | 4 | 等待 identity/memory/common-protocol adapter；不是 DiffuRec |
| RISK-08 | method-pass contract gate | 1 | 只消费原始 r7 终态 |

总计 37 个任务槽位。所有 GPU 任务固定 seed=100、`max_attempts=1`、`failure_policy=fail_closed`。

## 4. 数据集级 PreferGrow marker

RISK-13 不使用一个全局 marker。路径为：

```text
protocol/adapters/prefergrow/<Dataset>/PASS.json
```

这样可以避免把 r7 已验证的 Beauty/Steam EPE/`phi_R` 合同与 ML1M/ATG 尚未补齐的合同静默混用。未授权数据集仍在 manifest 中，但状态为 `blocked_adapter`。

## 5. 维护窗口

```text
planned shutdown: 2026-07-17T00:00:00+08:00
conservative launch cutoff: 2026-07-16T12:00:00+08:00
per-task buffer: 3 hours
```

调度条件：

```text
now + frozen_gpu_hours_high + 3h <= planned_shutdown
```

不满足时记为 `blocked_maintenance`，不是 scientific failure。禁止用 r7 的 `STOP_AFTER_CURRENT` 作为维护暂停，因为它会写 `stop_requested/no_rescue` 终态。

## 6. CLI

```bash
python3 scripts/aaai27_method_pass_continuation.py prepare \
  --protocol /absolute/path/prepare_protocol.json

python3 scripts/aaai27_method_pass_continuation.py validate \
  --queue-root /absolute/path/to/continuation-root

python3 scripts/aaai27_method_pass_continuation.py status \
  --queue-root /absolute/path/to/continuation-root

python3 scripts/aaai27_method_pass_continuation.py run \
  --queue-root /absolute/path/to/continuation-root \
  --poll-seconds 10
```

`status` 和 `validate` 为只读。`prepare` 拒绝非空目标目录。`run` 使用 OS flock 防止双控制器。

## 7. detached 启动

生产启动必须记录完整命令、source revision、manifest SHA、session 和 PID。tmux 命名格式：

```text
aaai27_continuation_<short-revision>
```

本次真实 session 与 PID：

```text
session: aaai27_continuation_e70d948
controller PID: 4102610
poll interval: 10 seconds
state record: state/tmux_session.json
launch script: state/launch_controller.sh
```

生产启动必须使用绝对脚本路径。不要把 `scripts/aaai27_method_pass_continuation.py`
作为依赖当前目录的相对路径交给嵌套 SSH/tmux shell。

启动后至少等待两个 poll interval，确认：

- controller PID 存活；
- r7 未终态时 `gate=waiting_r7`；
- continuation scientific child PID 为零；
- task records 为零；
- 两张 GPU 的原有进程未被干预；
- r7 manifest SHA 未改变。

## 8. 空日志与工件

退出码为零仍不等于任务通过。以下任一条件触发 fail-closed：

- task log 不存在或为 0 字节；
- success artifact 不存在或为 0 字节；
- wrapper 的 JSON/identity/hash 验证失败。

禁止事后手工补日志、补 manifest 或从控制台复制 metrics 伪造工件。

## 9. 维护与恢复

升级前必须确认不存在 continuation scientific child PID。服务器重启后：

1. 验证 hostname、`/data` 挂载、两张 L20、驱动/CUDA；
2. 重新计算 source、queue manifest、upstream binding hashes；
3. 检查没有 orphaned `running` record；
4. 使用同一 queue root 和同一 source bundle 重启；
5. passed task 不重跑；
6. `interrupted_unverified` 不自动重试。

## 10. 状态汇报格式

```text
任务号 | 状态标签 | 关键数字与 dated artifact 路径 | 与验收标准差距 | 下一步
```

本次部署状态行：

```text
CONT-R7 | resident_waiting_r7 | PID 4102610; manifest 79010b193eecad7dee59d2f6d86c764f7169f55b7bd08ba70f1e7999f2e8ec5e; root /data/Zijian/goal/aaai27_queue/2026-07-13-method-pass-continuation-e70d948 | gap: RISK-08 not terminal | next: automatic gate consumption
```
