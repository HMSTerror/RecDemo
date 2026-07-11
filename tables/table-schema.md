# 论文表结构与数据契约

_所有表只接受真实 dated artifacts；规划阶段不创建 mock 数值。_

---

| 表 | 目的 | 行 | 指标/字段 | 数据源 | 替换责任 |
|---|---|---|---|---|---|
| Table 1 | 数据与 utility preflight | 四域 | users/items、train rows、`U_ds`、`phi`、bank/split hash | Gate-0 JSON；E7 bootstrap | utility owner |
| Table 2 | 主方法与 host/full-v2 | 四域×方法 | NDCG@10、HR@10、validation selector、single/multi-seed tag | E0/e0_full_tail_v2 artifacts | evaluator owner |
| Table 3 | corruption dose response | Beauty/Steam×c0/c60/c100 | EPE、mean gate、`phi_R`、relative drop | RISK-04/05 + pilot | risk-pilot owner |
| Table 4 | 经典外部 baseline | SASRec×四域（必要时 Caser/GRURec） | same split/full catalog/NDCG@10/HR@10 | atomic baseline queue | baseline owner |
| Table 5 | attribution controls | ATG controls×四域 target | global-p、u-shuffle、dataset-gate-only、full | E2 artifacts | attribution owner |
| Table 6 | replication and uncertainty | 四域×seed | mean、std、95% CI、order retention | seed reruns + E7 | statistics owner |
| Table 7 | efficiency | method×dataset | wall hours、GPU-hours、peak VRAM、disk delta、steps | queue/controller logs | operations owner |

## 🧮 聚合规则

主指标按 frozen evaluator 的 row-weighted full-catalog 定义汇总；三 seed 先在 seed 内汇总再跨 seed 汇总，不能把用户行当作独立 seed。CI 使用冻结 transition-user records 的 user-cluster bootstrap；缺少原始 records 时表格填 `NA (input missing)`，不自行重采样。单 seed 行必须标注 `single-run observation`。
