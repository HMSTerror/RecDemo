# 2026-07-02 Gate0 实验过程与操作记录

## 1. 结论先行

这次 Gate0 的正式运行，确实是在服务器 `l20` 上完成的，不是在本地假跑。

- 服务器：`l20`
- 远端仓库：`/data/Zijian/goal/RecDemo`
- 运行方式：远端 `tmux`
- 正式 Gate0 产物目录：`/data/Zijian/goal/RecDemo/docs/reports/data/2026-07-02-gate0`

我在 `2026-07-02 22:36:21 +0800` 重新复查远端目录时，服务器仍可见以下正式产物：

- `gate0_u_tilde_report.md`，时间 `Jul 2 21:52`
- `gate0_u_tilde_report.json`，时间 `Jul 2 21:52`
- `gate0_u_tilde_summary.csv`，时间 `Jul 2 21:52`
- `gate0_failure_diagnostic.md`，时间 `Jul 2 22:29`
- `gate0_failure_diagnostic.json`，时间 `Jul 2 22:29`
- `gate0_failure_component_summary.csv`，时间 `Jul 2 22:29`

本次 Gate0 的最终正式结论是：

- `Verdict: fail`
- `SPRINT-05` 继续 `blocked`
- 主路径下一步不应直接开主表重训，而应先做 `calibration_repair_first`

对应的本地归档文件在 [E:/PreferGrow/docs/reports/data/2026-07-02-gate0](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_u_tilde_report.md:1)。

## 2. 本次 Gate0 的目标是什么

本次 Gate0 不是训练主表，也不是跑新的 Beauty 训练，而是按设计文档中的 Gate 0 口径，对生产 `sentence-t5-xl` 文本银行做一次正式、全量、可复查的 `u_tilde` 诊断。

设计依据见：

- [2026-07-02-aaai27-fallback-safe-kernel-sprint-design.md](E:/PreferGrow/docs/superpowers/specs/2026-07-02-aaai27-fallback-safe-kernel-sprint-design.md:94)

Gate0 判据是：

1. `abs(median_u_tilde(ML1M)) < 0.5`
2. `median_u_tilde(Steam) > median_u_tilde(ML1M)`
3. `median_u_tilde(Beauty) > median_u_tilde(ML1M)`

只有这个 Gate0 通过，并且更早的 `g == 0` 等价性门也已经通过，后续 `SPRINT-05` 主表重训才允许打开。

## 3. 正式运行环境与边界

这次正式 Gate0 使用的是下面这组固定环境：

- 服务器：`l20`
- 远端工作目录：`/data/Zijian/goal/RecDemo`
- 正式数据目录：`/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/{ML1M,Steam,Beauty,ATG}`
- 文本银行：各数据集目录中已经存在的 production `sentence-t5-xl` 银行工件
- 运行方式：远端 `tmux`

这里需要特别说明两点：

1. 这次 Gate0 用的是“已经生成好的生产文本银行”，不是在这一步重新训练或重新编码文本。
2. 你之前指定的 `t5` 模型路径 `/data/models/sentence-transformers/sentence-t5-xl` 主要对应后续训练/编码路径；但本次 Gate0 是对现成 production bank 做读取和诊断，不是重新做 text embedding 训练。

因此，这次实验的性质更准确地说，是“服务器上的正式评估/诊断流程”，不是“服务器上的新训练”。

## 4. 本地为了让 Gate0 真能落地，补了哪些工具

为了把这次 Gate0 从“本地可构想”推进到“远端可正式跑通”，这轮一共补了几类关键工具和修复。

### 4.1 Gate0 正式报告构建脚本

文件：

- [build_gate0_utilde_report.py](E:/PreferGrow/scripts/build_gate0_utilde_report.py:1)

作用：

- 在指定数据集目录中读取正式 `text_bank`、`sentence_t5_xl_item_emb`、`agreement_null_curves`
- 全量遍历真实用户历史
- 计算 `u_tilde` 和 `g`
- 输出三份正式产物：
  - [gate0_u_tilde_summary.csv](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_u_tilde_summary.csv:1)
  - [gate0_u_tilde_report.json](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_u_tilde_report.json:1)
  - [gate0_u_tilde_report.md](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_u_tilde_report.md:1)

后面又对报告文案做了一次增强，让它在失败时明确写出：

- 原假设与修正后假设
- `SPRINT-05` 为什么继续阻塞

### 4.2 远端 Gate0 `tmux` 启动器

文件：

- [launch_gate0_tmux.py](E:/PreferGrow/scripts/launch_gate0_tmux.py:1)

作用：

- 从本地直接通过 `ssh` 在 `l20` 上创建远端 `tmux` 会话
- 默认指向 `paper_raw_v1` 的正式数据路径
- 后续修成使用远端脚本绝对路径：

```bash
python3 /data/Zijian/goal/RecDemo/scripts/build_gate0_utilde_report.py ...
```

这个修复很关键。最早如果用相对路径，`tmux` 里的启动目录一旦不是 `/data/Zijian/goal/RecDemo`，就会因为脚本找不到而退出。

### 4.3 Beauty 远端训练启动器同步修复

文件：

- [launch_beauty_text_side_tmux.py](E:/PreferGrow/scripts/launch_beauty_text_side_tmux.py:1)

虽然这次没有真的启动 Beauty 训练，但你已经明确要求“如果后续训练重开，先只跑 Beauty”，所以这轮顺手把 Beauty launcher 也对齐了：

- 默认数据路径改到 `paper_raw_v1/Beauty`
- Windows 侧改成 shell-free `ssh argv`

这样如果后续主路径恢复，Beauty 入口不会再卡在旧路径和 Windows quoting 上。

### 4.4 远端代码同步器

文件：

- [sync_remote_recdemo_code.py](E:/PreferGrow/scripts/sync_remote_recdemo_code.py:1)

背景是：远端 `RecDemo` 仓库当时的 `git HEAD` 仍停在老版本 `e63193f`，而 Gate0 所需的新脚本和 v2 代码只在本地。

所以这次没有依赖远端 `git pull`，而是补了一个“最小运行时代码同步器”：

- 单次 `SSH + tar stream` 同步
- 只推送 Gate0/Beauty 所需运行时文件
- 同步后在远端执行 `py_compile` 级别检查

### 4.5 SSH 抖动下的后台重试 helper

文件：

- [retry_gate0_when_l20_ready.py](E:/PreferGrow/scripts/retry_gate0_when_l20_ready.py:1)
- 日志：[gate0_retry_l20.log](E:/PreferGrow/logs/gate0_retry_l20.log:1)

因为 `l20` 的 SSH 连接在当时存在明显抖动，这个 helper 负责：

1. 周期性尝试重新同步远端代码
2. 一旦同步成功，立即拉起远端 Gate0 `tmux`

它的意义不是“更优雅”，而是“在 SSH 可用窗口很短时，尽量自动把正式 Gate0 推过去”。

### 4.6 Gate0 失败追因脚本

文件：

- [build_gate0_failure_diagnostic.py](E:/PreferGrow/scripts/build_gate0_failure_diagnostic.py:1)

这不是最初 Gate0 启动前的工具，而是 Gate0 失败后补上的 follow-up 诊断脚本。它会在和 Gate0 相同的生产环境中，进一步拆出：

- `agreement`
- `mu_null`
- `sigma_null`
- `agreement - mu_null`
- `(agreement - mu_null) / sigma_null`
- `history_length`
- `completeness`
- `history_reliability`
- `u_tilde`
- `g`

对应产物是：

- [gate0_failure_diagnostic.md](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_failure_diagnostic.md:1)
- [gate0_failure_diagnostic.json](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_failure_diagnostic.json:1)
- [gate0_failure_component_summary.csv](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_failure_component_summary.csv:1)
- 中文解释：[gate0_failure_diagnostic_zh.md](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_failure_diagnostic_zh.md:1)

## 5. 本次 Gate0 的实际操作时间线

以下时间，以本地操作日志、同步记录和远端产物时间为准。

### 5.1 第一轮：先把远端跑通

- `2026-07-02 20:22:04`：后台 helper 开始第 1 轮同步
- `20:22:40` 到 `20:25:38`：前 4 轮同步全部因为 SSH 超时失败
- `20:26:43`：第 5 轮同步成功
- `20:26:48`：第 5 轮 Gate0 启动成功

这次虽然已经把会话拉起来了，但后来确认这轮不能当正式证据，因为当时 `tmux` 里还是相对路径启动，存在工作目录漂移风险。

### 5.2 第二轮：修复绝对路径后重启

我先把 [launch_gate0_tmux.py](E:/PreferGrow/scripts/launch_gate0_tmux.py:1) 改成远端绝对脚本路径，然后重启 helper。

随后日志显示：

- `20:37:41` 到 `20:44:16`：第 1 到第 7 轮仍然都卡在 SSH 超时
- `20:44:53`：第 8 轮同步成功
- `20:44:59`：第 8 轮 Gate0 启动成功

这一次才是正式有效的启动点。之后远端完整 Gate0 跑完，并写出了正式报告。

### 5.3 正式 Gate0 产物第一次完整落盘

远端正式目录：

```text
/data/Zijian/goal/RecDemo/docs/reports/data/2026-07-02-gate0
```

首次完整产物写出时间：

- `2026-07-02 20:52`

对应的三份正式 Gate0 文件为：

- `gate0_u_tilde_report.md`
- `gate0_u_tilde_report.json`
- `gate0_u_tilde_summary.csv`

### 5.4 为了补齐失败假设说明，做了第二次正式重跑

在 Gate0 第一次跑完之后，我发现“结果有了”，但“失败时应该怎样写 revised hypothesis 和 SPRINT-05 决策”还不够正式，所以又做了一轮：

1. 更新本地报告生成脚本
2. 再次同步到远端
3. 再次用 `tmux` 启动 Gate0
4. 用新版正式报告覆盖旧产物

新版正式 Gate0 报告落盘时间是：

- `2026-07-02 21:52:30 +0800`

也就是说，最终归档在本地的 [gate0_u_tilde_report.md](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_u_tilde_report.md:1) 不是“第一次随便写出来的报告”，而是按设计要求补齐失败决策说明后的正式版。

### 5.5 Gate0 失败后，追加了一轮 follow-up 追因

为了回答“为什么 ML1M 会离 null 这么远”和“还能不能回主路径”这两个问题，我又在同一台服务器、同一套生产文本银行上跑了 follow-up 追因诊断。

远端 follow-up 产物时间为：

- `2026-07-02 22:29`

这说明补充诊断同样是在 `l20` 上跑出来的，而不是本地根据 JSON 手写推断。

## 6. 这次过程中踩到的问题，以及怎么修的

### 6.1 远端正式数据路径不是旧的 `dataset/<Dataset>`

真实生产数据路径是：

```text
/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/{ML1M,Steam,Beauty,ATG}
```

不是早期默认的：

```text
/data/Zijian/goal/RecDemo/dataset/<Dataset>
```

修法：

- Gate0 launcher 默认路径改到 `paper_raw_v1`
- Beauty launcher 也同步改到 `paper_raw_v1`

### 6.2 远端仓库版本太旧

当时远端 `RecDemo` 的 `git HEAD` 还是：

```text
e63193f
```

但 Gate0 所依赖的脚本和 v2 逻辑都已经比这个版本新。直接依赖远端原仓库状态会跑不起来，所以本次实际采用的是“本地代码最小同步到远端运行时目录”的方案。

### 6.3 Windows 下 `ssh` quoting 不稳

最初 launcher 用的是 `shell=True` 方式调 `ssh`。在 Windows 上，这种方式一旦命令里包含多层引号和远端 bash 片段，很容易出 quoting 问题。

修法：

- 改成 shell-free 的 `subprocess.run(build_ssh_argv(...), check=True)`

### 6.4 `tmux` 里相对路径不可靠

最开始远端命令接近于：

```bash
cd /data/Zijian/goal/RecDemo && python3 scripts/build_gate0_utilde_report.py ...
```

只要 `tmux` 会话起始目录不是预想值，这种方式就可能失效。

修法是直接改成：

```bash
python3 /data/Zijian/goal/RecDemo/scripts/build_gate0_utilde_report.py ...
```

### 6.5 真正最麻烦的是 SSH 链路抖动

最实际的问题不是逻辑错误，而是 `l20` 的 SSH 可达性不稳定。失败多数发生在认证前的连接建立阶段。

这也是为什么本次不是手工不停重试，而是补了 helper 自动轮询。一旦连上，就立刻同步和启动远端 `tmux`，减少人为盯守成本。

## 7. 这次真正跑过的关键命令

下面列的是这轮里最有代表性的操作命令，不是伪命令。

### 7.1 本地测试

```powershell
& 'E:/anaco/python.exe' -m unittest `
  tests.test_build_gate0_failure_diagnostic `
  tests.test_build_gate0_utilde_report `
  tests.test_sync_remote_recdemo_code
```

我在这次补文档前又重新跑了一次，上述 12 个测试全部通过。

### 7.2 本地同步远端运行时代码

```powershell
& 'E:/anaco/python.exe' scripts/sync_remote_recdemo_code.py `
  --retries 2 `
  --retry-delay-seconds 2 `
  --connect-timeout 10
```

### 7.3 从本地拉起远端 Gate0 `tmux`

```powershell
& 'E:/anaco/python.exe' scripts/launch_gate0_tmux.py `
  --output-dir /data/Zijian/goal/RecDemo/docs/reports/data/2026-07-02-gate0
```

### 7.4 远端 follow-up 追因的 `tmux` 命令

```powershell
ssh -o ConnectTimeout=10 l20 "(tmux has-session -t gate0_failure_diag 2>/dev/null && tmux kill-session -t gate0_failure_diag) || true; tmux new-session -d -s gate0_failure_diag bash -lc 'python3 /data/Zijian/goal/RecDemo/scripts/build_gate0_failure_diagnostic.py --dataset ML1M=/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/ML1M --dataset Steam=/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/Steam --dataset Beauty=/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/Beauty --dataset ATG=/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/ATG --output-dir /data/Zijian/goal/RecDemo/docs/reports/data/2026-07-02-gate0 --gate0-report-json /data/Zijian/goal/RecDemo/docs/reports/data/2026-07-02-gate0/gate0_u_tilde_report.json'; tmux list-sessions | grep gate0_failure_diag || true"
```

### 7.5 远端复查服务器产物

```powershell
ssh -o ConnectTimeout=10 l20 "hostname; date '+%F %T %z'; ls -lah /data/Zijian/goal/RecDemo/docs/reports/data/2026-07-02-gate0"
```

我在本轮补文档时重新执行了这条核查命令，返回：

- `hostname = ubuntu`
- 时间 `2026-07-02 22:36:21 +0800`
- 目录内可见 Gate0 正式产物和 follow-up 追因产物

这就是“确实在服务器上跑过并留有远端产物”的直接证据。

## 8. Gate0 的正式结果是什么

正式报告见：

- [gate0_u_tilde_report.md](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_u_tilde_report.md:1)
- [gate0_u_tilde_report.json](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_u_tilde_report.json:1)

正式结论：

- `Verdict: fail`

四个数据集的 `median_u_tilde` 为：

- `ML1M = 1.427543`
- `Steam = 0.107291`
- `Beauty = 0.798168`
- `ATG = 0.724168`

失败原因是：

1. `|median_u_tilde(ML1M)| = 1.427543 > 0.50`
2. `median_u_tilde(Steam) = 0.107291 < ML1M = 1.427543`
3. `median_u_tilde(Beauty) = 0.798168 < ML1M = 1.427543`

这意味着它不是“稍微没过线”，而是方向上就不支持“ML1M 应该接近 null 点”的原始预期。

## 9. Gate0 失败后的补充诊断，给出了什么新结论

补充诊断见：

- [gate0_failure_diagnostic.md](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_failure_diagnostic.md:1)
- [gate0_failure_diagnostic_zh.md](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_failure_diagnostic_zh.md:1)

这轮追因最重要的新发现是：

- 主驱动不是 `raw agreement` 残差大到离谱
- 更像是 `null_curve_spread_or_scaling_mismatch`

ML1M 的关键中位数是：

- `median(agreement) = 0.942712`
- `median(mu_null) = 0.931382`
- `median(agreement - mu_null) = 0.011330`
- `median(sigma_null) = 0.003968`
- `median((agreement - mu_null) / sigma_null) = 2.855086`

这组数说明：ML1M 的 residual 只是小幅正值，但由于 `sigma_null` 很紧，被标准化之后放大成了很高的 `u_tilde`。

所以，这次 follow-up 的正式推荐路径是：

- `recommended_next_path = calibration_repair_first`

保留的兜底路径是：

- `fallback_path = frozen_claim_downgrade_if_schedule_expires`

换句话说，当前证据更支持“先修 calibration/null spread”，而不是“直接无视 Gate0 重开主表”。

## 10. 这次操作和原始实验设计偏离了多少

如果只看“Gate0 应该怎么做”，这次正式执行并没有偏离设计主路径，反而是把原来不完整的执行链补齐了。

与设计一致的部分：

1. 使用的是正式 production `sentence-t5-xl` 银行，而不是本地 toy 工件。
2. 使用的是远端 `l20` 和正式数据目录 `paper_raw_v1`。
3. 按 Gate0 判据产出正式 verdict。
4. 失败后没有偷偷重开 `SPRINT-05`，而是把主表重训继续阻塞。

真正新增但不算“偏航”的部分只有一项：

- Gate0 失败后，增加了 component-level 的追因诊断。

这一步不是背离原设计，而是失败后为了判断“还能不能回主路径”所做的必要补证。它没有绕开 Gate0，也没有替换 Gate0，只是把失败原因从粗粒度结论继续拆开。

## 11. 对后续路径的直接影响

这次 Gate0 操作链已经闭环完成：

1. 本地补齐和修复运行脚本
2. 远端同步运行时代码
3. 在 `l20` 上通过 `tmux` 拉起正式 Gate0
4. 产出正式 Gate0 报告
5. 同步回本地归档
6. 在同一服务器上追加追因诊断
7. 明确记录主路径下一步应先做 calibration repair

所以本次工作可以定性为：

- 操作层面：完成
- 结果层面：Gate0 失败
- 路径层面：`SPRINT-05` 继续阻塞

如果要尽量回到主路径，下一步应该优先处理：

- `agreement_null_curves` 的 spread 是否过紧
- `k = 2.0` 在当前 production bank 上是否偏小
- `sigma_null` 是否需要更稳健的 floor / estimator

而不是直接重开四数据集主表训练。

## 12. 相关文件清单

### 12.1 关键脚本

- [build_gate0_utilde_report.py](E:/PreferGrow/scripts/build_gate0_utilde_report.py:1)
- [build_gate0_failure_diagnostic.py](E:/PreferGrow/scripts/build_gate0_failure_diagnostic.py:1)
- [launch_gate0_tmux.py](E:/PreferGrow/scripts/launch_gate0_tmux.py:1)
- [launch_beauty_text_side_tmux.py](E:/PreferGrow/scripts/launch_beauty_text_side_tmux.py:1)
- [sync_remote_recdemo_code.py](E:/PreferGrow/scripts/sync_remote_recdemo_code.py:1)
- [retry_gate0_when_l20_ready.py](E:/PreferGrow/scripts/retry_gate0_when_l20_ready.py:1)

### 12.2 关键测试

- [test_build_gate0_utilde_report.py](E:/PreferGrow/tests/test_build_gate0_utilde_report.py:1)
- [test_build_gate0_failure_diagnostic.py](E:/PreferGrow/tests/test_build_gate0_failure_diagnostic.py:1)
- [test_launch_gate0_tmux.py](E:/PreferGrow/tests/test_launch_gate0_tmux.py:1)
- [test_launch_beauty_text_side_tmux.py](E:/PreferGrow/tests/test_launch_beauty_text_side_tmux.py:1)
- [test_sync_remote_recdemo_code.py](E:/PreferGrow/tests/test_sync_remote_recdemo_code.py:1)
- [test_retry_gate0_when_l20_ready.py](E:/PreferGrow/tests/test_retry_gate0_when_l20_ready.py:1)

### 12.3 正式产物

- [gate0_u_tilde_report.md](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_u_tilde_report.md:1)
- [gate0_u_tilde_report.json](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_u_tilde_report.json:1)
- [gate0_u_tilde_summary.csv](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_u_tilde_summary.csv:1)
- [gate0_failure_diagnostic.md](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_failure_diagnostic.md:1)
- [gate0_failure_diagnostic.json](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_failure_diagnostic.json:1)
- [gate0_failure_component_summary.csv](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_failure_component_summary.csv:1)
- [gate0_failure_diagnostic_zh.md](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_failure_diagnostic_zh.md:1)
