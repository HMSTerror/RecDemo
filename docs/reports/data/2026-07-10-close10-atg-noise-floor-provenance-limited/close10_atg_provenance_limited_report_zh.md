# CLOSE-10 ATG provenance-limited observed spread 报告

_只读证据归档；采集主机 `l20`，日期 2026-07-10。_

---

## 📋 结论

三次已完成的 ATG host 运行仅给出 provenance-limited observed spread，不是总体方差估计。三个运行目录均缺少 `frozen_run_manifest.json`，因此不声称完整配置一致性，也未事后重建任何 manifest。

最大成对 `test-p2 NDCG@10` observed spread 为 `0.002631944403637204`。原始 Gate-1 绝对 gap `0.011410105406507`（比值 `4.335238005308492`）与 E0 修正后绝对 gap `0.011505201353104493`（比值 `4.371369447319985`）均判为 `outside_observed_spread`。

## 📊 单次运行观测

| seed | best step | validation-p5 NDCG@10 | test-p2 NDCG@10 |
| ---: | ---: | ---: | ---: |
| 100 | 29000 | 0.028213199503339222 | 0.0397181623215186 |
| 101 | 32000 | 0.029021099610334278 | 0.04129374588439805 |
| 102 | 42000 | 0.029207551260010158 | 0.0423501067251558 |

## 🔎 独立 gap 对照

| 读数版本 | 绝对 gap | gap / observed spread | 判定 |
| --- | ---: | ---: | --- |
| 原始 Gate-1 | 0.011410105406507 | 4.335238005308492 | `outside_observed_spread` |
| E0 corrected | 0.011505201353104493 | 4.371369447319985 | `outside_observed_spread` |

两套 gap 分别从原始 Gate-1 报告与 E0 evaluator 修正案读取，未相互替代，也未改写冻结的 Table 2 数字。

## 🔗 Provenance 边界

| seed | summary SHA-256 | log SHA-256 | manifest |
| ---: | --- | --- | --- |
| 100 | `db5c3df497ab3ee4cfebcfa67fd32fb48428017422bd26d1bb41b8b7be3a70cc` | `79ce2bde083594e9346095eb743b561653352511ec88047a14375b00d7e74ac5` | 缺失；未重建 |
| 101 | `2c805c2fdf9e6a5f9785b3f3e242a13ee36ac1027b7a632bb46183529d504379` | `e84eb97c3f276a5f9949cc4998908c6e8febd6f217704ea31c033814813aec7a` | 缺失；未重建 |
| 102 | `654d2d989f20b3eb48288fe288323c14395216520c32348074c1f8cae7509d86` | `00941e7539be2d8fcf3b4a776312b2e9e5fb42dbf4a1ca71f65eff9e181fc9b1` | 缺失；未重建 |

## 🧾 完成标记原文

```text
EARLY_STOP_TRIGGERED step=34000 best_step=29000 best_metric=0.028213
EARLY_STOP_TRIGGERED step=37000 best_step=32000 best_metric=0.029021
EARLY_STOP_TRIGGERED step=47000 best_step=42000 best_metric=0.029208
2026-07-10 13:51:04 close10 ALL_SEEDS_DONE
```

每条 `BEST_RESULT` 还必须在构建时绑定同 seed 的 summary 路径、best step 与 metric；任一摘要、日志、哈希、seed 或完成标记缺失都会使构建失败。
