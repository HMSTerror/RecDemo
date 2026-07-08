# AAAI-27 Introduction 重写交付(2026-07-07,按用户六步提示词流程)

> 约束(高于提示词):①贡献 bullets 为**冻结措辞,逐字保留**(含其中的窄域 "first",其合规性归 CLOSE-08 检查④,不在本次改动权限内);②引用只准用 `paper/references.bib` 的 23 个已核实 key,不发明;③经验表述不得强于摘要冻结句;④禁写清单(freeze memo)适用。
> 应用方法:用第 6 部分的 tex 替换 `paper/main_v2.tex` 中 `\section{Introduction}` 起、到 `Our contributions:` 之前的正文段落;贡献 itemize 块**原样不动**;宏(\Uds、\phids、\ut)与 \ref 标签已对齐现稿。改后必须在 l20 用 `~/tools/tectonic` 编译验证,并同步 `paper/main_v2_zh.md` 引言段。

---

## 1. 初稿(brief first draft)

Diffusion-based recommenders replace one-shot prediction with corrupt-and-reconstruct. In the discrete instantiation, corruption acts directly on the item being ranked: the forward kernel fades the preferred item into a proposal distribution, and a learned score grows it back. The proposal distribution is therefore the family's central object—it fixes what "replaces" a faded preference. Existing work personalizes the score side and keeps the kernel global. We ask whether the kernel itself can be personalized with external text evidence, and answer with a caution: the better text predicts the next item, the more a text-tilted proposal corrupts future positives into negatives. We measure this with a train-only statistic, observe a 4/4 cross-dataset inversion, and build a two-factor gate with an exact fallback guarantee. A pre-registered validation reports honestly mixed outcomes.

## 2. 文献地图(23 个 bib key 的角色分配)

| key | 是什么 | 与本文关系 | 引言是否用 |
|---|---|---|---|
| `prefergrow` | 宿主模型(NeurIPS'25):离散偏好扩散,score 侧个性化+非偏好分支引导 | 被"补全"的对象:kernel 侧从未个性化 | ✅ 核心 |
| `d3pm` / `sedd` | 离散扩散基石(结构化转移核 / score entropy) | 本文核代数与训练目标的地基 | ✅ 一处 |
| `dllm-llada` | 扩散语言模型计划 | 浪潮的上游背景 | ✅ 一处 |
| `llada-rec` / `gr-diffgrm` / `gr-admasked` / `gr-mdtheory` | 2025Q4-2026H1 自适应腐蚀浪潮(并行 SID 解码/置信度任意序/自适应掩码/理论跟进) | 最近发展=gap 的精确对照:全部适配**模型内部信号**,无外部证据定价、无归约保证 | ✅ 核心 |
| `dreamrec` / `preferdiff` / `diffurec` / `idreamrec` | 连续扩散推荐线 | 相邻家族(条件在去噪器/引导上,不在离散核上) | ✅ 合并一句 |
| `cfg` / `acfg` / `cfgrec` / `tdpm` | 引导/条件化技术线 | related work 深入;引言不必展开 | ❌(留 §RW) |
| `recformer` / `unisrec` | 文本作为表示侧证据的序列推荐 | "文本证据常规用法在表示侧"的对照 | ✅ 一句 |
| `srns` / `debiased` | 负采样中的假负例代价 | 机制段的精确支点:腐蚀提议继承同一风险 | ✅ 一句 |
| `cdrec` / `ugr` / `truthsr` | bib 内其余(角色见现稿 §RW) | 与引言主线无直接关系 | ❌(留 §RW,添加前核对各自 scope) |

**与前人结果的精确对比(step 3 要求)**:`prefergrow` 证明了 score 侧个性化+推理期引导在该家族有效——恰好停在 kernel 之外;`gr-admasked` 观察到"均匀掩码有害"并给出启发式位置调度——自适应信号是模型内部的,无"证据该不该进来"的判据;`gr-mdtheory` 开始给 masked-diffusion 推荐做理论——不覆盖外部证据条件化的安全性。三者拼出本文的精确空位:**train-only 的证据定价 + 误导证据下的精确归约保证**。

## 3-4. 加引用版与重排版

(与第 6 部分合并呈现——重排后的顺序即最终顺序,单独中间稿意义不大,略。)

## 5. 顺序为什么这样排

1. **对象先行**(proposal distribution 是什么、控制什么)→ gap 才能作为"对象的属性"一句话说死(kernel 是全局的),而不是泛泛的"没人做过";
2. **近期浪潮放在 gap 之前**作为"recent developments"→ gap 只出现一次、火力集中(它们适配的是内部信号;缺定价与保证);
3. **假负例文献(`srns`/`debiased`)紧贴机制段**出现——读者恰好在需要"为什么腐蚀到未来正例代价高"的佐证时看到它;
4. **反转发现在理论之前**——安全性设计由发现驱动,不是装饰;
5. **诚实验证一句话收尾**放在设计之后——读作严谨性而非示弱(step 6:不在贡献清楚之前引入局限)。

## 6. 终稿(tex-ready;贡献块原样保留,此处到 itemize 前为替换范围)

```latex
\section{Introduction}

Diffusion-based recommenders replace single-step prediction with an
iterative corrupt-and-reconstruct process. In the discrete
instantiation---preference fading and growing over the item
vocabulary~\cite{prefergrow}, built on structured discrete kernels and
score-entropy training~\cite{d3pm,sedd}---corruption acts directly on
the object being ranked: the forward kernel fades the preferred item
into a \emph{proposal distribution} over alternatives, and the reverse
process grows the preference back.

The proposal distribution is the central object of this family. It
fixes what ``replaces'' a faded preference, and through that choice it
determines the stationary distribution of the forward chain, the
reference measure of detailed balance, the weights of the
score-entropy objective, and the analytic reverse ratio. Yet in
existing discrete preference diffusion the proposal is \emph{global}:
one kernel shared by every user, with personalization entering only
through the score network and inference-time guidance against a
non-preference branch~\cite{prefergrow}. Meanwhile, item text---the
most abundant external evidence about items---is routinely exploited
on the representation side of sequential
recommenders~\cite{recformer,unisrec}, and continuous-diffusion
recommenders condition denoisers or guidance
signals~\cite{dreamrec,preferdiff,diffurec}. The kernel itself has
remained unconditioned.

Making corruption \emph{adaptive} is now an active program in
generative recommendation: parallel semantic-ID decoding under masked
diffusion~\cite{llada-rec}, confidence-ordered any-order
decoding~\cite{gr-diffgrm}, and position-adaptive masking schedules
motivated by the observation that uniform masking is
harmful~\cite{gr-admasked}, with theoretical analysis beginning to
follow~\cite{gr-mdtheory} on top of the discrete-diffusion
language-model program~\cite{dllm-llada}. What this wave adapts to,
however, is model-\emph{internal} signal---confidence and position
heuristics. Two ingredients are missing for \emph{external} evidence:
a train-computable decision rule for whether evidence should be
allowed to shape corruption at all, and a guarantee for the shaped
process when the evidence is misleading. This paper is a
pre-registered reliability study of exactly those two ingredients, in
the simplest kernel family where they can be posed cleanly.

Intuition suggests a monotone rule: the better the text evidence, the
harder the kernel should lean on it. \emph{Our central empirical
finding is that this intuition is backwards.} The proposal is a
corruption distribution---items it favors are treated as where
preference goes when it fades, that is, as negatives. If text
similarity is informative enough to rank the user's actual next item
highly, a text-tilted proposal concentrates corruption mass on likely
future positives, manufacturing false negatives in proportion to the
quality of the evidence---a failure mode the negative-sampling
literature pays dearly to avoid~\cite{srns,debiased}. Measuring
evidence quality with a train-only statistic $\Uds$ (how well text
similarity discriminates the next item from sampled negatives), we
find that $\Uds$ \emph{inversely} rank-orders the outcome of
text-tilting the kernel on all four of our benchmarks
(Sec.~\ref{sec:inversion}): the largest gain occurs on the dataset
with the \emph{weakest} next-item text signal, and a severe loss on
the dataset with the \emph{strongest}.

The inversion dictates what a reliability signal for kernel
conditioning must do, and motivates \emph{fallback-safe evidence
conditioning}. A low-capacity gate
\begin{equation*}
  g(\ut,\Uds) \;=\; g_{\max}\;\phids\;\mathrm{clip}(\ut,0,1)
\end{equation*}
combines two history-only factors: a per-user coherence signal $\ut$,
calibrated against a length-matched \emph{random-history null} of the
evidence space (raw coherence has a high, dataset-dependent floor that
otherwise couples the kernel's operating point to embedding geometry),
and a frozen dataset-level utility factor $\phids$ that \emph{closes}
the gate as $\Uds$ enters the false-negative regime. The gated kernel
interpolates between the host's learned global proposal and a frozen
text anchor, leaving the host's pseudo-item mass untouched. The theory
is deliberately elementary---rank-one kernel algebra---but it buys
properties that score-side or loss-side injection cannot even express:
conditional on the fixed history-derived signals, all structural
properties of the host chain survive; when the gate closes, the kernel
\emph{is} the host kernel, exactly; and at any gate value the kernel
stays within $g$ of the host in total variation. A pre-registered
four-dataset validation and mechanism controls then test the design
under a frozen protocol, and we report the outcome as it fell:
directional gain where the gate opens, parity where it closes, and one
readout held open as an implementation question rather than evidence
in either direction.

Our contributions:
%% ↓↓↓ 以下 itemize 为冻结措辞,从现稿原样保留,勿改 ↓↓↓
```

(itemize 从现稿 `\begin{itemize} \item \textbf{The utility-inversion finding.} ...` 原样接续。)

## 应用与检查清单(给 Opus)

- [ ] 替换范围核对:`\section{Introduction}` 至 `Our contributions:` 前(现稿约 L114–L196,以实际 grep 为准);itemize 不动
- [ ] 编译:l20 `~/tools/tectonic main_v2.tex`,无新 warning
- [ ] 扫描:freeze memo 禁词表 grep=0;新增正文无 "first"(冻结 itemize 内的除外)
- [ ] 中文镜像 `paper/main_v2_zh.md` 引言段同步重写
- [ ] 最后一段"one readout held open"措辞在 Gate-2 后按 §3/§4 判定结果复核(与摘要句联动)
