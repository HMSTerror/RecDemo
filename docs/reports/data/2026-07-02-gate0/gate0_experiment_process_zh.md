# 2026-07-02 Gate0 实验过程与操作记录

## 1. 本次 Gate0 的目标

本次 Gate0 的目标不是训练主表，而是在正式生产银行上完成一次远端、全量、可复查的 `u_tilde` 诊断，验证 [E:/PreferGrow/docs/superpowers/specs/2026-07-02-aaai27-fallback-safe-kernel-sprint-design.md](E:/PreferGrow/docs/superpowers/specs/2026-07-02-aaai27-fallback-safe-kernel-sprint-design.md:94) 里定义的 Gate 0 判据：

1. `abs(median_u_tilde(ML1M)) < 0.5`
2. `median_u_tilde(Steam) > median_u_tilde(ML1M)`
3. `median_u_tilde(Beauty) > median_u_tilde(ML1M)`

只有 Gate0 和 `g == 0` 等价性门都满足，后续 `SPRINT-05` 主表重训才允许打开。

## 2. 目标运行环境

本次正式 Gate0 使用的是以下环境与路径：

- 服务器：`l20`
- 远端仓库：`/data/Zijian/goal/RecDemo`
- 远端正式数据：`/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/{ML1M,Steam,Beauty,ATG}`
- 文本银行：生产 `sentence-t5-xl` 银行
- 运行方式：远端 `tmux`

对应的本地产物与证据目录：

- 正式报告 markdown：[gate0_u_tilde_report.md](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_u_tilde_report.md:1)
- 正式报告 json：[gate0_u_tilde_report.json](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_u_tilde_report.json:1)
- 汇总表：[gate0_u_tilde_summary.csv](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_u_tilde_summary.csv:1)

## 3. 本地为 Gate0 新增或修正的工具

为了让这次 Gate0 真能在 `l20` 上按正式路径落地，本地一共补了 5 类工具/修复：

### 3.1 Gate0 报告构建脚本

文件：

- [E:/PreferGrow/scripts/build_gate0_utilde_report.py](E:/PreferGrow/scripts/build_gate0_utilde_report.py:1)

作用：

- 在指定数据集目录上读取正式 `text_bank / sentence_t5_xl_item_emb / agreement_null_curves`
- 全量遍历真实用户历史，计算 `u_tilde` 与 `g`
- 输出：
  - `gate0_u_tilde_summary.csv`
  - `gate0_u_tilde_report.json`
  - `gate0_u_tilde_report.md`

后续又补了一次报告文案增强，使其在 `fail` 时显式写出：

- 修正后的假设
- `SPRINT-05` 继续阻塞的决策

### 3.2 远端 Gate0 tmux 启动器

文件：

- [E:/PreferGrow/scripts/launch_gate0_tmux.py](E:/PreferGrow/scripts/launch_gate0_tmux.py:1)

作用：

- 在 `l20` 上通过 `tmux` 启动 Gate0
- 默认指向 `paper_raw_v1` 数据路径
- 后续修正为使用远端脚本绝对路径  
  `python3 /data/Zijian/goal/RecDemo/scripts/build_gate0_utilde_report.py ...`

这个绝对路径修复很关键，因为最初用相对路径时，`tmux` 会话可能落在 `/home/zijian`，从而导致脚本找不到。

### 3.3 Beauty 远端启动器同步修复

文件：

- [E:/PreferGrow/scripts/launch_beauty_text_side_tmux.py](E:/PreferGrow/scripts/launch_beauty_text_side_tmux.py:1)

作用：

- 虽然这次没有真的进入 Beauty 训练，但用户明确要求后续只先跑 Beauty，因此提前把这个 launcher 修到和 Gate0 一致：
  - 改成 `paper_raw_v1/Beauty`
  - Windows 侧改成 shell-free `ssh argv`

### 3.4 远端代码同步工具

文件：

- [E:/PreferGrow/scripts/sync_remote_recdemo_code.py](E:/PreferGrow/scripts/sync_remote_recdemo_code.py:1)

作用：

- 因为远端 `RecDemo` 的 git HEAD 还停在老 commit `e63193f`
- 而 Gate0 需要的新脚本和 v2 代码都只在本地
- 所以新增了一个单次 SSH + tar stream 的运行时代码同步器，把 Gate0/Beauty 所需的 21 个运行时文件同步到远端，并在远端做 `py_compile` 验证

### 3.5 SSH 抖动下的后台重试 helper

文件：

- [E:/PreferGrow/scripts/retry_gate0_when_l20_ready.py](E:/PreferGrow/scripts/retry_gate0_when_l20_ready.py:1)
- 日志：[E:/PreferGrow/logs/gate0_retry_l20.log](E:/PreferGrow/logs/gate0_retry_l20.log:1)

作用：

- 因为 `l20` 的 22 端口一度频繁超时
- helper 会周期性尝试：
  1. 同步代码
  2. 同步成功后启动 Gate0 tmux

这让我们在 SSH 窗口短暂恢复时，也能自动把 Gate0 推过去。

## 4. 本次 Gate0 的关键时间线

以下时间都以本地日志记录为准。

### 4.1 第一轮尝试

- `2026-07-02 20:22:04`：helper 开始第 1 轮 sync
- `20:22:40` 到 `20:25:38`：前 4 轮 sync 全部因 SSH 超时失败
- `20:26:43`：第 5 轮 sync 成功
- `20:26:48`：第 5 轮 Gate0 launch 成功

这一轮虽然成功启动过一次，但后来发现：

- 当时的 tmux 启动脚本还是相对路径
- 远端实际运行目录可能偏到 `/home/zijian`
- 所以这轮不适合作为最终正式证据

### 4.2 修复绝对路径后重启 helper

在 [E:/PreferGrow/scripts/launch_gate0_tmux.py](E:/PreferGrow/scripts/launch_gate0_tmux.py:1) 修好绝对路径后，重新启动 helper。

随后日志显示：

- `20:37:41` 到 `20:44:16`：第 1 到第 7 轮 sync 持续失败，原因都是 SSH 超时
- `20:44:53`：第 8 轮 sync 成功
- `20:44:59`：第 8 轮 Gate0 launch 成功

这次是关键启动点。之后远端完整 Gate0 真正跑完，并在正式目录中落下结果。

### 4.3 正式 Gate0 产物写出

远端正式 Gate0 目录：

- `/data/Zijian/goal/RecDemo/docs/reports/data/2026-07-02-gate0`

首次完整产物写出时间：

- `2026-07-02 20:52`

这批文件包括：

- `gate0_u_tilde_report.md`
- `gate0_u_tilde_report.json`
- `gate0_u_tilde_summary.csv`

### 4.4 报告文案增强后的二次重跑

为了让正式报告满足 sprint 设计里“失败时要写 revised hypothesis，并显式阻塞 SPRINT-05”的要求，我在本地补充了报告字段与 markdown 文案后，又做了一次：

1. 同步更新后的脚本到远端
2. 再次通过 `tmux` 启动 Gate0
3. 等待新版正式报告覆盖原产物

新版报告落盘时间：

- `2026-07-02 21:52:30 +0800`

之后把三份正式产物同步回本地目录 [E:/PreferGrow/docs/reports/data/2026-07-02-gate0](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_u_tilde_report.md:1)。

## 5. 本次过程中遇到的问题与对应修复

### 5.1 远端数据路径不是旧的 `dataset/<Dataset>`

实际生产数据在：

```text
/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/{ML1M,Steam,Beauty,ATG}
```

不是旧的：

```text
/data/Zijian/goal/RecDemo/dataset/<Dataset>
```

修复：

- Gate0 launcher 改到 `paper_raw_v1`
- Beauty launcher 也同步改到 `paper_raw_v1`

### 5.2 远端仓库代码版本太旧

远端 `RecDemo` 的 git HEAD 还是：

```text
e63193f
```

但本次 Gate0 依赖的新脚本、v2 路径和 launcher 都只在本地。  
因此没有直接依赖远端 `git pull`，而是新增同步工具，把运行时所需文件推到远端。

### 5.3 Windows 下 `ssh` shell quoting 不稳

最初 launcher 通过 `subprocess.run(..., shell=True)` 调 SSH，Windows 侧 quoting 风险较大。

修复：

- 改成 shell-free 的 `subprocess.run(build_ssh_argv(...), check=True)`

### 5.4 tmux 内相对路径不可靠

最早 Gate0 远端命令形如：

```bash
cd /data/Zijian/goal/RecDemo && python3 scripts/build_gate0_utilde_report.py ...
```

但一旦 `tmux` 会话启动目录不是预期目录，就可能找不到脚本。

修复：

```bash
python3 /data/Zijian/goal/RecDemo/scripts/build_gate0_utilde_report.py ...
```

### 5.5 SSH 链路本身持续抖动

最实际的问题不是代码，而是 `l20` 的 SSH 可达性不稳定。  
从日志可见，大量失败都发生在真正建立认证前的 TCP/SSH 连接阶段。

为了解这个问题，本次没有选择手工一遍遍重试，而是：

- 增加 helper 后台循环
- 等待稳定窗口出现
- 一旦连上，立即同步并拉起远端 tmux

## 6. 这次实际执行过的几类命令

### 6.1 本地单测校验

典型命令：

```powershell
& 'E:/anaco/python.exe' -m unittest `
  tests.test_build_gate0_utilde_report `
  tests.test_launch_gate0_tmux `
  tests.test_launch_beauty_text_side_tmux `
  tests.test_sync_remote_recdemo_code `
  tests.test_retry_gate0_when_l20_ready
```

### 6.2 本地同步远端代码

```powershell
& 'E:/anaco/python.exe' scripts/sync_remote_recdemo_code.py `
  --retries 1 `
  --retry-delay-seconds 1 `
  --connect-timeout 10
```

### 6.3 本地通过 tmux 拉起 Gate0

```powershell
& 'E:/anaco/python.exe' scripts/launch_gate0_tmux.py `
  --output-dir /data/Zijian/goal/RecDemo/docs/reports/data/2026-07-02-gate0
```

### 6.4 远端核查会话与产物

```powershell
ssh l20 "tmux ls 2>/dev/null || true"
ssh l20 "ls -lah /data/Zijian/goal/RecDemo/docs/reports/data/2026-07-02-gate0"
ssh l20 "cat /data/Zijian/goal/RecDemo/docs/reports/data/2026-07-02-gate0/gate0_u_tilde_report.md"
```

### 6.5 把远端正式产物拉回本地

```powershell
scp l20:/data/Zijian/goal/RecDemo/docs/reports/data/2026-07-02-gate0/gate0_u_tilde_report.md `
    E:/PreferGrow/docs/reports/data/2026-07-02-gate0/
scp l20:/data/Zijian/goal/RecDemo/docs/reports/data/2026-07-02-gate0/gate0_u_tilde_report.json `
    E:/PreferGrow/docs/reports/data/2026-07-02-gate0/
scp l20:/data/Zijian/goal/RecDemo/docs/reports/data/2026-07-02-gate0/gate0_u_tilde_summary.csv `
    E:/PreferGrow/docs/reports/data/2026-07-02-gate0/
```

## 7. 本次实验的最终正式结果

正式报告结论：

- `Verdict: fail`

正式全量统计的 `median_u_tilde`：

- `ML1M = 1.427543`
- `Steam = 0.107291`
- `Beauty = 0.798168`
- `ATG = 0.724168`

失败原因在正式报告里已经写明：

1. `|median_u_tilde(ML1M)| = 1.427543 > 0.50`
2. `median_u_tilde(Steam) = 0.107291 < ML1M = 1.427543`
3. `median_u_tilde(Beauty) = 0.798168 < ML1M = 1.427543`

也就是说，这次 Gate0 不是轻微未过，而是方向级别地不支持原先的 ML1M-near-null 预期。

## 8. 本次操作的结论与后续影响

本次 Gate0 的操作链已经闭环完成：

1. 本地补齐/修正了所需脚本
2. 远端同步运行时代码
3. 在 `l20` 上通过 `tmux` 启动正式 Gate0
4. 产出带日期的正式报告
5. 把正式报告同步回本地
6. 在报告中显式写出 revised hypothesis 与 `SPRINT-05` 阻塞决策

因此本次 Gate0 可以视为操作层面完成、结果层面失败。

对后续路径的直接影响是：

- `SPRINT-04` 可以关闭
- `SPRINT-05` 不允许直接打开
- 如果要回到主路径，下一步应该先修正 calibration / claim path，而不是直接开四数据集主表重训

## 9. 相关文件清单

### 本次关键脚本

- [E:/PreferGrow/scripts/build_gate0_utilde_report.py](E:/PreferGrow/scripts/build_gate0_utilde_report.py:1)
- [E:/PreferGrow/scripts/launch_gate0_tmux.py](E:/PreferGrow/scripts/launch_gate0_tmux.py:1)
- [E:/PreferGrow/scripts/launch_beauty_text_side_tmux.py](E:/PreferGrow/scripts/launch_beauty_text_side_tmux.py:1)
- [E:/PreferGrow/scripts/sync_remote_recdemo_code.py](E:/PreferGrow/scripts/sync_remote_recdemo_code.py:1)
- [E:/PreferGrow/scripts/retry_gate0_when_l20_ready.py](E:/PreferGrow/scripts/retry_gate0_when_l20_ready.py:1)

### 本次关键测试

- [E:/PreferGrow/tests/test_build_gate0_utilde_report.py](E:/PreferGrow/tests/test_build_gate0_utilde_report.py:1)
- [E:/PreferGrow/tests/test_launch_gate0_tmux.py](E:/PreferGrow/tests/test_launch_gate0_tmux.py:1)
- [E:/PreferGrow/tests/test_launch_beauty_text_side_tmux.py](E:/PreferGrow/tests/test_launch_beauty_text_side_tmux.py:1)
- [E:/PreferGrow/tests/test_sync_remote_recdemo_code.py](E:/PreferGrow/tests/test_sync_remote_recdemo_code.py:1)
- [E:/PreferGrow/tests/test_retry_gate0_when_l20_ready.py](E:/PreferGrow/tests/test_retry_gate0_when_l20_ready.py:1)

### 本次正式结果

- [gate0_u_tilde_report.md](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_u_tilde_report.md:1)
- [gate0_u_tilde_report.json](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_u_tilde_report.json:1)
- [gate0_u_tilde_summary.csv](E:/PreferGrow/docs/reports/data/2026-07-02-gate0/gate0_u_tilde_summary.csv:1)
