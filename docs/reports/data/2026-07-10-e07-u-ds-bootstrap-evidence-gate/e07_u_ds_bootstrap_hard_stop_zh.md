# AAAI-E07 U-ds Bootstrap 证据门报告

_2026-07-10，针对冻结 Gate-0 四域样本的只读证据审计_

---

## 🚫 结论

`AAAI-E07` 触发 **HARD STOP**，本轮没有运行 bootstrap。正式 Gate-0 归档只保留四域汇总值和 coherence 四分位汇总，没有保留逐 transition utility、原始负样本 ID、transition ID 或用户聚类标识。因此，无法在不重新生成 transition/negative 的前提下进行 user-clustered bootstrap，也不能计算四域 `U_ds` 的 95% 区间或全序保留概率。

本轮执行的 bootstrap replicate 数为 `0`；该数值表示证据门阻止了统计计算，不表示区间宽度或不确定性为零。

## 📊 已归档的点估计

下表仅转录正式 Gate-0 汇总工件中的观测点估计，不把四行汇总数据当作 bootstrap 样本。

| 数据集 | 报告的样本 transition 数 | `U_ds` popularity | `U_ds` uniform |
| --- | ---: | ---: | ---: |
| ML1M | 4,000 | 0.75353875 | 0.79852625 |
| Beauty | 4,000 | 0.71242750 | 0.71720375 |
| ATG | 4,000 | 0.68826250 | 0.69201250 |
| Steam | 4,000 | 0.56956625 | 0.56507875 |

观测点估计的降序为 `ML1M > Beauty > ATG > Steam`。由于缺少逐 transition 与用户聚类证据，本报告不提供 95% 区间，也不提供该全序的 bootstrap 保留概率。

## 🔎 证据门依据

| 检查项 | 结果 | 判定依据 |
| --- | --- | --- |
| 正式 Gate-0 JSON | 仅四域汇总及 16 个四分位汇总 | 无 transition ID、user ID 或逐行 utility |
| 正式 Gate-0 summary CSV | 每域一行 | 4 行不能恢复 16,000 个 transition 的联合分布 |
| 正式 coherence CSV | 每域四行 | 四分位均值不能恢复域内或用户内变异 |
| Gate-0 生成脚本 | 逐 transition 数组只驻留内存 | 落盘仅写 dataset summary 与 quartile summary |
| l20 正式归档 | 共 23 个文件，无合格逐 transition 工件 | 文件名检索与内容级 schema 检索一致 |
| Git 历史 | 仅见 FOLLOWUP-09 的 ML1M/Steam 逐点文件 | 不存在四域 Gate-0 逐记录集合 |
| FOLLOWUP-09 | ML1M 19,328 行；Steam 127,292 行 | 每用户四行、缺 uniform utility、域不全且不是 Gate-0 4,000 行样本 |

本地与 l20 的四个核心来源 SHA-256 完全一致；精确 hash、排除理由与候选清单见 `e07_evidence_gate.json` 和 `e07_evidence_inventory.csv`。

## 🧪 负样本定义与统计边界

`popularity` negative 是从训练集 next-item 的经验分布中有放回抽取 100 个 item；`uniform` negative 是在完整 item ID 区间均匀有放回抽取 100 个 item。逐 transition utility 为真实 next item 与 100 个 negative 的余弦相似度逐对比较均值，严格大于计 `1`、相等计 `0.5`。

原生成脚本使用 sampling seed `7`，但没有归档实际抽中的 transition、negative ID 或逐 transition utility。重新运行该脚本会重新生成证据，违反本轮“只使用已归档记录”的约束，因此没有执行。

`p=1/24` 只能表述为：在 exchangeability 假设下，若四个标签的 `4!` 种全序等可能，某一指定全序对应 `1/24` 的描述性组合比例。它不是确认性 p 值，本报告也没有进行显著性检验。

## 🔒 本轮未执行的操作

- 未重新采样 transition
- 未重新生成 popularity 或 uniform negatives
- 未把四分位均值伪装成逐 transition 记录
- 未用 FOLLOWUP-09 的两域记录替换 Gate-0 四域样本
- 未启动训练或新增 model seed
- 未补造置信区间、全序保留概率或 training-seed variance

## 🔧 可审计命令

```powershell
rg --files docs/reports/data/2026-07-02-gate0
rg -n "to_csv|sampled_df|popularity_scores|uniform_scores|user_id" scripts/build_gate0_text_utility_report.py
git rev-list --objects --all | rg -i "(gate0|utility).*(transition|score|record|point)"
git log --all --name-only --pretty=format: -- "docs/reports/data/**"
Get-FileHash -Algorithm SHA256 scripts/build_gate0_text_utility_report.py,docs/reports/data/2026-07-02-gate0/gate0_text_utility_report.json,docs/reports/data/2026-07-02-gate0/gate0_text_utility_summary.csv,docs/reports/data/2026-07-02-gate0/gate0_text_utility_coherence_quartiles.csv
```

```bash
find /data/Zijian/goal/RecDemo/docs/reports/data/2026-07-02-gate0 -maxdepth 4 -type f
grep -RIl --include='*.csv' --include='*.json' --include='*.jsonl' 'utility_popularity' /data/Zijian/goal/RecDemo/docs/reports/data
find /data/Zijian/goal/RecDemo /data/Zijian/goal/RecDemoRuns -type f \( -iname '*gate0*transition*' -o -iname '*utility*transition*' -o -iname '*transition*point*' -o -iname '*utility*score*' \)
sha256sum /data/Zijian/goal/RecDemo/scripts/build_gate0_text_utility_report.py /data/Zijian/goal/RecDemo/docs/reports/data/2026-07-02-gate0/gate0_text_utility_report.json /data/Zijian/goal/RecDemo/docs/reports/data/2026-07-02-gate0/gate0_text_utility_summary.csv /data/Zijian/goal/RecDemo/docs/reports/data/2026-07-02-gate0/gate0_text_utility_coherence_quartiles.csv
```

## 📝 论文安全措辞

> 在单次归档的 Gate-0 抽样观察中，四个观测数据集的 `U_ds` 点估计顺序为 `ML1M > Beauty > ATG > Steam`。由于冻结的逐 transition 记录与用户聚类标识未归档，本轮无法估计不确定性或全序保留概率；exchangeability 假设下的 `1/24` 仅为描述性组合计算，不是确认性 p 值。
