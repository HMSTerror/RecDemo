# r7 method-pass continuation 本地验证报告

## 冻结信息

```text
branch: codex/r7-method-pass-continuation
tested and deployed revision: e70d948
platform: Windows / Python 3.13.0
date: 2026-07-13 Asia/Shanghai
```

## Provenance import

从服务器 immutable bundle：

```text
/data/Zijian/goal/RecDemo_aaai27_risk0607_987eb19_r7
```

导入 queue core、adapter dependency closure、pilot wrapper 及测试。19 个初始文件和 16 个 adapter 模块分别完成远程/本地 SHA-256 对照。导入后的基线：

```text
63 passed, 1 skipped
```

跳过项为 Windows 上不适用的 Linux flock integration。

## TDD 证据

已观察到并保存的 RED 类型包括：

- continuation upstream 模块不存在；
- maintenance policy 模块不存在；
- Stage D manifest 模块不存在；
- E5 reuse auditor 模块不存在；
- continuation controller 模块不存在；
- CLI 模块不存在；
- unsafe required marker 未被旧 validator 拒绝；
- guarded DiffRec 缺 marker 未被旧 validator 拒绝；
- zero-byte task log 被旧 runtime 误判为成功。

对应最小实现完成后，最终 focused + imported regression 命令结果：

```text
94 passed, 1 skipped in 11.59s
```

覆盖：

- r7 waiting/method-pass/audit-only/submission-stop；
- 14/14 records、inactive branch、interrupted record、hash mismatch；
- maintenance exact boundary、disk、budget、dependency、adapter marker；
- 37-task Stage D matrix；
- RISK-13 production wrapper argv；
- E5 SASRec 四域 atomic reuse；
- per-dataset PreferGrow authorization；
- controller start ordering and preserve-only zero launch；
- queue-core regression；
- zero-byte log fail-closed。

部署前发现直接执行 `scripts/aaai27_method_pass_continuation.py` 时无法导入顶层
`scripts` package。该问题在创建生产 queue root 前失败，不涉及任何训练。新增回归测试先
复现 `ModuleNotFoundError`，再加入最小入口 bootstrap。修复后的局部回归为：

```text
15 passed in 2.55s
```

Windows 首次扩大回归时，pytest 全局临时目录因 ACL 返回 7 个 setup error；改用工作树内
隔离 `--basetemp` 后 15/15 通过。该环境错误没有被记为代码失败。

## 静态检查

```text
python -m compileall: PASS
git diff --check: PASS
```

## 本地部署工件

```text
source archive:
.deployment/source_e70d948.tar
SHA-256: fc4d822836f1089d43542729ae1d152c57407b055292fb573217ac0acc96dd5f

source manifest:
.deployment/source_manifest_e70d948.txt
SHA-256: 5ebc98f961863c03f5ab9d86aebe9cdeff87b72cdd5a89aabd450de2c39f0553
```

## Linux 与生产部署验证

服务器 immutable bundle：

```text
/data/Zijian/goal/RecDemo_aaai27_continuation_e70d948
source archive SHA-256: fc4d822836f1089d43542729ae1d152c57407b055292fb573217ac0acc96dd5f
source manifest SHA-256: 5ebc98f961863c03f5ab9d86aebe9cdeff87b72cdd5a89aabd450de2c39f0553
Linux full continuation/queue regression: 88 passed, 12 subtests passed in 0.89s
```

生产 queue：

```text
root: /data/Zijian/goal/aaai27_queue/2026-07-13-method-pass-continuation-e70d948
manifest SHA-256: 79010b193eecad7dee59d2f6d86c764f7169f55b7bd08ba70f1e7999f2e8ec5e
controller session: aaai27_continuation_e70d948
controller PID: 4102610
observed gate: waiting_r7
r7 progress at verification: 8 passed, 1 running
continuation task records: 0
continuation scientific starts: 0
```

仅存在以下 adapter pass marker：

```text
prefergrow/Beauty/PASS.json
prefergrow/Steam/PASS.json
sasrec/PASS.json
```

ML1M、ATG 没有同等级 EPE/`phi_R` 方法合同，故没有 PreferGrow marker。RISK-14、
Caser、GRURec、DiffRec 也没有真实 adapter marker。它们仍出现在冻结 37-task manifest 中，
但不能启动。

驻留启动后等待超过两个 10 秒 poll interval。控制器仍存活，37/37 槽位均为
`blocked_upstream`，r7 manifest 仍为：

```text
387636c8c5dc5b09bb9c509db26b0f335ecac3ed1525e3c4bee3289612bb966e
```

第一次 tmux 尝试因嵌套引号使相对脚本路径错误地从 `/home/zijian` 解析，session 当即退出，
没有创建 controller lock 或 task record。第二次使用 queue state 中的绝对路径启动脚本后成功。
旧错误行保留在 `logs/controller.log`，未删除或改写。

## 备份声明

本任务没有执行服务器备份，符合用户“暂时先不备份”的明确指令。
