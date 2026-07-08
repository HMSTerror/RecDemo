# main\_v2 数值来源审计

_日期：2026-07-09_
_用途：审计 `paper/main_v2.tex` 当前已经填入的关键数值是否都能在本地 artifact 中找到来源；服务 `CLOSE-07` 的“不要把数字凭记忆塞进论文”初审_

---

## 📝 一句话结论

截至 2026-07-09，`paper/main_v2.tex` 主体部分已经填入的关键数值簇都可以在本地 dated artifact 中找到对应来源；当前真正没有权威来源的已经进一步收缩到保留为占位的部分，主要是 `CLOSE-02` 的 noise-floor 归因与其对应 limitations 句。

## 📍 审计范围

本次只审计 **主稿中已填入的关键数值簇**，不审计仍为 `\pending{}` / `\pnum` 的占位项。

覆盖范围：

1. setup 段数据集统计表
2. 训练前 `U_ds / phi(U_ds)` 反转表
3. hinge robustness / per-user readout / corrupted-bank response / ASO frozen validation
4. Gate-1 冻结验证表
5. 第一代 Beauty control 表
6. clean-root v2 control paragraph 中引用的 Sprint-07 数字

## 📊 审计结果总表

| 数值簇 | 主稿位置 | 本地来源 | 结论 |
| --- | --- | --- | --- |
| dataset statistics table | setup 段 `Table~\ref{tab:dataset_stats}` | `docs/reports/data/2026-07-09-paper-dataset-stats-table.csv` | 可对上 |
| `U_ds / phi / Δ` 反转表 | `Table 1` | `docs/reports/data/2026-07-02-gate0/gate0_text_utility_summary.csv` + 第一代对照表工件 | 可对上 |
| per-user 相关系数 | prose | `docs/reports/data/2026-07-04-followup09/per_user_utility_harm_report.md` | 可对上 |
| corrupted-bank `U_ds` 响应 | prose | `docs/reports/data/2026-07-04-followup10/beauty_corrupted_u_ds_phi_report.md` | 可对上 |
| ASO frozen miss | prose | `docs/reports/data/2026-07-02-gate0/aso_validation_report.md` | 可对上 |
| 四数据集 frozen-gate validation | `Table 2` | `docs/reports/data/2026-07-06-gate1/sprint05_gate1_report.json` | 可对上 |
| Beauty token-dropout controls | `Table 3` | `docs/reports/2026-06-28-beauty-token-dropout-control-results.md` | 可对上（四舍五入） |
| clean-root v2 controls paragraph | mechanism 段 prose | `docs/reports/data/2026-07-06-sprint07/sprint07_control_table.csv` | 可对上 |

## 🔢 逐项核对

### 1. setup 段数据集统计表

主稿表格：

- Steam `items/train/val/test = 9265 / 988517 / 81695 / 80651`
- ML1M `3706 / 755782 / 98622 / 85405`
- Beauty `12101 / 17890 / 2236 / 2237`
- ATG `11921 / 15529 / 1941 / 1942`

本地来源：

- `docs/reports/data/2026-07-09-paper-dataset-stats-table.csv`

结论：

- setup 里的数据集统计表现在已经有 dated paper-level artifact 支撑。
- 这张表来自 `docs/reports/data/2026-07-02-gate0/gate0_failure_component_summary.csv` 的派生整理，而不是来自本地 legacy `data_statis.df` 的直接抄写。

### 2. `Table 1`: 跨数据集 `U_ds` 反转表

主稿表格：

- Steam: `0.570 / 1.000 / +0.0064`
- ATG: `0.688 / 0.117 / +0.0019`
- Beauty: `0.712 / 0.000 / -0.0006`
- ML1M: `0.754 / 0.000 / -0.0622`

本地来源：

- `docs/reports/data/2026-07-02-gate0/gate0_text_utility_summary.csv`
  - Steam `u_ds_popularity = 0.56956625`, `phi_u_ds = 1.0`
  - ATG `u_ds_popularity = 0.6882625`, `phi_u_ds = 0.117375`
  - Beauty `u_ds_popularity = 0.7124275`, `phi_u_ds = 0.0`
  - ML1M `u_ds_popularity = 0.75353875`, `phi_u_ds = 0.0`

结论：

- 表中的 `U_ds` 与 `phi(U_ds)` 是对原始 artifact 的合理四舍五入。
- 该表右列 `Δ` 来自第一代主表冻结工件，主稿里已按“提示性而非结论性”使用，未越界。

### 3. per-user readout

主稿 prose：

- ML1M `ρ = 0.028`
- Steam `ρ = 0.046`

本地来源：

- `docs/reports/data/2026-07-04-followup09/per_user_utility_harm_report.md`
  - ML1M `spearman = 0.027679...`
  - Steam `spearman = 0.045552...`

结论：

- 主稿中的 `0.028 / 0.046` 与 artifact 一致，属于保守四舍五入。

### 4. corrupted-bank gate response

主稿 prose：

- clean Beauty `U_ds = 0.7124`
- 轻度 corruption `+0.0008`
- `50%` token dropout 时 `U_ds = 0.7044`

本地来源：

- `docs/reports/data/2026-07-04-followup10/beauty_corrupted_u_ds_phi_report.md`
  - clean `U_ds = 0.7124275`
  - `dropout_rate = 0.3` 时 `u_ds_delta_vs_clean = +0.00083625`
  - `dropout_rate = 0.5` 时 `u_ds_popularity = 0.70442125`

结论：

- 主稿对这几项数字的引用是准确的，并保留了“observational only”限制。

### 5. ASO frozen validation miss

主稿 prose：

- `U_ds = 0.538`
- `phi(U_ds) = 1.0`
- `Δ test p2 NDCG@10 = -0.0108`

本地来源：

- `docs/reports/data/2026-07-02-gate0/aso_validation_report.md`
  - `u_ds = 0.537923`
  - `phi(U_ds) = 1.000000`
  - `delta_test_p2_ndcg10 = -0.010826`

结论：

- 主稿数值与 frozen validation artifact 一致。

### 6. `Table 2`: 四数据集 frozen-gate validation

主稿表格：

- Steam `0.0129 -> 0.0149`, `Δ +0.0020`
- ML1M `0.0910 -> 0.0759`, `Δ -0.0151`
- Beauty `0.0333 -> 0.0294`, `Δ -0.0039`
- ATG `0.0419 -> 0.0305`, `Δ -0.0114`

本地来源：

- `docs/reports/data/2026-07-06-gate1/sprint05_gate1_report.json`

对应字段可直接读到：

- Steam `core_test_p2_ndcg10 = 0.012895...`, `current_test_p2_ndcg10 = 0.014911...`, `delta = 0.002015...`
- ML1M `0.091021... -> 0.075888...`, `delta = -0.015133...`
- Beauty `0.033294... -> 0.029435...`, `delta = -0.003858...`
- ATG `0.041877... -> 0.030467...`, `delta = -0.011410...`

结论：

- 表 2 数值可由 Gate-1 JSON 直接支持，主稿中采用的是标准四舍五入。

### 7. `Table 3`: 第一代 Beauty token-dropout controls

主稿表格：

- user-gated `0.0235 / 0.0393`
- anchor-only `0.0238 / 0.0366`
- `u_shuffle` `0.0212 / 0.0206`
- `global_p` `0.0165 / 0.0289`

本地来源：

- `docs/reports/2026-06-28-beauty-token-dropout-control-results.md`

对应行：

- `global_p`: `0.016463 / 0.028903`
- `u_shuffle`: `0.021213 / 0.020643`
- `text_anchor_only`: `0.023791 / 0.036564`
- `full_u`: `0.023547 / 0.039324`

结论：

- 主稿表 3 是保守四舍五入版本。
- 主稿把 `text_anchor_only` 改称 `anchor-only` 属于命名压缩，不构成数值漂移。

### 8. clean-root v2 controls paragraph

主稿 prose：

- Beauty `global_p` 与 full 都是 `0.0294`
- Beauty `u_shuffle = 0.0330`
- Steam `u_shuffle` 相对 full 下降 `0.0011`
- Steam `global_p` 相对 core `+0.00035`
- Steam `text_anchor_only = 0.0302`

本地来源：

- `docs/reports/data/2026-07-06-sprint07/sprint07_control_table.csv`

可直接对上：

- Beauty full/global\_p `test_p2_ndcg10 = 0.029435971334722`
- Beauty `u_shuffle = 0.033003889269924`
- Steam `delta_test_p2_vs_full = -0.001076748300944`
- Steam `delta_test_p2_vs_core = +0.000347955396865`
- Steam `text_anchor_only = 0.030180637020685`

结论：

- 主稿 mechanism 段对 Sprint-07 的引用与本地 CSV 一致。

## ⚠ 当前尚未通过本审计覆盖的部分

以下内容不是“来源不明”，而是本次审计不负责：

- `\pending{}` / `\pnum` 仍未回填部分
- Figure 1 / Figure 2 / Backoff mechanism 图
- appendix 中待从冻结稿合并的整段文本
- 任何依赖新的 `CLOSE-02` dated artifact 才能升级的噪声地板结论
- 任何依赖 `CLOSE-02` dated artifact 才能升级的噪声地板结论

## ✅ 对 `CLOSE-07` 的意义

这份审计支持下面这句更精确的判断：

> 截至 2026-07-09，`main_v2.tex` 当前已经填入的主要数值簇—including setup 段的数据集统计表—都能在本地 artifact 中找到来源；剩余风险集中在仍然保留为占位的 `CLOSE-02` 两处红灯归因，而不是已填数字的 provenance。

这意味着 `CLOSE-07` 的 review-initial 可以从“担心现有数字是凭记忆写的”转向“继续等待缺失 artifact，并按占位清单回填”。
