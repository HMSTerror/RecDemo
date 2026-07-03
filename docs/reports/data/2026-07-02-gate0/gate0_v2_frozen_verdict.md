# Gate 0-v2 Frozen Criterion Verdict

- Source report JSON: `E:\PreferGrow\docs\reports\data\2026-07-02-gate0\gate0_text_utility_report.json`
- Evaluated at: `2026-07-03T14:36:27+08:00`
- Verdict: `FAILED`
- `SPRINT-05` decision: `blocked_family_d_downgrade`

## Dataset inputs

| Dataset | U_ds | phi(U_ds) | bank_hash | split_hash |
| --- | ---: | ---: | --- | --- |
| ML1M | 0.753539 | 0.000000 | `76fcfc25668145bfbaba194f2f0f652acda0c424363f689f35bb653eb525497d` | `7895e743467fd60060127264894250a0502d94028e84441400aa14dfd9118576` |
| Steam | 0.569566 | 1.000000 | `78fed57c4afba29031624357ad7b8e543aa20a0b06b3373e69525625e6e78023` | `a0e0a7e03cb0823386da7f0832f595253633014dd50f64fc63c2d431d0f84006` |
| Beauty | 0.712427 | 0.000000 | `591e4f4ee24160becd190f2b5279a48a351004ff6fd09f228473188a182b5d9b` | `ab2863e37b13290aa216ae4c83c725a852e2a7fdd9325afb1d501e0141e3f2b6` |
| ATG | 0.688262 | 0.117375 | `90ac91f8d54a19cf5f0c70a304b0a6ddf63d5803e45f0a85e293377642b9812f` | `33315c196f7a377a223f2a20705d3557e827c39c547baf16b69645f2e43db0ec` |

## Frozen conditions

1. Condition 1: ML1M has the maximum U_ds: `PASSED`
   - margin: `0.041111`
   - detail: ranking=['ML1M', 'Beauty', 'ATG', 'Steam']; ML1M U_ds=0.753539; next-best non-ML1M U_ds=0.712427
2. Condition 2: phi(U_ML1M) <= 0.2: `PASSED`
   - margin: `0.200000`
   - detail: phi(U_ML1M)=0.000000; threshold=0.200000
3. Condition 3: at least two of Steam/Beauty/ATG have phi(U_ds) >= 0.5: `FAILED`
   - margin: `-1.000000`
   - detail: qualifying_datasets=['Steam']; count=1; required_count=2

## Decision

- `criterion_pass`: `false`
- `third_gate_repair_round_allowed`: `false`
- Action: Frozen Gate 0-v2 criterion failed; keep SPRINT-05 blocked and switch to the Family D claim-downgrade path.
- Family D deadline: `2026-07-07`
