# EPE / `phi_R` dated method amendment and r6a evidence arbitration

Date: 2026-07-12 (Asia/Shanghai)

Status: evidence amendment for the r7 attempt. This is not a retroactive preregistration and does not change any RISK-05 number, prediction, threshold, seed, corruption level, or no-rescue rule.

Machine-readable evidence: `r6a_evidence_manifest.json` in this directory.

## 1. What is proven by the frozen artifacts

The r6a E1-pass branch completed eight of fourteen tasks: the two hosts and six full arms across Beauty and Steam. All six anchor-only tasks failed before training because their argv did not supply an explicit gate-scale override. The loader consequently auto-discovered the clean utility report; the corrupted/c0 bank identity did not match that report and the fail-closed check rejected the task. The active production `model/text_side.py` also contains a later closed-gate branch keyed by `self.gate_dataset_scale == 0.0`; therefore merely making the report load would not have been sufficient for a valid anchor control on a clean-`phi=0` dataset.

The r7 repair is correspondingly narrow: anchor-only argv will receive exactly one `text_side.gate_dataset_scale_override=1.0`. Production `model/text_side.py` remains unchanged. The repair is valid only after a final-proposal probe establishes both `proposal != p_core` and equality to the fixed `g_max` anchor mixture.

## 2. c100 interpretation is now fixed

The six full-arm argv entries are present verbatim in the r6a queue manifest. Beauty and Steam c100 each explicitly contain:

```text
text_side.gate_dataset_scale_override=0.0
```

Thus c100 did not demonstrate spontaneous collapse of the history-level factor `u_tilde`. The dataset scale was zero before that factor could contribute. The earlier tentative explanation is withdrawn and must not appear in the paper, runbooks, captions, or handoff prompts.

The correct artifact-level observation is narrower:

- Beauty host and full-c100 selected best summaries share SHA-256 `b3d3b248...d1d6b9`;
- Steam host and full-c100 selected best summaries share SHA-256 `8679393e...c1b65`;
- the corresponding checkpoints are not byte-identical: Beauty uses `ea8323c1...d4c0dc` versus `69aa1c96...a5dbd`, and Steam uses `70c71ae...61fb8` versus `d9f5a4a8...862de`.

Permitted wording:

> Under preregistered `phi_R=0`, the production training path selected a best-summary artifact byte-identical to the matched host; checkpoints differ because the full arm serializes additional text-side state.

This is a strong implementation sanity check and an independent companion to E1/R12. It is not a nontrivial efficacy result and is not evidence of adaptive user-level backoff.

## 3. Three method generations must remain separate

The evidence chain contains three distinct objects:

1. Legacy `U_ds` is a train-only discovery descriptor. Its legacy four-domain inverse ordering motivated the risk audit but is not a universal law and does not become confirmatory merely because it was observed first.
2. RISK-03 EPE is the mean log excess mass that the frozen text proposal assigns to the observed next positive relative to the frozen core proposal. PNE@10 is a neighborhood-mass visualization. These are train-only exposure measurements, not end-to-end recommendation metrics.
3. r6a/r7 uses the dated RISK-05 numerical `phi_R` override. It is not the legacy `phi(U_ds)` hinge and must be identified as a method amendment wherever r6a/r7 results appear.

No new FPM statistic is needed in this cycle: EPE and PNE@10 already implement the direct observed-positive and observed-positive-neighborhood exposure audit. E7 remains incomplete, because all selected RISK-03 reports record `not_estimable`, reason `user IDs absent for one or more sampled train transitions`, and `bootstrap_replicates=0`. The configured value 1000 is a request, not an executed bootstrap count. Regenerating records requires a separate user-approved dated protocol amendment and is not authorized here.

## 4. Frozen `phi_R` sign inconsistency

RISK-03 defines positive EPE as stronger exposure of the observed next positive. The parent design then requires a dataset gate that is monotone non-increasing in that risk. The frozen RISK-05 implementation and artifact instead use:

```text
phi_R(D) = clip((R_100 - R_D) / (R_100 - R_clean), 0, 1)
```

For both datasets, `R_clean > R_100`. Algebraically, the derivative with respect to `R_D` is `-1/(R_100-R_clean) > 0`; the implemented mapping is therefore monotone increasing in EPE. The frozen values are:

| Dataset | c0 | c60 | c100 |
|---|---:|---:|---:|
| Beauty | 1.000000 | 0.136631 | 0.000000 |
| Steam | 1.000000 | 0.058081 | 0.000000 |

The implementation is coherent if `phi_R` is interpreted as evidence retention or corruption reliability: clean evidence opens the dataset scale and fully permuted evidence closes it. It is not coherent as a demonstrated rule that directly suppresses high positive-exposure risk, because higher clean EPE receives the larger scale.

This amendment does not change the frozen function after results. Instead it narrows the scientific claim:

- EPE/PNE@10 measure observed-positive exposure;
- `phi_R` in r6a/r7 is a corruption-response reliability scale;
- the r7 controlled pilot tests reliability/fallback behavior under this scale;
- even a mechanical RISK-08 PASS cannot alone establish that high EPE causes the gate to close.

The existing RISK-05 machine label and original RISK-08 exit vocabulary remain preserved for provenance. Paper prose must use the narrower interpretation and cite this amendment.

## 5. r6a single-run observations and Beauty disclosure

All values below are seed-100 single-run observations selected by validation p5 NDCG@10 under evaluator `e0_full_tail_v2`.

| Dataset | Arm | Best step | Val NDCG@10 | Val delta | Test NDCG@10 | Test delta |
|---|---|---:|---:|---:|---:|---:|
| Beauty | host | 7,000 | 0.022175 | — | 0.038195 | — |
| Beauty | full c0 | 7,000 | 0.022174 | -0.000002 | 0.039851 | +0.001656 |
| Beauty | full c60 | 6,000 | 0.022212 | +0.000037 | 0.039824 | +0.001629 |
| Beauty | full c100 | 7,000 | 0.022175 | 0.000000 | 0.038195 | 0.000000 |
| Steam | host | 28,000 | 0.013720 | — | 0.012234 | — |
| Steam | full c0 | 32,000 | 0.014807 | +0.001087 | 0.013752 | +0.001519 |
| Steam | full c60 | 70,000 | 0.016339 | +0.002619 | 0.015107 | +0.002874 |
| Steam | full c100 | 28,000 | 0.013720 | 0.000000 | 0.012234 | 0.000000 |

Steam c60 is the strongest nontrivial completed point because validation and test move in the same direction. Beauty c0/c60 are test-only positive observations: their validation deltas are approximately zero. Any paper table or figure that includes the Beauty test values must include validation beside them and state:

> Model selection used validation only; test metrics were logged during development.

The project must not call the Beauty values significant, stable, statistically equivalent, or within noise.

## 6. Evidence strength and remaining gap

Evidence grading for the paper:

| Claim | Evidence level | Permitted scope |
|---|---|---|
| E1/R12 specified-path exact fallback | production trace, 2,986 comparisons and zero failures | designated revision/path only |
| r6a c100 host recovery | selected best-summary byte identity under explicit `phi_R=0` | implementation sanity check only |
| EPE/PNE@10 values | train-only artifact-proven point estimates | observed-positive exposure proxy; no user CI |
| r6a c0/c60 effects | seed-100 selected summaries | single-run observations only |
| anchor attribution and RISK-08 | absent in r6a | requires complete r7 fourteen-task evidence |
| E7 uncertainty | not estimable, zero executed replicates | limitation only |

The r7 attempt is necessary because r6a has zero per-run `artifact_manifest.json` files, fourteen zero-byte run-local `single_train.log` files, six failed anchors, and no RISK-08 exit. A six-arm append cannot satisfy the original same-root fourteen-artifact RISK-08 contract. The only non-post-hoc repair is a full dated r7 attempt with the frozen numeric protocol, corrected anchor gate source, nonempty logs, and automatically generated provenance manifests.

## 7. Frozen-root protection

This memo was produced from read-only SSH inspection. It does not modify r6a, RISK-03, RISK-04, RISK-05, E1/R12, Gate-1, SPRINT-07, or any other frozen artifact. The r7 source and queue must be created at new dated absent paths. Before deployment, and again after deployment, the four r6a source-file hashes in `r6a_evidence_manifest.json` must be recomputed; any change is a hard stop.
