# RISK-05 Implementation-Only Amendment for r4

_PreferGrow AAAI-27 · finalized 2026-07-11 · STOP before training_

---

## 📋 Scope

This amendment preserves the frozen RISK-05 scientific protocol and changes only the implementation/provenance contract required after the failed r3 queue. It does not alter seed, datasets, EPE definition, corruption levels, `phi_R`, thresholds, evaluator, selector, task counts, retry policy, or reporting obligations.

The r4 amendment is finalized as `stop_prelaunch_host_identity_mismatch`. It is not a PASS marker and does not authorize training.

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
6. Treat R12 as evidence for revision `0338cc2…`; require a fresh final-revision verification before any successor launch.

## 🧠 Scientific Claim Boundary

`phi_R` is a controlled-corruption experimental gate derived from preregistered train-only EPE. It is not an undeclared replacement for the paper's four-domain `phi(U_ds)` method. Results from this pilot can test the controlled risk-response prediction; they cannot be inserted directly as four-domain final-v2 efficacy without an explicit method-story amendment.

Unit tests, manifest validation, and no-training smoke establish engineering contracts only. Any completed seed-100 task remains a single-run result/observation; no significance, stability, equivalence, or within-noise wording is authorized.

## 🚫 r4 finalization outcome

The r4 protocol was emitted with SHA-256 `b37661a887d3c583e4528c73bec56451b272da18bcfac08637488eae19e02f06`, and its 22-task manifest was emitted with SHA-256 `8d5989f6e91006b0ab7ffe0e3326945719964d9ffec98e4f2742450723801838`. Independent inspection then found that all four host tasks used `graph.type=hybrid`, whereas the paper and E1/R12 define the learned-proposal fallback host as `AdaptiveWise` with graph-owned `p1`.

The controller never started, `record_count=0`, `actual_gpu_hours=0.0`, `running=0`, and the queue had no `runs/` directory. r4 is therefore preserved as a prelaunch-invalid audit artifact and is ineligible for RISK-08. It must not be deleted, overwritten, resumed, or reinterpreted as a model result.

The frozen values and machine-readable STOP decision are in [implementation_amendment.json](implementation_amendment.json). The exact failure evidence is in the [r4 host-identity audit](../2026-07-11-risk0607-r4-prelaunch-host-identity-audit/risk0607_r4_prelaunch_host_identity_audit.md). The original runtime template remains retained and marked stale in [RISK-05 freeze status](../2026-07-11-risk05-freeze/STALE.md).
