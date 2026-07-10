# Gate-2 wording amendment memo — 2026-07-10

## Decision

This dated amendment has been applied to the English submission source and the Chinese mirror. It changes claim scope and evidence labels only. The frozen Table 2 metric cells remain unchanged.

The revised paper separates three levels of evidence. The formal result gives exact kernel reduction at \(g=0\). For nonzero gates, the total-variation statement is restricted to the proposal distribution and one forward transition row. The four-dataset results are single-run observations. They are not promoted into an end-to-end production-equivalence claim.

## Evidence read before amendment

| Evidence | Audited result | Wording consequence |
|---|---|---|
| E0 corrected evaluator | All 18 method-dataset artifacts were reevaluated under the same full-tail, row-weighted, real-item contract; Gate-0, Gate-0-v2, Gate-1, and all four preregistered decisions did not flip | DiffuRec evaluator comparability is confirmed only for legacy validation-selected frozen checkpoints under corrected test evaluation; checkpoint-selection equivalence is not claimed |
| E1 production trace | Beauty first diverges at step 0 on `core_proposal_logits.in_optimizer`; `downstream_launch_authorized=false` | The paper records an optimizer-ownership implementation mismatch and does not claim an end-to-end exact-reduction demonstration |
| E7 bootstrap gate | Per-transition and user-cluster resampling units were not archived; zero bootstrap replicates were run | `1/24` is only the descriptive fraction for one specified order among \(4!\) equally likely label orders under exchangeability, not a confirmatory p-value |
| CLOSE-02 ML1M | Measured maximum pairwise host spread is `0.003171207143786`; the frozen Table 2 gap is `0.015133045070724` and the E0-corrected gap is `0.014850532981` | The closed-gate ML1M miss is outside the measured host run-to-run floor and remains an implementation question |
| CLOSE-10 ATG | Completed p2 NDCG@10 readouts are `0.0397181623215186`, `0.04129374588439805`, and `0.0423501067251558`; maximum observed spread is `0.002631944403637204`; the E0-corrected ATG gap is `0.011505201353104493` or `4.3713694473x` the spread | The paper calls this a provenance-limited observed three-run spread. All three frozen manifests are absent, so it does not claim complete configuration parity or a fully manifested ATG noise floor |

Source SHA-256 values:

```text
da11d9f7307ad4377c9bf02d378fbf69bddae0453be3403502ef7c0ec3c4f9e5  E0/e0_evaluator_amendment.json
b19d9473c8864028aec2de0421971f14c31603a14f510966fde3dd654ff8e43a  E1/e01_hard_stop.json
1bde287a1fa3b4a6753dd7dde2739d436895ead46f4469a9016ea53c22e9d8d7  E7/e07_evidence_gate.json
37b6cfbb69f7a0435a76fd6d140c8eba186f1694595df2959e6579cbc378655c  CLOSE-02/close02_ml1m_noise_floor_report.json
cf615cdf2bb6392e6fef62e7e44a1c5bbed75edece3b9a3fdc4ec3a69d6e2dc0  CLOSE-10/close10_atg_provenance_limited_report.json
```

## Applied English changes

The abstract, contribution list, experiment setup, four-dataset interpretation, conclusion, limitations, first-generation corruption discussion, and reproducibility statement were synchronized to the following rules:

- `bounded downside` is no longer used as an end-to-end performance statement. The manuscript names proposal TV and one-step transition-row TV explicitly.
- ATG `phi=0.117` is called barely-open wherever the empirical miss is interpreted. The rounded `0.12` display in frozen Table 2 is retained.
- The four-domain readout is described as one closed-gate Beauty parity hit, one closed-gate ML1M miss, one barely-open ATG miss, and one fully open Steam directional hit that misses its reference magnitude.
- ML1M is compared with its measured host floor. ATG is compared only with the provenance-limited observed three-run spread and carries the missing-manifest limitation in the abstract, experiment interpretation, and limitations.
- E1's step-0 optimizer-ownership mismatch is reported. E2 and E3 were not launched after the hard stop, so no stronger ATG attribution or final-v2 corruption-response claim is made.
- First-generation corruption numbers remain as limited historical observations; they are not presented as final-v2 corruption-response evidence.
- DiffuRec is marked comparable under the corrected common test evaluator only. The paper does not claim that DiffuRec and the in-house runs used equivalent checkpoint-selection procedures.
- The following reproducibility disclosure is included verbatim: “Model selection used validation only; test metrics were logged during development. Accordingly, we do not describe the test split as an untouched final holdout.”

## 中文同步

中文对照稿同步执行同一证据边界：TV 界只覆盖 proposal 与单步前向转移行；`1/24` 只是在 exchangeability 假设下的描述性组合比例；ATG 的 `φ=0.117` 始终标为 barely-open；ML1M 与测得的宿主噪声地板比较，而 ATG 只与 provenance-limited 三次运行观测 spread 比较并明确三份 manifest 均缺失。E1 的 step-0 optimizer ownership 差异、E2/E3 未启动、DiffuRec 可比性范围和开发期 test logging 声明也已同步。

## Frozen-number audit

The amendment does not replace Table 2's four metric rows:

```text
Steam  host=0.0129 ours=0.0149 delta=+0.0020
ATG    host=0.0419 ours=0.0305 delta=-0.0114
Beauty host=0.0333 ours=0.0294 delta=-0.0039
ML1M   host=0.0910 ours=0.0759 delta=-0.0151
```

Only the ATG interpretation label changes to barely-open parity miss. E0 corrected metrics remain in the dated evaluator amendment and are not selectively copied into Table 2.

## Launch consequences

E1's hard stop removes launch authorization for E2, E3, E4, E5, and E8 in this sprint. E6 and E9 remain zero-launch deferred rows. The paper therefore records the missing final-v2 attribution/corruption evidence as a limitation instead of introducing replacement runs or rescue wording.

## Review gates

The spec-compliance review must verify all requested English/Chinese claim pairs, the exact reproducibility sentence, unchanged Table 2 metric cells, and the E1/CLOSE-10 limitations. The quality review must reject any end-to-end extension of the TV bound, inferential use of `1/24`, unqualified ATG floor language, checkpoint-selection-equivalence wording, or a final-v2 corruption-response claim.

