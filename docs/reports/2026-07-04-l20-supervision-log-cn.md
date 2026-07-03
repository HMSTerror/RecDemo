# l20 训练监督日志(滚动)

- 开始:2026-07-04
- 角色分工:Claude 监督/调整计划 + 实时日志 + AAAI 论文;Codex 写代码;l20 实跑训练评估
- 账本:`issues/2026-07-02_17-06-23-aaai27-fallback-safe-kernel.csv`
- 远端:`ssh l20` → `/data/Zijian/goal/RecDemo`(用户口述路径 `/data/Zijian/Goal`,以远端实际大小写为准,连通后核实)

## 条目 1 — 2026-07-04 17:3x(+08:00)

**状态:l20 ssh 连接超时(172.18.0.40:22),ping 50% 丢包 — 内网链路抖动,与 2026-07-03 Codex 遇到并自愈的故障同型。**

- 已建立自动重连监视(每小时 3 次,连上即执行 SPRINT-05 预检并汇报;7 天自动过期)。
- 不阻塞本地关键路径,已完成:
  - **FOLLOWUP-08 ✅** Family D 基线措辞冻结 → `docs/reports/2026-07-04-family-d-claim-freeze-cn.md`(死线 7/7,提前 3 天关闭)
  - Codex 后台派发:FOLLOWUP-10 脚本(corrupted-bank U_ds/φ 复算,本地写码+测试,连通后上服务器跑)
- **待连通后的发射清单(SPRINT-05 预检,按 spec §8.2)**:
  1. `df -h /data`(上次满盘事故防复发,≥50G 余量才开跑)+ GPU 空闲检查
  2. 远端代码同步:`scripts/sync_remote_recdemo_code.py`(本地 HEAD = b92013b+,含 FOLLOWUP-06 双因子门控)
  3. 校验 U_ds 产物 hash 与 `gate0_text_utility_summary.csv` 一致、null 曲线产物在位
  4. `g≡0` 等价冒烟(远端短跑)通过后,tmux 并行发射 4 数据集验证跑(best-checkpoint-only 存储策略)
  5. 记录 run manifest(config/seed/bank hash/null hash/U_ds hash)入日志与账本
- 风险提示:若链路持续不通超过 24h(即 7/5 晚),SPRINT-05 的 7/6 期限顺延一天,7/14 Gate 2 检查点不动 — 缓冲仍够;需要用户侧检查 VPN/内网(我无法替代)。

<!-- 后续条目由监督循环追加于下方 -->

## 条目 2 — 2026-07-04 晚(本地强化批次)

服务器仍不通(按用户指示暂停远端;自动发射监视已撤)。本地完成:FOLLOWUP-08 冻结、φ 敏感性分析(65% 平台;冻结点 harm=0/gain=0.0066;LOO 4/4)、命题 7(目标碰撞)入正文、bib 全部核实(CDRec→WSDM'26,UGR→KDD'26,PreferDiff→ICLR'25)。运维阻塞:codex CLI 401(需重新登录)。

**恢复连接后发射清单新增第 0 步(优先于 SPRINT-05)**:在生产 bank 上计算 **ASO 的 U_ds**(纯离线,几分钟)— 若落在铰链半开区 [0.55, 0.70],把 ASO 加为第五数据集并纳入验证跑:它将把 "selective gain" 的 n 从 1 变 2,并测试铰链中段,是当前性价比最高的单点补强。
