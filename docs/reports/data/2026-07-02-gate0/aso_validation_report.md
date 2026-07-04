# ASO Frozen Validation Report

- Dataset: `ASO`
- Scientific role: `pure_out_of_sample_prediction_point`
- Evaluated at: `2026-07-04T14:42:36+08:00`
- Step-0 report: `E:\PreferGrow\docs\reports\data\2026-07-02-gate0\aso_step0_report.json`
- Pre-registered prediction tier: `phi_ge_0p5_positive`
- Pre-registered prediction: `delta_test_p2_ndcg10 > 0`
- Evaluation rule: `delta_test_p2_ndcg10 > 0`
- Prediction outcome: `MISS`

## Frozen Launch Checks

- `PASS` Manifest dataset matches the frozen ASO step-0 report: manifest=ASO step0=ASO
- `PASS` The frozen rule opened the run because phi(U_ds) > 0: phi(U_ds)=1.000000; run_decision=launch_validation_run
- `PASS` Manifest utility artifact path matches the frozen step-0 source: manifest=/data/Zijian/goal/RecDemo/docs/reports/data/2026-07-02-gate0/aso_step0_utility/gate0_text_utility_report.json step0=/data/Zijian/goal/RecDemo/docs/reports/data/2026-07-02-gate0/aso_step0_utility/gate0_text_utility_report.json
- `PASS` Manifest U_ds / phi / hashes match the frozen step-0 decision: u_ds=0.537923/0.537923; phi=1.000000/1.000000
- `PASS` Frozen storage policy is best-checkpoint only: write_best_checkpoint=True; write_snapshot_checkpoint=False
- `PASS` Early-stop selector is ndcg10 at p5: early_stop_metric=ndcg10; early_stop_strength=p5

## Artifact Sources

- Core summary copy: `E:\PreferGrow\docs\reports\data\2026-07-02-gate0\aso_validation_inputs\aso_core_best_summary_hybrid.json`
- Core summary source: `/data/Zijian/goal/RecDemo/checkpoints-meta/ASO/best_summary_hybrid.json`
- Core summary sha256: `8ffb94d8193f7776e6d649259b9a077f8142d315293925399f072f2453b0687f`
- Run summary copy: `E:\PreferGrow\docs\reports\data\2026-07-02-gate0\aso_validation_inputs\aso_validation_best_summary_proposal_adaptive.json`
- Run summary source: `/data/Zijian/goal/RecDemoRuns/main_table_text_side/aso_proposal_adaptive_mainpath/checkpoints-meta/ASO/best_summary_proposal_adaptive.json`
- Run summary sha256: `cb66aba13fc86ccbb92c075796bc3dd66f34ba868773777a8bfbdb08b451c89e`
- Run manifest copy: `E:\PreferGrow\docs\reports\data\2026-07-02-gate0\aso_validation_inputs\aso_validation_frozen_run_manifest.json`
- Run manifest source: `/data/Zijian/goal/RecDemoRuns/main_table_text_side/aso_proposal_adaptive_mainpath/checkpoints-meta/ASO/frozen_run_manifest.json`
- Run manifest sha256: `d576683b1a00710d959954433f3bfd84de8bae9ab84aee2494799f507c0e4b4c`

## Outcome vs Frozen Host

| Metric | Frozen host | Frozen-gate ASO | Delta |
| --- | ---: | ---: | ---: |
| Validation NDCG@10 (p2) | 0.047704 | 0.035216 | -0.012488 |
| Test NDCG@10 (p2) | 0.037325 | 0.026499 | -0.010826 |
| Test NDCG@10 (p5) | 0.035194 | 0.026709 | -0.008485 |
| Test NDCG@10 (p10) | 0.034421 | 0.026819 | -0.007602 |

## Decision

- The frozen ASO prediction missed: phi(U_ds) opened the gate and predicted a positive delta, but the observed test p2 delta versus the frozen host is negative.
- This report records the frozen prediction exactly as specified. It does not change any threshold, tier, or launch rule after observing ASO.
