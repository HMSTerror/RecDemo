# AAAI-27 Abstract 冻结候选（2026-07-12 dated amendment）

_状态：P0-6 方法范围候选；不是 r7 结果报告。投稿母本仍为 `paper/main_v2.tex`。_

## 一句话裁决

当前摘要已经从“单一 `U_ds` 风险门”改为三代证据链：legacy `U_ds` discovery → RISK-03 EPE/PNE@10 direct exposure audit → controlled-corruption `phi_R` evidence-retention intervention。摘要可以冻结方法、理论边界和 r6a 已完成的 single-run observations；r7 的 anchor 结果、RISK-08 结论和任何 gate-efficacy 句在不可变出口生成前均不得写入。

## 证据来源与优先级

1. 英文投稿母本：`paper/main_v2.tex` 的 `abstract` 环境。
2. 方法修正案：`docs/reports/data/2026-07-12-r7-evidence-amendment/EPE_PHI_R_METHOD_AMENDMENT.md`。
3. 机器可读证据：同目录 `r6a_evidence_manifest.json`。
4. E0 evaluator 修正：`docs/reports/data/2026-07-10-evaluator-amendment/e0_evaluator_amendment.json`。
5. E1/R12：`docs/reports/data/2026-07-11-e01-gzero-production-trace-r12/`。
6. r7 仅限 prelaunch/live-start provenance；若文档与远端实时工件冲突,以远端工件为准。

## 当前英文摘要候选（必须与投稿母本逐句同步）

```text
Discrete preference diffusion recommenders such as PreferGrow corrupt a user's preferred item by fading it toward a proposal distribution and learn to grow the preference back. Personalization in this family acts entirely on the score side: the transition kernel is shared by all users. We personalize the kernel, and in doing so surface a counterintuitive fact: because the proposal is a corruption distribution, text evidence can be too good to use. On four benchmarks, a legacy train-only next-item text-utility statistic gives a descriptive inverse ordering of first-generation tilt outcomes. The ordering is perfect on the archived measurement scale but becomes three-of-four under the corrected common evaluator through an adjacent Beauty--ATG swap; we therefore treat it as a discovery signal, not a population law. We measure the proposed mechanism more directly with train-only observed-next-positive exposure (EPE/PNE@10), and use a two-factor, history-only gate g=g_max s_D clip(u_tilde,0,1) to interpolate between the host's learned proposal and a frozen text anchor. The frozen dataset scale s_D is generation-specific: the legacy four-domain hinge and the dated controlled-corruption reliability scale are reported separately. The design is fallback-safe at the kernel level: it reduces exactly to the host at g=0, while TV(p_u,p_core)<=g and one-step transition-row TV is at most (1-alpha_sigma)g; these are not end-to-end performance bounds. After repairing an optimizer-ownership mismatch, a revision-scoped E1 trace passed 2,986 designated comparisons, without testing standalone checkpoint replay or metric equivalence. In a seed-100 controlled-corruption precursor, Steam c60 moved validation and test NDCG@10 in the same direction; Beauty's positive differences were test-only, and c100 recovered the host best summary under an explicit zero dataset scale. Missing anchor artifacts and user-level uncertainty prevent an efficacy claim or a multi-run reliability assessment. The contribution is thus a reliability audit and a kernel-scoped safe construction, not uniform empirical improvement.
```

排版注：上面的纯文本用 `<=` 便于审阅；LaTeX 母本保留 `\TV`、下标和数学环境写法。

## 中文语义镜像

离散偏好扩散推荐器把用户偏好物品向 proposal distribution 褪色腐蚀,再学习恢复偏好。本文把原本只在 score 侧发生的个性化移到转移核,并发现文本证据作为 corruption proposal 时可能“好到不能直接用”。Legacy train-only 下一物品文本效用统计量在归档测量尺度上与第一代结果呈描述性 4/4 逆序；修正后的共同 evaluator 因 Beauty/ATG 相邻互换而降为 3/4,所以该排序只是 discovery signal。RISK-03 用 EPE/PNE@10 直接测 observed-next-positive exposure,广义门 `g=g_max·s_D·clip(ũ,0,1)` 则把不同代际的冻结数据集尺度明确分开。理论只保证 `g=0` 核级精确归约及 proposal/单步转移行 TV 界。E1/R12 只覆盖指定路径。r6a 中 Steam c60 的 validation/test 同向,Beauty 正差为 test-only,c100 是 explicit zero-scale fallback sanity check。anchor 与用户级不确定性缺失阻止 efficacy 主张或多次运行可靠性判断,因此论文定位是 reliability audit 与 kernel-scoped safe construction。

## 已冻结的科学边界

- `U_ds` 只能称 legacy train-only discovery descriptor；归档尺度 4/4,修正 evaluator 3/4。
- `1/24` 只能称 exchangeability 假设下某一指定全序的描述性比例,不是 p 值。
- EPE/PNE@10 只能称 observed-next-positive exposure proxy；不是完整 false-negative rate 或 end metric。
- `phi_R` 对冻结点随 EPE 增加,只能称 evidence-retention/corruption-reliability scale；不得写“高 EPE 自动关门”。
- c100 统一写为：显式 `phi_R=0` 下 selected best-summary 与 matched host 字节级相同；checkpoint 因额外 text-side state 而不同。
- 禁止把 c100 解释成 `u_tilde` 自动塌缩或 adaptive user-level backoff。
- Beauty c0/c60 若出现 test 值,必须同列 validation delta（约零）,并披露 selector 只看 validation、test 在开发期被记录。
- 所有 seed-100 结果只写 `single-run observation/result`；不写显著性、跨种子稳定性、统计等价或噪声范围等升级措辞。
- DiffuRec 不进入 confirmatory comparison；SASRec 是唯一共同协议外部参照,Beauty validation-to-test drop 保留为 unresolved anomaly。
- E7 为 `not_estimable`：请求 1000,实际执行 bootstrap 为 0。

## r7 结果占位纪律

截至本修正案生成时,r7 只有 prelaunch 与 detached-wait 工件,没有训练 task record、performance metric 或 RISK-08 exit。摘要不得写“r7 passed”“anchor attribution confirmed”或任何数值。只有同根 14 个 active tasks 全部通过、每臂同时具备非空日志、validation-selected best summary 与 `artifact_manifest.json`,且原始 `RISK-08_EXIT.json` 生成后,才能依据出口机械更新摘要。

## 机械 Go/No-Go 闸

| 时间/事件 | 摘要动作 |
|---|---|
| 2026-07-16 晚：r7 已启动/完成且原 RISK-08 合同可执行 | 维持 full-submission 路线,但只写已生成的不可变工件 |
| 2026-07-16 晚：GPU 未释放但 CPU/论文侧完成 | 保留当前降级候选,等待到 7/18,不预写结果 |
| 2026-07-18：仍无修复后 anchor evidence | 删除 gate-efficacy 语言,只保留 audit + EPE/PNE@10 + exact fallback |
| `RISK-08=submission_stop` | 删除 predictive-risk claim；禁止新阈值、新 corruption、第二 seed 与 rescue tuning |

AAAI-27 硬点仍为：摘要 2026-07-21、全文 2026-07-28、补充材料 2026-07-31（AoE）。

## 冻结前检查清单

- [ ] 英文候选与 `paper/main_v2.tex` 的摘要逐句一致。
- [ ] 中文稿没有比英文稿更强的因果、统计或 efficacy 主张。
- [ ] 4/4 均明确限定为 legacy/archived scale；corrected evaluator 同句给出 3/4。
- [ ] Beauty val/test 同列；development-time test logging 已披露。
- [ ] c100 是 explicit zero-scale sanity check,没有 `u_tilde` collapse。
- [ ] r7 未完成时没有任何 r7 performance/PASS 句。
- [ ] `submission_stop` 分支没有留下救援调参余地。
