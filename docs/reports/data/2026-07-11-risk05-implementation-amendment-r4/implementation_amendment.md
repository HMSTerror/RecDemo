# RISK-05 Implementation-Only Amendment for r4

_PreferGrow AAAI-27 · drafted 2026-07-11 · not yet a launch marker_

## 📋 Scope

This amendment preserves the frozen RISK-05 scientific protocol and changes only the implementation/provenance contract required after the failed r3 queue. It does not alter seed, datasets, EPE definition, corruption levels, `phi_R`, thresholds, evaluator, selector, task counts, retry policy, or reporting obligations.

The document is currently `draft_pending_final_commit_and_server_smoke`. It must not be used as a PASS marker or training authorization by itself.

## 🔒 Frozen Scientific Fields

| Field | Frozen value |
|---|---|
| Seed | 100 |
| Domains | Beauty, Steam |
| Asset levels | 0, 20, 40, 60, 80, 100 |
| Pilot levels | 0, 60, 100 |
| Branch sizes | 14 pass-branch tasks; 8 fail-audit tasks |
| Primary risk statistic | EPE, train only |
| Gate formula | `clip((R_100-R_D)/(R_100-R_clean),0,1)` |
| Evaluator | `e0_full_tail_v2` |
| Selector | `validation-ndcg10-rowweighted-v1` |
| Attempts | one; no retry |

Pilot-level `phi_R` values remain:

| Dataset | c0 | c60 | c100 |
|---|---:|---:|---:|
| Beauty | 1.0 | 0.1366311174092942 | 0.0 |
| Steam | 1.0 | 0.05808110271503808 | 0.0 |

## 🔧 Implementation-Only Changes

1. Resolve each embedding from the exact RISK-04 relative path (`level-000/060/100`) and verify its file SHA-256 before emitting a manifest.
2. Use the queue root as the manifest containment root; require every Hydra `work_dir` to equal its task `run_dir`.
3. Pass the frozen `phi_R` as an explicit dataset-gate override for controlled full arms, and require the agreement null curve plus exactly one dataset-gate source.
4. Bind bank, embedding, and RISK-05 preregistration provenance to each evidence-conditioned task.
5. Run only from a clean immutable source root that contains optimizer, EMA, checkpoint, and common-evaluator ownership for graph `p1`.
6. Treat R12 as evidence for revision `0338cc2…`; perform a fresh final-revision verification before r4 launch.

## 🧠 Scientific Claim Boundary

`phi_R` is a controlled-corruption experimental gate derived from preregistered train-only EPE. It is not an undeclared replacement for the paper's four-domain `phi(U_ds)` method. Results from this pilot can test the controlled risk-response prediction; they cannot be inserted directly as four-domain final-v2 efficacy without an explicit method-story amendment.

Unit tests, manifest validation, and no-training smoke establish engineering contracts only. Any completed seed-100 task remains a single-run result/observation; no significance, stability, equivalence, or within-noise wording is authorized.

## 🛑 Finalization Gate

Before this draft becomes runnable, a dated final artifact must record all of the following without placeholders:

- repaired source commit and clean source-manifest SHA-256;
- exact immutable source and new queue roots;
- ledger and config SHA-256;
- exact RISK-04 and RISK-05 bindings;
- validated 22-task manifest SHA-256;
- server-side no-training smoke result;
- a final decision of PASS or STOP.

The frozen values and machine-readable change list are in [implementation_amendment.json](implementation_amendment.json). The original runtime template is retained but marked stale in [RISK-05 freeze status](../2026-07-11-risk05-freeze/STALE.md).
