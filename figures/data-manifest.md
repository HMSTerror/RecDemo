# 论文图表数据清单

_图表只从真实 CSV/JSON 生成；当前清单描述所需数据与状态，不是模拟图。_

---

| 图 | 类型 | 横轴/纵轴 | 数据源 | 当前状态 | 允许 caption |
|---|---|---|---|---|---|
| Fig. 1 | Mermaid flowchart | evidence → gate → kernel → evaluator | spec、E1 trace、RISK-08 | 可先画结构图 | implementation and evidence boundary |
| Fig. 2 | scatter + 95% CI | x=`U_ds`，y=host/full delta | Gate-0 + E0/pilot；E7 CI | CI 未完成 | descriptive cross-dataset relation |
| Fig. 3 | line plot | x=corruption level，y=mean gate/EPE | RISK-04/05 + pilot | c0/c60/c100 pilot pending | controlled corruption response |
| Fig. 4 | bar/box plot | method×dataset NDCG@10 | Table 2/4/6 real logs | SASRec/三 seed pending | matched evaluator comparison |
| Fig. 5 | Pareto/scatter | GPU-hours vs NDCG@10 | efficiency logs | 未开始 | accuracy–cost observation |

## 🔗 数据文件约束

每个图必须列出 input path、SHA-256、生成脚本 revision、过滤规则和是否 test metric。不得从论文正文手抄数字；不得把 synthetic manifest、unit test 或 no-training smoke 作为性能输入。
