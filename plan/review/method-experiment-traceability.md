# 方法—实验—证据追溯矩阵

_本矩阵防止引言中的贡献没有对应实验，或把工程契约写成性能结论。_

---

| 贡献/主张 | 方法模块 | 实验 | 表/图 | 允许表述 | 证据状态 |
|---|---|---|---|---|---|
| train-only `U_ds` 能预警文本污染风险 | utility preflight、null calibration、hinge `phi` | Gate-0 四域 utility；bootstrap E7 | Table 1、Fig. 2 | 四域描述性 inversion；不得称 population law | Gate-0 artifact；CI 未完成 |
| `g=0` 精确回退 host kernel | proposal gate、shared tensor、fallback branches | E1/R12 lockstep | Table 2、Fig. 1 | 指定 revision/path 的 implementation trace | 2986/2986 trace pass |
| kernel-level downside 可界定 | one-step proposal TV bound | theory unit + transition-row audit | Theory box、Fig. 1 | 仅 proposal/单步 transition-row kernel-level bound | 需正文与实验边界同步 |
| controlled corruption 改变风险而非改变数据语义 | RISK-04 banks、frozen `phi_R` | Steam c60 preflight、Beauty/Steam pilot | Fig. 3、Table 3 | preflight authorizes pilot；不能替代 efficacy | severe gate pass；pilot pending |
| 方法优于/可比经典推荐器 | frozen host/full-v2 + common evaluator | SASRec 四域，必要时 Caser/GRURec | Table 4 | only if four-domain atomic group completes | 未开始 |
| 结果不是 gate-specific artifact | ATG attribution、u-shuffle、global-p | E2 | Table 5 | attribution observation with controls | 未开始 |
| 结果不依赖单 seed | seed 100/101/102 matched rerun | CLOSE-10/三 seed | Table 6 | mean/CI/dispersion after completion | seed100 path pending |
| 可复现且资源代价可接受 | queue manifest、runtime、logging | efficiency audit | Table 7 | wall time/GPU-hour/storage report | 未开始 |

## 🔍 证据边界

R3/r4/r5 的失败或 prelaunch audit 用于解释实现风险与 fail-closed 价值，不得回填性能表。DiffuRec 已从 confirmatory comparison 排除；E0 中出现的 provenance 记录只用于 evaluator scale audit。DiffRec 若未按共同协议运行，只能列为 cited/audit-only，不得声称公平 baseline 已存在。
