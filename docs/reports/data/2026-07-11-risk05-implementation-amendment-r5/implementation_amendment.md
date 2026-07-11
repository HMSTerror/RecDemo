# RISK-05 successor implementation amendment for r5

_PreferGrow AAAI-27 · 2026-07-11 · prelaunch gates passed; one GPU1 controller authorized_

---

## 📋 Decision boundary

r5 is a successor attempt, not a resume of r4. The r4 queue stopped before training because its adapter bound the pilot host to `HybridWise`, which has no learned `p1`. r5 corrects that implementation identity to the paper's already-defined `AdaptiveWise` host and preserves every frozen scientific field.

This amendment is `pass_authorized_for_single_gpu1_controller_launch`. It authorizes one r5 controller on GPU1 under the frozen manifest; it does not authorize performance claims or RISK-08 before complete task artifacts exist.

## 🔒 Immutable bindings

| Binding | Frozen value |
| --- | --- |
| Source revision | `6f18b3d8ecf945fd3230d827db2e813e675af492` |
| Source archive SHA-256 | `c28ce7da6047fd0a35372566e4eaf77efd2175048ce4e8a868e1ade4899fd266` |
| Source root | `/data/Zijian/goal/RecDemo_aaai27_risk0607_6f18b3d` |
| Queue root | `/data/Zijian/goal/aaai27_queue/2026-07-11-risk0607-6f18b3d-r5` |
| Protocol SHA-256 | `3bf4cba9a71bf0232dc9e4d46e451879104428d6037bf5610a2f17faf561afeb` |
| Ledger SHA-256 | `d2e291a9c6695a94ec76575a9259c4753acd4c486f222d238edf6f9929aee39d` |
| Config SHA-256 | `7dcb3eead20011a4f74317506f4b1c6e20f77dd778fd0acba302dabbf660b809` |
| `single_train.py` SHA-256 | `e50c69f573fb4e41269bdfbb5a12ed9595ad11db5636fcdfd8f4849ce21f2196` |

## 🧬 Scientific identity correction

The four pilot host tasks must use `graph.type=adaptive`, own the learned proposal as graph `p1`, and emit `best_summary_adaptive.json`. All 18 evidence-conditioned tasks must use `graph.type=proposal_adaptive` and emit `best_summary_proposal_adaptive.json`. The queue validator rejects either graph or summary identity drift before dispatch.

This is not a change from one valid scientific host to another. It repairs the r4 adapter's mismatch with the host already defined in the paper and tested by E1/R12. No seed, data, corruption level, bank, `phi_R`, threshold, evaluator, selector, optimizer setting, or retry policy is tuned in response to an outcome; r4 produced no outcome.

## 🧪 Frozen pilot fields

| Dataset | `phi_R(c0)` | `phi_R(c60)` | `phi_R(c100)` |
| --- | ---: | ---: | ---: |
| Beauty | 1.0 | 0.1366311174092942 | 0.0 |
| Steam | 1.0 | 0.05808110271503808 | 0.0 |

The pass branch remains 14 tasks and the fail-audit branch remains 8 tasks. Every task uses seed 100, `max_attempts=1`, `failure_policy=fail_closed`, evaluator `e0_full_tail_v2`, and selector `validation-ndcg10-rowweighted-v1`.

## 🚦 Finalization evidence

All prelaunch conditions passed. The uploaded archive and extracted source matched every recorded hash. Manifest SHA-256 `5a7d1c253c88f4689f96e1c9f57b5edac9f429818284e879b702ddb20358f2ed` passed the independent 22-task host/evidence, path, asset and `phi_R` audit; controller validation passed; dry-runs selected 14 E1-pass and 8 E1-fail-audit tasks.

The [final-revision smoke](r5_prelaunch_smoke.json) constructed the production AdaptiveWise host, found graph `p1` exactly once in named/optimizer/EMA ownership, round-tripped a nonuniform `p1` through a temporary checkpoint and common evaluator, deleted the temporary checkpoint, and constructed strict Beauty full-c60 from its real bank, null curve and exact `phi_R`. It called no optimizer step and left queue checkpoint count at zero with no `runs/` directory. The [resource audit](r5_prelaunch_resource_audit.json) records r3 stopped, r4 controller-free, GPU0 external PID untouched, GPU1 free and `/data` above 40 GiB.

Unit tests, manifest validation, dry-runs and no-training smoke are engineering evidence only. Any later seed-100 metric is a single-run result/observation and cannot be described as significant, stable, statistically equivalent, or within noise.
