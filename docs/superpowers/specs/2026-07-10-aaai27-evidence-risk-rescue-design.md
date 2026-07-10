# AAAI-27 Evidence-Risk Rescue Design

**Status:** User-approved design, frozen for executable CSV generation on 2026-07-10

**Target:** AAAI-27 main-track submission

**Primary execution ledger:** `issues/2026-07-10_21-18-20-aaai27-evidence-risk-rescue.csv`

**Working title:** *When Better Evidence Hurts: Auditing Content-Conditioned Corruption in Discrete Diffusion Recommendation*

## 1. Decision summary

This rescue replaces the unsupported story that evidence-conditioned corruption should improve recommendation uniformly. The confirmation target is instead a reliability question:

> When external evidence shapes a discrete diffusion corruption proposal, does predictive evidence increase exposure to future positives, can that risk be measured from training transitions before retraining, and can a risk-gated proposal reduce negative transfer while preserving the host kernel structure?

The design freezes the following decisions.

1. `DiffuRec` is removed from the confirmatory model-comparison table because it is not the `DiffRec` baseline used in the PreferGrow paper. Existing DiffuRec runs, hashes, and E0 artifacts remain archived; no artifact is deleted, overwritten, relabeled, or presented as a DiffRec reproduction.
2. The confirmatory shared-protocol baseline block is `SASRec`, `Caser`, `GRURec`, and `DiffRec`, followed by the PreferGrow host and the proposed method. `BERT4Rec` is an optional additional classic baseline, not described as part of the original PreferGrow Table 1 block.
3. `DreamRec`, `PreferDiff`, and `DDSR` may appear as published-reference context only unless their official implementations pass the shared-protocol adapter audit before the baseline launch cutoff. Published numbers and local shared-protocol results must never be mixed in one ranked table.
4. Existing four-domain utility inversion and the ASO miss are discovery evidence. They cannot be used as confirmation of a newly introduced risk statistic.
5. Confirmatory evidence comes from a prospectively frozen, popularity-stratified evidence-corruption sweep on Beauty and Steam. Risk definitions, corruption hashes, predictions, and stop conditions are recorded before any corresponding validation or test result is read.
6. All pilot training starts with `random_seed=100`. Only gate-passing host/full and selected mechanism arms expand to seeds `100/101/102`.
7. `fallback-safe`, `no-harm`, and end-to-end exact-reduction claims are forbidden unless the production-path E1 trace passes at steps 0, 1, 100, and 1000, including optimizer membership and state.
8. The total new budget is planned at 7--10 cumulative GPU-days, with a hard ceiling of 12 GPU-days. Two NVIDIA L20 GPUs may run in parallel, with no more than one training process per GPU.

## 2. Problem and opportunity

The current manuscript has a potentially important observation but an invalidly strong method story. Text evidence is beneficial when used as a representation, condition, or retrieval signal. A corruption proposal has different semantics: its high-mass items are destinations of preference fading and therefore behave like structured negatives or alternative states. Evidence that predicts the next positive item can consequently be harmful when used to shape corruption.

The archived evidence is mixed rather than uniformly positive:

- Steam has the weakest archived text utility and the only positive host-relative direction.
- Beauty is a closed-gate near-parity observation.
- ML1M is a closed-gate implementation miss that exceeds the measured host spread.
- ATG is a barely-open miss.
- ASO is an honest out-of-sample prediction miss.
- Per-user utility/harm correlations do not reproduce the cross-dataset ordering.
- E1 finds a production-path divergence at step 0 because the canonical core proposal has different optimizer ownership.

This pattern cannot support a universal accuracy-improvement claim. It can support a stronger scientific question if the project adds controlled evidence-quality interventions, prospectively validates a mechanism-aligned train-only risk statistic, and narrows all guarantees to the level actually established.

## 3. Goals

### 3.1 Scientific goals

1. Establish or falsify a controlled relationship between evidence risk and the host-relative effect of text-shaped corruption.
2. Compare the archived rank-based utility statistic `U_ds` with mechanism-aligned positive-exposure statistics computed only from training transitions.
3. Test whether a frozen risk gate reduces negative transfer relative to an ungated text anchor without claiming uniform superiority over the host.
4. Separate structural kernel reduction from optimizer, training-trajectory, selector, and test-metric equivalence.
5. Rebuild the external comparison around methods aligned with the original PreferGrow baseline family and a single shared protocol.

### 3.2 Submission goals

1. Produce a claim/evidence map in which every Introduction contribution has a dated artifact, an explicit limitation, or is removed.
2. Produce one confirmatory baseline table, one host-relative three-seed table, one mechanism table, one evidence-risk response figure, and one efficiency table.
3. Preserve all negative results and exploratory artifacts while preventing stale or model-mismatched numbers from entering confirmatory tables.
4. Complete the rescue decision by 2026-07-14, freeze the abstract by 2026-07-18, preserve the submission target no later than 2026-07-20, finish the full manuscript by 2026-07-27, and finish supplementary material by 2026-07-30.

## 4. Non-goals

The rescue does not authorize the following.

- Claiming state-of-the-art performance or uniform improvement across datasets.
- Deleting DiffuRec artifacts or hiding that an exploratory model-mismatched baseline was run.
- Renaming DiffuRec results as DiffRec.
- Copying published baseline numbers into a local shared-protocol ranking table.
- Selecting corruption levels, risk thresholds, checkpoints, or paper claims using favorable test outcomes.
- Running a broad hyperparameter sweep after inspecting pilot results.
- Treating `1/24` as a confirmatory p-value.
- Treating three training seeds as enough to use `significant`, `stable`, `statistically equivalent`, or `within noise` without an appropriate analysis.
- Claiming that proposal or transition-row TV bounds control end-to-end recommendation loss.
- Solving the already accepted repeated-test-inspection limitation through a new holdout in this rescue window.

## 5. Discovery evidence and confirmation boundary

### 5.1 Discovery-only inputs

The following may motivate the risk hypothesis and define diagnostics, but cannot count as prospective confirmation of a new metric:

- the four-domain `U_ds` ordering and host-relative text-tilt outcomes;
- the frozen-gate Steam, Beauty, ML1M, and ATG results;
- the ASO out-of-sample miss;
- first-generation Beauty token-dropout controls;
- existing Beauty corrupted-bank `U_ds` values;
- FOLLOWUP-09 per-user correlation results;
- E0 corrected test evaluations;
- E1 optimizer-ownership failure.

### 5.2 Confirmatory units

The confirmatory units are new conditions whose evidence banks are generated and hashed after this design freeze:

- Beauty popularity-stratified embedding permutations at 0%, 20%, 40%, 60%, 80%, and 100%;
- Steam popularity-stratified embedding permutations at the same six levels;
- pilot training at 0%, 60%, and 100%;
- intermediate 20%, 40%, and 80% training only after the pilot gate passes without changing metric definitions or predictions.

All corruption uses seed 100. The item mapping, popularity stratum, vector shape, row norms, pseudo-item convention, and dataset split hashes remain unchanged. Validation/test targets are not inputs to bank construction or risk estimation.

## 6. Risk statistics

### 6.1 Existing utility statistic

`U_ds` remains a secondary preflight descriptor: the probability-like train-only statistic measuring whether frozen text similarity ranks the observed next item above popularity-sampled negatives. Its archived four-domain behavior is not promoted to a universal law.

### 6.2 Exact Positive Exposure

For a frozen text proposal `q_text(.|h)`, a frozen core proposal `q_core(.)`, and a training transition `(h,y)`, define log excess positive exposure

\[
\operatorname{EPE}(h,y)
=
\log(q_{\text{text}}(y\mid h)+10^{-12})
-
\log(q_{\text{core}}(y)+10^{-12}).
\]

The dataset statistic is the mean over a frozen sample of 4000 training transitions drawn with sampling seed 7 and clustered by user for uncertainty estimation. Positive EPE means the text proposal exposes the observed next positive more strongly than the host proposal.

### 6.3 Positive-Neighborhood Exposure

Let `N_10(y)` contain `y` and its nine nearest real-item neighbors under the frozen item evidence embedding. Define

\[
\operatorname{PNE@10}(h,y)
=
\sum_{j\in N_{10}(y)}q_{\text{text}}(j\mid h),
\]

and an excess form by subtracting the corresponding core-proposal mass. `EPE` is primary because it uses the observed training positive directly; `PNE@10` is a mechanism visualization and sensitivity measure. The neighborhood excludes padding and the non-preference pseudo-item.

### 6.4 Leakage and provenance contract

Every risk report records:

- source split path and SHA-256;
- item bank path and SHA-256;
- core proposal checkpoint/artifact and SHA-256;
- transition sample IDs or user/row identifiers;
- sampling seed and row count;
- candidate policy;
- exact formulas and epsilon;
- aggregate point estimates and user-clustered intervals;
- no validation/test metric.

If frozen transition records lack user IDs, the bootstrap is marked not estimable. Records may be regenerated only from the frozen train split under a new dated artifact and must reproduce aggregate point estimates before uncertainty is reported; no validation/test transition may be substituted.

## 7. Risk-gated proposal

The method remains a low-capacity interpolation:

\[
p_g(\cdot\mid h)
=
(1-g(h,D))p_{\text{core}}
+g(h,D)q_{\text{text}}(\cdot\mid h).
\]

The gate is

\[
g(h,D)=g_{\max}\,\phi_R(R_D)\,\operatorname{clip}(\widetilde u(h),0,1),
\]

where `R_D` is the frozen dataset/bank risk statistic and `u_tilde` is the existing length-null-calibrated history coherence. `phi_R` must be specified in a dated preregistration artifact after train-only preflight and before pilot training. It must be monotone non-increasing in risk, use no validation/test number, and remain unchanged for every pilot and confirmatory arm.

The host pseudo-item mass remains unchanged. At `g=0`, proposal and derived kernel objects must reduce to the host under identical state-space conventions. No end-to-end performance guarantee follows from this statement.

## 8. E1 implementation amendment

The archived E1 trace is a hard blocker for any training-equivalence claim. The amendment must choose and document one canonical ownership model for the core proposal parameter, then apply it consistently to host, `global_p`, closed-gate full, and nonzero-gate full paths.

The production lockstep trace uses copied initialization, RNG state, ordered batch IDs, selector configuration, and optimizer configuration. It compares steps 0, 1, 100, and 1000 for:

- canonical parameter names and SHA-256;
- trainable flags and optimizer membership;
- optimizer param-group fields and state tensors;
- proposal rows and pseudo-item mass;
- loss terms and total loss;
- gradients and updated parameters;
- RNG state;
- sampling output under a fixed evaluation seed.

The predeclared FP32 maximum absolute tolerance is `1e-6`. Any unexpected difference stops equivalence language and prevents the host/full three-seed matrix from being interpreted as a fallback test. If E1 is not resolved by 2026-07-11 23:59 Asia/Shanghai, the method contribution is downgraded to a kernel-level construction and the 2026-07-14 rescue gate decides whether an audit-only paper remains viable.

## 9. Shared evaluation contract

Every locally rerun method uses:

- `dataset/paper_raw_v1/<dataset>/protocol.json` and the corresponding frozen train/val/test frames;
- native item IDs adapted without dropping catalog rows;
- full-catalog ranking over real items only;
- padding and pseudo-item exclusion documented per model;
- row-weighted tail-complete HR@10 and NDCG@10;
- validation-only checkpoint selection by NDCG@10;
- fixed evaluation RNG where inference is stochastic;
- seed, commit, CLI/config, split hashes, evaluator version, best step, and latest/best checkpoints in an isolated run directory;
- best plus latest checkpoint retention only;
- the reproducibility sentence: model selection used validation only; test metrics were logged during development.

The old Table 2 remains an archived historical table. New confirmatory tables must replace all locally compared methods together under this contract; no selective numeric backfill is allowed.

## 10. Baseline policy

### 10.1 Confirmatory core block

The required block is:

1. SASRec;
2. Caser;
3. GRURec;
4. DiffRec;
5. PreferGrow host variant matching the proposed arm;
6. risk-gated proposal method.

Each external baseline starts with one author-default or published-best configuration frozen before launch, seed 100, and no sweep. Once any model in a baseline row launches, all four datasets must finish or the row is reported incomplete; favorable-subset reporting is forbidden.

### 10.2 Optional block

`BERT4Rec` may run after the core block without being described as an original PreferGrow baseline. `DreamRec`, `PreferDiff`, and `DDSR` require official-code availability and a passed shared-protocol audit before the cutoff. Otherwise they appear only in a separately labeled published-context table without local ranking claims.

### 10.3 DiffuRec exclusion

DiffuRec is absent from the confirmatory model-comparison table and all claims derived from it. A supplementary protocol note states that it was an exploratory external anchor later excluded from the confirmation set because the target original-paper comparator was DiffRec, a different model family. Existing artifacts remain stale-safe and auditable.

## 11. Controlled response experiment

### 11.1 Preflight

For all 12 dataset-level banks, compute `U_ds`, EPE, PNE@10, excess PNE@10, proposal entropy, top-k mass concentration, mean user coherence, mean gate, target popularity, and history-length strata. No training launches unless at least one primary risk statistic spans either a 20% relative range from clean or 0.5 pooled standard deviations across the six levels in each dataset.

### 11.2 Pilot arms

At 0%, 60%, and 100% corruption, run one seed-100 host per dataset and the following arms per level:

- ungated `text_anchor_only`;
- frozen `risk_gated_full`.

The host is shared across corruption levels because it does not consume the evidence bank. If E1 passes, this produces 14 pilot runs across Beauty and Steam: two hosts plus twelve evidence-conditioned runs. If E1 reaches a terminal fail outcome by the R1 deadline, the diagnostic pilot may still run the host and `text_anchor_only` arms only, producing eight runs across the two datasets; no `risk_gated_full` arm, method-performance claim, or training-equivalence claim is authorized on that branch.

### 11.3 Pilot pass criteria

The response-curve story passes only if all conditions below hold without threshold or metric changes:

1. At least one dataset exhibits the preregistered risk ordering across 0%, 60%, and 100% with no opposite adjacent reversal larger than 0.002 NDCG@10.
2. Across the six dataset-condition points, the primary risk statistic and ungated anchor delta have the preregistered negative association with descriptive Spearman `rho <= -0.5`.
3. On the E1-pass branch, the risk-gated arm improves the worst host-relative delta over `text_anchor_only` by at least 0.002 NDCG@10 or halves the magnitude of the worst negative delta, while every launched outcome remains reported. On the E1-fail diagnostic branch this condition is not evaluated and cannot support a method claim.
4. No manifest, split, selector, evaluator, corruption hash, or kernel-version mismatch is present.

If the phenomenon conditions fail, intermediate corruption levels are not trained, the predictive risk claim is removed, and the 2026-07-14 gate selects a submission stop. If the phenomenon conditions pass but E1 fails, the gate may select a bounded audit paper without risk-gated training. No new risk statistic, threshold, finer grid, rescue seed, or tuned corruption level may be introduced in this cycle.

### 11.4 Confirmatory expansion

If the pilot passes, train 20%, 40%, and 80% for the same two evidence-conditioned arms under seed 100, then expand the host/full main matrix and selected mechanism arms to seeds 101 and 102. All response plots display every condition and raw seed point.

## 12. Main and mechanism experiments

### 12.1 Four-domain matched matrix

After E1 passes, run host and risk-gated full on Steam, ML1M, Beauty, and ATG for seeds 100, 101, and 102: 24 isolated training runs. Each seed pair shares initialization policy, batch order policy, selector, split, bank, evaluator, and checkpoint retention.

Primary reporting:

- HR@10 and NDCG@10 per seed;
- mean and standard deviation without significance language based only on three seeds;
- paired host/full delta per seed;
- mean gate, EPE, `U_ds`, and negative-transfer indicator;
- worst-case and average host-relative delta.

### 12.2 Mechanism controls

On one pilot-passing dataset/condition selected by the preregistered highest-risk and lowest-risk anchors, run:

- host;
- `text_anchor_only`;
- `global_p`;
- dataset-gate-only;
- full user-and-dataset gate;
- `u_shuffle`.

The selection rule is frozen from train-only risk, not test performance. Seed 100 runs first; only the full and `u_shuffle` pair expands to seeds 101/102 if the pilot gate passes.

## 13. Statistics and interpretability

### 13.1 Uncertainty

- Training-seed dispersion is reported from seeds 100/101/102 as raw points, mean, and standard deviation.
- Metric uncertainty uses 1000--5000 user-clustered paired bootstrap replicates on host/full differences.
- Risk-statistic uncertainty uses user-clustered resampling of frozen train transitions.
- Training-seed variation and user-level bootstrap uncertainty are never conflated.
- Spearman association is descriptive and accompanied by a dataset-clustered or condition-aware bootstrap sensitivity analysis.

### 13.2 Interpretability outputs

The paper must include:

1. evidence-risk versus host-relative NDCG@10 response curves;
2. exact-positive and positive-neighborhood proposal mass by corruption level;
3. target-popularity, history-length, and risk-quantile slices;
4. gate distributions for aligned and shuffled user signals;
5. at least three qualitative cases showing whether high text mass lands on the actual next item, a close substitute, or an unrelated item.

Captions state what is measured and do not claim causality beyond the controlled intervention.

## 14. Efficiency and resources

The execution budget is:

| Work package | Planned cumulative GPU-days |
|---|---:|
| E1 traces, evaluator checks, smoke tests | 0.1 |
| Beauty/Steam corruption pilot and expansion | 0.8--1.8 |
| Required baseline block | 0.8--2.0 |
| Four-domain three-seed host/full matrix | 5.4--6.9 |
| Selected mechanism controls and efficiency | 0.3--0.8 |
| Total planning range | 7.4--11.6 |

The operational planning target is 10 GPU-days and hard ceiling is 12 GPU-days. With two L20 GPUs, the expected GPU wall clock is 4--6 days; engineering and paper integration make the realistic calendar 5--8 days. Reserve 25--40 GB under isolated run roots. No card hosts more than one training process.

Efficiency profiling uses frozen host/full checkpoints on Steam and ML1M with identical precision and batch size, 100 warm-up batches, 1000 timed batches, and five repeats. Report parameters, checkpoint size, peak memory, train/eval throughput, sampling latency, hardware/software versions, median, and range. If timing coefficient of variation exceeds 5%, repeat the complete protocol once and report both attempts.

## 15. Paper architecture and allowed claims

### 15.1 Recommended narrative

1. External evidence has different semantics in representations and corruption proposals.
2. Existing cross-dataset results motivate a false-positive-exposure risk hypothesis but do not confirm it.
3. A controlled corruption intervention tests the hypothesis prospectively.
4. Train-only risk statistics quantify proposal exposure to observed positives.
5. A low-capacity risk gate shrinks content conditioning when risk is high.
6. Kernel validity and reduction are separated explicitly from end-to-end training and accuracy.
7. Complete positive and negative outcomes define the method boundary.

### 15.2 Contribution claims permitted after their gates pass

- A controlled empirical finding that evidence risk and corruption benefit are non-monotone or inversely associated under the frozen intervention.
- A train-only positive-exposure diagnostic prospectively evaluated on new corruption conditions.
- A risk-gated, structure-preserving proposal interpolation with kernel-level reduction and TV bounds.
- A shared-protocol reliability evaluation including negative transfer, selector/evaluator controls, and implementation tracing.

### 15.3 Forbidden claims

- first-ever, unless a fresh literature verification supports the exact scope;
- universally beneficial or uniformly superior;
- fallback-safe without the qualifier `kernel-level` unless E1 passes;
- significant, stable, statistically equivalent, or within noise from a single run or three raw seeds alone;
- untouched final holdout;
- `U_ds` is a validated universal predictor;
- the proposal TV bound limits NDCG degradation;
- DiffuRec reproduces DiffRec or the original PreferGrow baseline row.

## 16. Result artifacts

The final evidence package contains:

1. `table_shared_protocol_baselines.csv`: all required baseline methods and four domains together.
2. `table_three_seed_host_full.csv`: all 24 host/full runs and paired deltas.
3. `table_mechanism_controls.csv`: every launched control arm.
4. `risk_preflight_report.json`: formulas, hashes, train-only point estimates, and intervals.
5. `risk_response_points.csv`: every dataset, corruption level, arm, seed, metric, and risk statistic.
6. `figure_risk_response.{pdf,svg,png}` generated only from the CSV.
7. `figure_exposure_slices.{pdf,svg,png}` generated only from archived row-level diagnostics.
8. `table_efficiency.csv` with hardware/software provenance.
9. `claim_evidence_traceability.md` mapping contributions to method modules, experiments, tables/figures, allowed wording, and status.
10. a dated paper amendment memo recording removal of DiffuRec from confirmation, preservation of its artifacts, and the exact baseline policy.

No planning or mock number may enter the manuscript as a result. If a result is absent, the table cell is `NA` with a reason rather than an inferred value.

## 17. Stage gates and hard stops

### Gate R0: scope and protocol freeze

Required before new experiments:

- this spec and executable CSV committed;
- DiffuRec exclusion policy recorded without artifact deletion;
- common evaluator and selector contract frozen;
- baseline block and all-four reporting rule frozen;
- GPU budget and deadlines recorded.

### Gate R1: implementation semantics

Deadline: 2026-07-11 23:59 Asia/Shanghai.

- E1 lockstep trace passes, or the paper drops end-to-end equivalence and unqualified safety language;
- no expensive host/full main matrix launches while equivalence is unresolved.

### Gate R2: risk preflight

Deadline: 2026-07-12 23:59 Asia/Shanghai.

- risk formulas, transition sample, corruption banks, hashes, predictions, and `phi_R` are frozen;
- preflight range gate passes before pilot training.

### Gate R3: controlled pilot

Deadline: 2026-07-13 23:59 Asia/Shanghai.

- Beauty and Steam 0/60/100 pilot results complete;
- the response gate is evaluated exactly once;
- failure removes the predictive gate claim and prohibits rescue tuning.

### Gate R4: submission story decision

Deadline: 2026-07-14.

Choose exactly one exit:

1. `risk-gated method`: R1 and R3 pass; proceed to all confirmatory work;
2. `bounded evidence-risk audit`: R3 supports the phenomenon but E1 fails; keep diagnostics and kernel-level construction only;
3. `stop main-track rescue`: the controlled phenomenon does not replicate or protocol parity cannot be established.

### Gate R5: confirmation and integration

- core baseline and three-seed matrix complete before numbers enter the main paper;
- abstract freezes 2026-07-18;
- submission checkpoint remains no later than 2026-07-20;
- full manuscript and supplement follow the 2026-07-27 and 2026-07-30 cutoffs.

## 18. Validation and review

Before the CSV closes, verification must establish:

1. every CSV row has a real artifact or an explicit stopped/not-estimable outcome;
2. all required baselines appear for all four datasets or the entire method row is marked incomplete;
3. no DiffuRec number appears in a confirmatory table or claim;
4. DiffuRec artifacts remain present and hash-auditable;
5. E1 wording matches the actual production trace outcome;
6. every response-curve point traces to a frozen corruption bank and training manifest;
7. every paper number traces to a dated CSV/JSON source;
8. single-run and three-seed language obeys the wording restrictions;
9. English and Chinese manuscripts express the same claims and limitations;
10. the final same-model vision review compares this approved design with the delivered artifacts and appends follow-up rows if any claim/evidence gap remains.

## 19. Execution handoff

The corresponding 19-column issues CSV is the only authorized execution ledger for this rescue. Work outside its rows is prohibited. Row state is updated as evidence lands; a failed gate is closed with its negative outcome rather than bypassed. Generating this spec and CSV does not itself authorize remote training launch: execution begins only after the user explicitly requests CSV execution.
