# SPRINT-07 v2 control arms

## Table

| dataset | arm | status | val_p5_ndcg10 | test_p2_ndcg10 | test_p5_ndcg10 | test_p10_ndcg10 | delta_test_p2_vs_full | delta_test_p2_vs_core | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Beauty | full | completed | 0.024532750777768 | 0.029435971334722 | 0.042029809097732 | 0.040298677463239 | 0 | -0.003858886468956 |  |
| Beauty | u_shuffle | completed | 0.023318789053729 | 0.033003889269924 | 0.042127932860094 | 0.040316663235564 | 0.003567917935202 | -0.000290968533755 | not_degrade |
| Beauty | text_anchor_only | completed | 0.024433820570726 | 0.028988654306103 | 0.040315700530138 | 0.038998491937144 | -0.000447317028619 | -0.004306203497575 |  |
| Beauty | global_p | completed | 0.024532750777768 | 0.029435971334722 | 0.042029809097732 | 0.040298677463239 | 0 | -0.003858886468956 | close |
| Steam | full | completed | 0.016632993411695 | 0.014911009456831 | 0.015140031944749 | 0.016165704843637 | 0 | 0.002015202301118 |  |
| Steam | u_shuffle | completed | 0.015577343667865 | 0.013834261155886 | 0.01395611026239 | 0.015141379190723 | -0.001076748300944 | 0.000938454000173 | degrades |
| Steam | text_anchor_only | completed | 0.031104085587286 | 0.030180637020685 | 0.032028121412696 | 0.035542184560795 | 0.015269627563855 | 0.017284829864973 |  |
| Steam | global_p | completed | 0.015651911258996 | 0.013243762552577 | 0.013868768330687 | 0.015133772100742 | -0.001667246904253 | 0.000347955396865 | close |

## Chinese Summary

### Beauty
- full: status=completed, phi_u_ds=0, val_p5=0.024532750777768, test_p2=0.029435971334722, test_p5=0.042029809097732, test_p10=0.040298677463239.
- u_shuffle vs full: status=completed, verdict=not_degrade, delta_test_p2=0.003567917935202.
- text_anchor_only: status=completed, delta_test_p2_vs_full=-0.000447317028619, last_logged_step=28000.
- global_p vs core: status=completed, phi_u_ds=0, verdict=close, delta_test_p2_vs_core=-0.003858886468956.
- observed full/global_p equality is consistent with phi_u_ds=0 shutting the dataset-level gate off.

### Steam
- full: status=completed, phi_u_ds=1, val_p5=0.016632993411695, test_p2=0.014911009456831, test_p5=0.015140031944749, test_p10=0.016165704843637.
- u_shuffle vs full: status=completed, verdict=degrades, delta_test_p2=-0.001076748300944.
- text_anchor_only: status=completed, delta_test_p2_vs_full=0.015269627563855, last_logged_step=148000.
- global_p vs core: status=completed, phi_u_ds=1, verdict=close, delta_test_p2_vs_core=0.000347955396865.

