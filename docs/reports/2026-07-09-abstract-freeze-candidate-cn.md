# Abstract 冻结候选

_日期：2026-07-09_
_用途：把 `paper/main_v2.tex` 中当前英文摘要抽成独立冻结候选稿，明确哪些句子已可冻结，哪些句子仍受 `CLOSE-02` 约束_

---

## 📝 一句话结论

截至 2026-07-09，当前英文摘要的绝大部分句子都已经可以作为 `CLOSE-06` 的冻结候选；唯一仍然带有条件性的，是关于 “两条 closed-gate parity checks 的差距是否可视为 run-to-run noise” 那一句，它必须继续服从 `CLOSE-02` 的 dated artifact。

## 📍 摘要来源

- 投稿母本：`paper/main_v2.tex`
- 抽取区间：`\\begin{abstract}` 到 `\\end{abstract}`
- 冻结边界：`docs/reports/2026-07-04-family-d-claim-freeze-cn.md`
- 噪声地板约束：`docs/reports/data/2026-07-09-close02-ml1m-noise-floor-sync-note.md`

## 🎯 当前英文摘要候选稿

```text
Discrete preference diffusion recommenders such as PreferGrow corrupt a user's preferred item by fading it toward a proposal distribution and learn to grow the preference back. Personalization in this family acts entirely on the score side: the transition kernel is shared by all users. We personalize the kernel, and in doing so surface a counterintuitive fact: because the proposal is a corruption distribution, text evidence can be too good to use. On four benchmarks, a train-only measure of how well text similarity predicts the next item inversely rank-orders the outcome of text-tilting the kernel in all four cases: the tilt helps where text defines informative hard negatives and fails where text predicts future positives; corruption then becomes false-negative pollution. We operationalize this with a two-factor, history-only gate (a per-user coherence signal calibrated against a length-matched random-history null, damped by a frozen dataset-level utility factor) that interpolates between the host's learned proposal and a frozen text anchor. The design is fallback-safe: the conditioned chain retains Markovianity, detailed balance, and the analytic reversal of the host kernel; it reduces exactly to the host when the gate closes; and it deviates by at most the gate value in total variation. Controls (reliability shuffling, global proposals, ungated anchors) show the mechanism requires an aligned per-user signal, and corruption diagnostics show adaptive backoff as evidence degrades. A pre-registered four-dataset validation of the frozen gate returned a mixed verdict: the opened gate keeps a small positive gain and one closed-gate dataset holds parity, while two datasets miss their parity bands by margins comparable to run-to-run noise, which we report as an open implementation question rather than evidence in either direction. The cross-dataset inversion rests on four points; gains are selective by design---where text utility is high the method's value is safety, not improvement.
```

## ✅ 已可冻结的句子块

下面这些部分当前已经不依赖新的远端工件：

1. **问题设定与宿主介绍**
   - PreferGrow / discrete preference diffusion / proposal distribution / score-side personalization
2. **核心发现**
   - “text evidence can be too good to use”
   - 四数据集上的 inversion 叙事
3. **方法定义**
   - two-factor, history-only gate
   - fallback-safe 三件套：Markovianity、detailed balance、analytic reversal、exact reduction、TV bound
4. **机制证据**
   - controls
   - corruption diagnostics
5. **冻结边界句**
   - `The cross-dataset inversion rests on four points; gains are selective by design---where text utility is high the method's value is safety, not improvement.`

## ⚠ 唯一仍然受 `CLOSE-02` 约束的句子

当前摘要里最敏感的句子是：

> `...while two datasets miss their parity bands by margins comparable to run-to-run noise, which we report as an open implementation question rather than evidence in either direction.`

这句现在可以保留，原因是：

- 它仍然属于 `weak-default` 口径
- 没有提前宣称 “within the measured host noise floor”
- 与 `paper/main_v2.tex` 当前正文保持一致

但它**不能**在没有新的 dated `CLOSE-02` artifact 时升级成更强表述。

## 🔁 若 `CLOSE-02` 落地后的替换原则

### 维持当前句子

适用于：

- 没有新的 dated close02 artifact
- 或新 artifact 仍然不足以支持 within-noise

### 条件升级版本

仅当新的 dated close02 artifact 明确支持 ML1M 缺口落在宿主噪声地板内时，才允许把上面那句改成更强版本。具体替换句块已经单独写在：

- `docs/reports/2026-07-09-main-v2-wording-patches-cn.md`

## 📋 OpenReview 冻结前检查项

- [ ] 当前 abstract 仍与 `paper/main_v2.tex` 完全一致
- [ ] main sentence 与 boundary sentence 仍保持 Family D 冻结口径
- [ ] 没有出现 forbidden-list phrasing
- [ ] `CLOSE-02` 若无新工件，摘要保留当前弱口径
- [ ] `CLOSE-02` 若有新工件，升级只能通过 wording patch doc 执行

## 🔆 结论

对 `CLOSE-06` 来说，摘要现在并不是“整段都在等实验”，而是只有一个噪声归因句子还在等 `CLOSE-02`。这意味着标题和摘要冻结的主要工作，已经从“继续写”转成“守住边界、等唯一条件句是否需要替换”。
