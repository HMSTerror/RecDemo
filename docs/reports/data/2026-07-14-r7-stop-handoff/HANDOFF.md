# PreferGrow r7 暂停交接与科学裁决

_服务器快照时间：2026-07-14T22:06:23+08:00；面向下一位监督模型与项目负责人。_

---

## 📋 执行结论

本轮后续调度已经按用户要求停止。continuation controller 不再运行，`STOP_AFTER_CURRENT` 已存在，且从未启动任何 continuation 科学任务。r7 最后两项仍按原合同自然运行，root ACTRec 未被干预。

科学上，现有实验不能证明“EPE 越高导致 anchor 越有害，且风险门能按预注册机制修复该伤害”的完整假设。四类冻结现象检查中，full pointwise prediction 当前满足，但其余三类已经由完成工件锁定为失败。正确的论文路线是 fallback-safe kernel 与 prospective reliability audit，而不是普遍性能提升或已验证的 EPE 风险预测。

## 📊 服务器状态

| 项目 | 新鲜状态 |
| --- | --- |
| r7 queue root | `/data/Zijian/goal/aaai27_queue/2026-07-12-risk0607-987eb19-r7` |
| r7 manifest SHA-256 | `387636c8c5dc5b09bb9c509db26b0f335ecac3ed1525e3c4bee3289612bb966e` |
| r7 records | `12 passed / 2 running / 0 failed` |
| 运行项 | `Steam.full.c60`、`Steam.full.c100` |
| RISK-08 | 未生成 |
| r7 terminal | 未生成 |
| continuation root | `/data/Zijian/goal/aaai27_queue/2026-07-13-method-pass-continuation-e70d948` |
| continuation manifest SHA-256 | `79010b193eecad7dee59d2f6d86c764f7169f55b7bd08ba70f1e7999f2e8ec5e` |
| continuation controller | `stopped`，reason=`user_requested` |
| continuation records | `0` |
| 安全停止标记 | `state/STOP_AFTER_CURRENT` |
| GPU0/GPU1 | 均约 `10.8 GiB` 已用、`34.8 GiB` 空闲、利用率 `100%` |
| `/data` | `54 GiB` 可用；hard stop 为 `40 GiB` |

`controller.json` 的停止时间为 `2026-07-14T22:03:23+08:00`。禁止仅根据旧 tmux 名称或历史日志判断控制器仍在运行；必须同时核对 PID、`controller.json` 和 `STOP_AFTER_CURRENT`。

## 🔎 冻结假设判定

以下三项仅依赖已经终验的 anchor 与 Beauty full 工件，因此最后两条 Steam full 结果无法翻转。

| 冻结检查 | 阈值 | 实际结果 | 判定 |
| --- | ---: | ---: | --- |
| Anchor response ordering，Beauty 最差相邻反向量 | `≤0.002` | `0.002034093` | 失败，超出 `0.000034093` |
| Anchor response ordering，Steam 最差相邻反向量 | `≤0.002` | `0.017976131` | 失败 |
| EPE 与 anchor delta 的 Spearman | `ρ≤−0.5` | `ρ=+0.142857` | 失败 |
| Worst-anchor improvement | `≥0.002` 或负损失减半 | `0.000517196`；anchor 本身为正 | 失败 |

Full pointwise prediction 的当前结果为通过：Beauty c0/c60/c100 与 Steam c0 已终验；Steam c60/c100 仍是运行中 selected-best，当前也处于 `abs(delta test NDCG@10)<0.01` 的 parity 范围。它们只能维持或破坏 pointwise 检查，不能修复上述三项机制失败。

因此，若剩余两个 artifact manifest 通过完整 provenance 校验，原 finalizer 的预期逻辑为：E1=`pass` 且 `phenomenon_pass=false`，输出 `submission_stop`。在真实 marker 出现前，必须写“预期”，不能手工创建 RISK-08 或 terminal。

## 📈 可以保留的科学证据

- E0 evaluator amendment、R12 production trace、`g=0` kernel exact reduction 与 one-step kernel TV bound 仍然成立
- Beauty c100 在显式 `phi_R=0` 下与 host val/test 一致，可作为生产路径关门 sanity check
- Steam c0 full 的 validation/test NDCG@10 delta 分别为 `+0.001086732` 与 `+0.001518683`，只能称 seed=100 单次观测
- Beauty c0 full 的 test delta 为 `+0.001655589`，但 validation delta 约为 `−0.000001568`，必须标为 test-only observation
- Full pointwise prediction 当前受控，但不足以证明 EPE 的预测性或用户级 gate 的机制归因
- 负向预注册结果可支持“离线风险代理不足以预测端到端效果”的 reliability audit 结论

## ⚙️ 已实现但已停止的调度能力

本地 revision `8f7632c` 实现了 opt-in 共享调度：每卡最多两个 GPU 计算进程、外部进程计数、至少 `8192 MiB` 空闲显存、进程树去重、效率任务独占、运行中任务按 `gpu_hours_high` 预留预算。旧队列默认仍为一卡一任务。

验证记录：

- Windows：`98 passed / 1 skipped`；skip 为 Linux flock 集成测试
- Linux bundle：`99 passed / 12 subtests passed`
- Bundle：`/data/Zijian/goal/RecDemo_aaai27_continuation_8f7632c_b1`
- Source manifest SHA-256：`504b03388b00579ceb0f40a65a74b6417f25e0172b2c04132cda4aaa6c129b93`
- 失败上传残留目录：`/data/Zijian/goal/RecDemo_aaai27_continuation_8f7632c`，仅约 `4 KiB`；未经用户授权不要删除

该能力目前处于停止状态。不得删除 `STOP_AFTER_CURRENT` 或重启 controller，除非用户重新明确授权；即便授权，`submission_stop` 也必须继续阻止科学任务。

## ✍️ 论文调整边界

允许保留：

- proposal/kernel 级安全注入位置
- `g=0` exact reduction 的数学与指定实现 trace
- one-step transition-row TV bound，严格限定为 kernel 级
- 前瞻、冻结、fail-closed 的审计流程
- 预注册机制预测未通过的负结果

必须删除或降级：

- “EPE 能预测 anchor harm”的确认性陈述
- “风险门验证了机制并稳定提升”的陈述
- 任何 significant、stable、statistically equivalent、within noise 措辞
- 仅展示 Beauty test 正向而省略 validation parity 的表格
- 把 c100 解释成用户级 `u_tilde` 自动塌缩

## ✅ 下一模型的动作顺序

1. 先读本文件、根目录 `HANDOFF.md`、`status.json`、RISK-05 preregistration 与 `pilot_report.py`
2. 对服务器做新鲜只读查询；不得从本文件复制状态当作当前状态
3. 让 r7 最后两项自然结束，不停止、不重启、不修改阈值
4. 等原 r7 controller 生成真实 RISK-08/terminal；不得手工补 marker
5. 若真实出口为 `submission_stop`，运行只读 paper evidence builder，保存完整负结果并切换 audit-only 稿件
6. 不重启 continuation，不启动 E2/E4/E8、第二 seed 或 rescue tuning，除非用户签发新的 dated protocol amendment
7. 将中英文稿同步改为 fallback-safe kernel + prospective falsification/audit 故事
8. 保留 SASRec adapted common-contract baseline，并继续披露 Beauty 异常与 test 开发期记录事实

## 🔗 必读文件

- `HANDOFF.md`
- `docs/reports/data/2026-07-14-r7-stop-handoff/status.json`
- `docs/reports/data/2026-07-13-aaai-local-fixed-disk/epe_phi_r_method_amendment.md`
- `docs/reports/data/2026-07-13-aaai-local-fixed-disk/claim_evidence_traceability.md`
- `docs/reports/data/2026-07-13-aaai-local-fixed-disk/sasrec_implementation_data_audit.md`
- `scripts/aaai27_adapters/preregistration.py`
- `scripts/aaai27_adapters/pilot_report.py`
- `scripts/build_r7_paper_evidence.py`
- `docs/superpowers/specs/2026-07-14-continuation-gpu-sharing-design.md`
- `paper/main_v2.tex`
- `paper/main_v2_zh.md`

