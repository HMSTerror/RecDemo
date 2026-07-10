# CLOSE-10 ATG provenance-limited observed spread report

_Read-only evidence archive collected from `l20` on 2026-07-10._

---

## 📋 Conclusion

The three completed ATG host runs provide a provenance-limited observed spread, not an estimate of population variance. Their run directories lack `frozen_run_manifest.json`, so complete configuration parity is not claimed and no manifest was reconstructed retrospectively.

The maximum pairwise `test-p2 NDCG@10` observed spread is `0.002631944403637204`. The original Gate-1 absolute gap is `0.011410105406507` (ratio `4.335238005308492`), and the E0-corrected absolute gap is `0.011505201353104493` (ratio `4.371369447319985`). Both comparisons are recorded as `outside_observed_spread`.

## 📊 Single-run observations

| seed | best step | validation-p5 NDCG@10 | test-p2 NDCG@10 |
| ---: | ---: | ---: | ---: |
| 100 | 29000 | 0.028213199503339222 | 0.0397181623215186 |
| 101 | 32000 | 0.029021099610334278 | 0.04129374588439805 |
| 102 | 42000 | 0.029207551260010158 | 0.0423501067251558 |

## 🔎 Independent gap comparisons

| Readout | Absolute gap | Gap / observed spread | Decision |
| --- | ---: | ---: | --- |
| Original Gate-1 | 0.011410105406507 | 4.335238005308492 | `outside_observed_spread` |
| E0 corrected | 0.011505201353104493 | 4.371369447319985 | `outside_observed_spread` |

The two gaps are read independently from the original Gate-1 report and the E0 evaluator amendment. This package does not replace the frozen Table 2 metrics.

## 🔗 Provenance boundary

| seed | Summary SHA-256 | Log SHA-256 | Manifest |
| ---: | --- | --- | --- |
| 100 | `db5c3df497ab3ee4cfebcfa67fd32fb48428017422bd26d1bb41b8b7be3a70cc` | `79ce2bde083594e9346095eb743b561653352511ec88047a14375b00d7e74ac5` | absent; not reconstructed |
| 101 | `2c805c2fdf9e6a5f9785b3f3e242a13ee36ac1027b7a632bb46183529d504379` | `e84eb97c3f276a5f9949cc4998908c6e8febd6f217704ea31c033814813aec7a` | absent; not reconstructed |
| 102 | `654d2d989f20b3eb48288fe288323c14395216520c32348074c1f8cae7509d86` | `00941e7539be2d8fcf3b4a776312b2e9e5fb42dbf4a1ca71f65eff9e181fc9b1` | absent; not reconstructed |

## 🧾 Completion-marker excerpts

```text
EARLY_STOP_TRIGGERED step=34000 best_step=29000 best_metric=0.028213
EARLY_STOP_TRIGGERED step=37000 best_step=32000 best_metric=0.029021
EARLY_STOP_TRIGGERED step=47000 best_step=42000 best_metric=0.029208
2026-07-10 13:51:04 close10 ALL_SEEDS_DONE
```

During construction, each `BEST_RESULT` line must also bind the same-seed summary path, best step, and metric. A missing summary, log, hash, seed, or completion marker causes the builder to fail closed.
