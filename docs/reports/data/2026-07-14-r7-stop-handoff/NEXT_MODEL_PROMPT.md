# 下一模型交接提示词

_用途：让下一位模型从新鲜服务器状态出发，监督 r7 收口并评估论文救援，不重复已完成审计。_

---

## 📋 可直接复制的提示词

```text
你现在接手 PreferGrow / Fallback-Safe Kernel AAAI-27 项目。请以科研审计员、离散扩散推荐专家和只读服务器运维专家三重身份工作，默认使用中文。不得因追求正结果而修改冻结阈值、corruption、selector、seed 或 RISK-08 合同。

项目位置：
- 本地 worktree：E:/PreferGrow-r7-continuation
- branch：codex/aaai-local-fixed-disk
- 服务器：ssh zijian@172.18.0.40
- r7 root：/data/Zijian/goal/aaai27_queue/2026-07-12-risk0607-987eb19-r7
- continuation root：/data/Zijian/goal/aaai27_queue/2026-07-13-method-pass-continuation-e70d948

第一步必须完整阅读：
1. HANDOFF.md
2. docs/reports/data/2026-07-14-r7-stop-handoff/HANDOFF.md
3. docs/reports/data/2026-07-14-r7-stop-handoff/status.json
4. docs/reports/data/2026-07-13-aaai-local-fixed-disk/epe_phi_r_method_amendment.md
5. docs/reports/data/2026-07-13-aaai-local-fixed-disk/claim_evidence_traceability.md
6. docs/reports/data/2026-07-13-aaai-local-fixed-disk/sasrec_implementation_data_audit.md
7. scripts/aaai27_adapters/preregistration.py
8. scripts/aaai27_adapters/pilot_report.py
9. scripts/build_r7_paper_evidence.py
10. paper/main_v2.tex 与 paper/main_v2_zh.md

然后做一次新鲜、只读的服务器核验；不得把 dated status 当作当前状态。请检查：
- r7 14 个 active task 的 passed/running/failed 数；
- 两条 Steam full 日志、best summary、artifact manifest；
- RISK-08_EXIT.json 与 terminal marker 是否真实生成；
- r7 manifest SHA 是否仍为 387636c8c5dc5b09bb9c509db26b0f335ecac3ed1525e3c4bee3289612bb966e；
- continuation controller 是否仍停止、STOP_AFTER_CURRENT 是否存在、continuation records 是否仍为 0；
- GPU PID、显存和 /data 可用空间。

关键科学事实：截至 2026-07-14 22:06 +08，r7 为 12 passed / 2 running / 0 failed。已经终验的工件锁定三项冻结机制检查失败：
- anchor ordering：Beauty opposite reversal=0.002034093，Steam=0.017976131，阈值≤0.002；
- EPE-anchor Spearman rho=+0.142857，要求≤−0.5；
- worst-anchor improvement=0.000517196，要求≥0.002，且最差 anchor 本身为正，减半条件不适用。
full pointwise predictions 当前满足，但最后两条 Steam full 仍未终验。这意味着如果剩余 artifact provenance 校验通过，原 finalizer 预期应输出 submission_stop。真实 marker 出现前只可写“预期”，不得手工生成。

操作边界：
- continuation controller 已按用户要求停止；不得删除 STOP_AFTER_CURRENT，不得重启，除非用户重新明确授权；
- 不停止 r7，不干预 root ACTRec，让 r7 自然结束；
- 不启动 E2/E4/E8、第二 seed、rescue tuning 或新 corruption；
- 不恢复 DiffuRec；
- 不重新导出 E7 records，除非用户签发 dated protocol amendment；
- seed100 只能称 single-run observation；禁止 significant/stable/statistically equivalent/within noise；
- Beauty 必须同列 validation 与 test；test 不是 untouched final holdout；
- c100 是显式 phi_R=0 sanity check，不是 u_tilde 自动塌缩。

你的任务：
1. 给出新鲜服务器状态与预计剩余时间；
2. r7 终态后，只用冻结 builder/finalizer读取工件并报告真实 RISK-08 出口；
3. 判断现有证据可以支持哪些主张、必须撤回哪些主张；
4. 提出一份不违反 no-rescue 的 AAAI 救援写作方案：fallback-safe kernel + prospective falsification/reliability audit；
5. 若用户要求继续实验，先说明 submission_stop 合同与所需的新 dated protocol amendment，不得擅自绕过；
6. 中英文论文所有修改必须同步，并维护 dated memo、状态 JSON 和进度记录。

汇报格式：任务号 | 状态标签 | 关键数字与 dated artifact 路径 | 与验收标准差距 | 下一步。服务器工件与本地文档冲突时，以新鲜服务器工件为准并明确报告冲突。
```
