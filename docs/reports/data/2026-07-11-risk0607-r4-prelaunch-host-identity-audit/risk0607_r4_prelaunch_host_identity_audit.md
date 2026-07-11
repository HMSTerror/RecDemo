# RISK-06/RISK-07 r4 prelaunch host-identity audit

_PreferGrow AAAI-27 · checked 2026-07-11 19:29:28 +08:00 · manifest and read-only runtime evidence only_

---

## 📋 Decision

The r4 queue is **prelaunch-invalid** and must not be started, resumed, reused, or supplied to RISK-08. Its manifest was built successfully, but its four `host` tasks use `graph.type=hybrid`. The paper and E1/R12 contract define the fallback host as `AdaptiveWise`, whose learned proposal is `softmax(p1)`.

No r4 training started. The read-only controller status reported `controller=null`, `tmux=null`, `record_count=0`, `actual_gpu_hours=0.0`, and `running=0`; the `runs/` directory was absent.

## 🔬 Identity evidence

| Contract surface | r4 observation | Required identity | Verdict |
| --- | --- | --- | --- |
| Host graph argv | `graph.type=hybrid` | `graph.type=adaptive` | Fail |
| Host proposal | Fixed HybridWise mixture | Learned `softmax(p1)` | Fail |
| Host summary | `best_summary_hybrid.json` | `best_summary_adaptive.json` | Fail |
| Evidence arms | `graph.type=proposal_adaptive` | `graph.type=proposal_adaptive` | Match |
| Seed/evaluator/selector | `100` / `e0_full_tail_v2` / validation-only selector | Frozen values | Match |

The mismatch originates in `scripts/aaai27_adapters/pilot_adapters.py`, which hard-coded `hybrid` for the pilot host. `scripts/aaai27_queue/validation.py` accepted it because the validator checked the dataset/arm matrix without checking graph or summary identity.

## 🛡️ Disposition

- Preserve the r4 root and manifest SHA-256 `8d5989f6e91006b0ab7ffe0e3326945719964d9ffec98e4f2742450723801838`
- Do not create a stop marker solely to compensate for a controller that never started
- Do not delete, overwrite, resume, or reinterpret r4
- Do not call this a training failure, model result, or performance observation
- Create a successor only from a new committed immutable source and a never-used dated queue root
- Require the host-identity regression, queue validator, checkpoint/common-evaluator smoke, strict real-asset full construction, and resource gates to pass before launch

## 🔒 Claim boundary

This artifact proves only that a prelaunch scientific-identity invariant failed and that zero r4 training occurred. It supplies no evidence about recommendation quality, corruption response, gate efficacy, or RISK-08.
