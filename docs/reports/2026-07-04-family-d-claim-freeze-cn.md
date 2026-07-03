# Family D 基线措辞冻结备忘(FOLLOWUP-08)

- 冻结日期:2026-07-04(死线 2026-07-07 之前)
- 依据:`docs/superpowers/specs/2026-07-02-aaai27-fallback-safe-kernel-sprint-design.md` §8.1
- 输入证据:
  - `docs/reports/data/2026-07-02-gate0/gate0_v2_frozen_verdict.md`(Gate 0-v2 FAILED,仅 Steam 开门)
  - `docs/reports/data/2026-07-02-gate0/gate0_text_utility_summary.csv`(生产 U_ds)
  - `docs/reports/data/2026-07-01-text-side-vs-core-main-table-remote-v77.csv`(第一代 vs core 冻结对照)
  - `docs/reports/data/2026-07-02-gate0/gate0_v2_family_d_downgrade_memo_zh.md`

## 1. 冻结的 abstract 级主张(操作基线)

以下为论文摘要与结论允许的最强措辞,今日起为**操作基线**;2026-07-07 过后无论任何跑动是否完成,该基线自动生效:

> **EN(主句):** Because the proposal of discrete preference diffusion is a *corruption* distribution, text evidence can be too good to use: a train-only text-utility statistic inversely rank-orders the outcome of text-tilting the kernel on all four benchmarks (4/4). We operationalize this with a two-factor, history-only gate anchored to the host's learned proposal, which provably reduces to the host kernel when the gate closes (exact reduction; TV ≤ g) and backs off adaptively as evidence degrades.

> **EN(经验边界句,必须伴随主句出现):** The cross-dataset inversion rests on four points; gains are selective by design — where text utility is high the method's value is safety, not improvement.

## 2. 头版分析:U_ds 逆序表(冻结数字)

| dataset | U_ds(pop-neg) | φ(U_ds) | 第一代 Δtest NDCG@10 vs core |
| --- | ---: | ---: | ---: |
| Steam | 0.570 | 1.000 | +0.0064 |
| ATG | 0.688 | 0.117 | +0.0019 |
| Beauty | 0.712 | 0.000 | −0.0006 |
| ML1M | 0.754 | 0.000 | −0.0622 |

4/4 完美逆序(随机序零假设下 p = 1/24)。此表为论文 Table 1,已按本表填入 `paper/main.tex`。

## 3. 禁写清单(继承 spec §4.6,冻结)

1. `consistent gains across all datasets` / `uniform superiority`
2. `metadata sparsity robustness` 作为正证据(负结果只准进附录并如实标注)
3. `kernel consistently outperforms encoder and loss injection`
4. 一切 `first multimodal / first uncertainty-aware / first trustworthy` 类表述(旧 spec §1.4 全单继承)
5. 把第一代(v1)数字当最终系统 benchmark(只准作机制证据与失败模式,归属须如附录 D 声明)
6. 把 ML1M 写成 "nearly closes the gap" —— 它的角色是被机制解释的反例与 g≡0 归约的实证检验位

## 4. 只升不降规则(spec §8.2 rule 3)

- SPRINT-05 冻结门控验证跑的四条预注册预测(ML1M/Beauty |Δ|<0.01;ATG |Δ|<0.01;Steam Δ>0)**全部命中**时,方可按 `paper/main.tex` 中 `GATE-2 UPGRADE` 注释升级经验措辞,且必须以带日期的修订备忘记录;
- 任一预测未中:维持本备忘第 1 节措辞;ML1M/Beauty 平价失败额外触发实现红灯,论文中命题 6 的经验性表述暂停引用直至查明;
- 任何情况下不得回写本备忘第 3 节禁写清单中的句式。

## 5. 生效声明

本备忘冻结后,`paper/main.tex`(commit `b92013b` 起)的摘要、贡献、结论措辞即为 Family D 基线的正文实现;后续对这三处的任何加强性修改必须引用一份新的带日期升级备忘,否则视为违反冻结纪律。
