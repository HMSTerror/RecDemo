# AAAI 本地固定盘交接（2026-07-13）

## 2026-07-14 manuscript integration addendum

- English/Chinese active manuscripts now distinguish U_ds discovery, EPE measurement, and preregistered phi_R intervention.
- Strict 4/4 wording was removed; Steam/ML1M endpoints and the Beauty/ATG adjacent swap are reported.
- Adapted common-contract SASRec is integrated across all four domains with Beauty validation/test side by side.
- Editable TikZ method/risk diagrams and a deterministic phi_R PDF/PNG are under `paper/figures/`.
- Three RISK-08 conditional result modules remain external to the compiled manuscript.
- `paper/AAAI_BUILD.md` records that the official author kit and local TeX engine are absent.
- `scripts/sync_and_build_r7_paper_evidence.ps1` is remote-read-only and works for nonterminal status snapshots. Terminal Windows release is still fail-closed because the production validator expects the original Linux clean-null path; add immutable external-provenance copying/path mapping before relying on terminal local release.

## 一句话状态

本地方法、evaluator 与 SASRec 证据已形成 dated 草案；r7 论文结果仍由 14-task 原子终态闸门阻塞，当前任何部分臂都不得进入主表。

## 工作位置

- Worktree：`E:/PreferGrow-r7-continuation`
- Branch：`codex/aaai-local-fixed-disk`
- Dated package：`docs/reports/data/2026-07-13-aaai-local-fixed-disk/`
- 冻结输入 inventory：`input_sha256.csv`
- 服务器 continuation revision：`e70d9481cca57617c04e7fdbc7fc7f9dc83b1b3c`
- 服务器 r7/continuation controller 不属于本分支写权限范围。
- `inputs/r7/source/scripts/run_aaai27_pilot_task.py` 对应服务器原始路径；早期快照还保留一份位于 `source/scripts/aaai27_adapters/` 的同内容副本，二者均由 inventory 记录，审计时以原始路径副本为准。

## 已落地内容

1. `epe_phi_r_method_amendment.md`：分离 `U_ds`、EPE、`phi_R`，纠正 c100 解释。
2. `table1_evaluator_arbitration.md/.csv`：证明严格 4/4 在新旧尺下均不成立。
3. `sasrec_implementation_data_audit.md`：审计适配版 SASRec 的数据、模型、selector 与 Beauty 落差。
4. `scripts/build_r7_paper_evidence.py`：只读 fail-closed 发布器；测试位于 `tests/test_build_r7_paper_evidence.py`。
5. `gate2_bilingual_amendment.md`：中英文冻结措辞。
6. `claim_evidence_traceability.md/.csv`：主张—证据—禁用措辞映射。
7. `risk_response_source.csv`、`sasrec_four_domain_source.csv`：图表数据合同源。
8. 根目录两份 checklist 与 `tables/`、`figures/` 数据合同。

## r7 发布操作

在服务器 r7 已终态并将完整 root 以只读方式提供后运行：

```bash
python scripts/build_r7_paper_evidence.py \
  --queue-root <R7_QUEUE_ROOT> \
  --expected-manifest-sha256 <FROZEN_QUEUE_SHA256> \
  --output-dir docs/reports/data/<DATE>-r7-paper-evidence
```

训练尚未终态但只需要状态文件时，可加 `--allow-not-ready`。严禁为了出表伪造 marker、复制 r6a 数字或手工补齐一条缺臂。

## 下一位模型的第一组动作

1. 对服务器做新鲜只读查询，确认 14 个 active record、日志和 RISK-08/terminal 状态。
2. 若仍非终态，只更新 status，不改论文性能表。
3. 若出口为 `risk_gated_method`，用 builder 生成 CSV/JSON，再人工核验 Beauty validation/test 与 c100 标签。
4. 若出口为 `audit_only` 或 `submission_stop`，保留负结果，切换 audit-only 稿件，不启动 rescue tuning。
5. 依据 `AAAI_MANUSCRIPT_INTEGRATION_CHECKLIST.md` 一次性修改中英文稿。

## 尚缺实验

- P0：r7 14-task 原子终态与 RISK-08 出口。
- P0：E2 ATG attribution，前提是真实 continuation entrypoint 与 frozen contract 已验证。
- P1：E4 ML1M matched pair，实测预算约 44–55 GPU-h；卡释放晚则写 limitation。
- P1：E8 isolated-L20 efficiency，约 2–6 GPU-h。
- Deferred：三 seed、BERT4Rec、更多数据集、prospective holdout。
- E7：除非用户另签 dated protocol amendment，禁止重新导出 records。

## 不可跨越的边界

- seed100 只能称 single-run observation。
- Beauty 正向结果必须同时展示 validation 近 parity 与 test 数字。
- c100 是显式 `phi_R=0` sanity check，不是自适应用户门塌缩。
- SASRec 是 adapted common-contract baseline，不是 official reproduction。
- test 不是 untouched final holdout。
- DiffuRec 不恢复到 confirmatory comparison。
