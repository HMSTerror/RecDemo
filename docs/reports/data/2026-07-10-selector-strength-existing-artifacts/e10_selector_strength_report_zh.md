# AAAI-E10 既有工件 selector-strength 审计

_采集时间：`2026-07-10T19:15:43+08:00`；来源主机：`l20`_

---

## 📋 口径与边界

- 本报告只枚举已经冻结的 host、full 与 SPRINT-07 control best checkpoint、best summary 和 manifest。
- 本次未启动训练，未启动 evaluation-selection run，未重选 checkpoint，也未按 test 数值筛选。
- `analyze_selector_sweep.py` 未执行：该脚本会按替代 validation selector 另选 step，并生成 best-test checkpoint 汇总，不符合 E10 的冻结 checkpoint 边界。
- 每行的 `p2/p5/p10` 都是同一个 validation-selected checkpoint 上记录的 test readout；冻结的 primary selector 不变。
- 数字来自旧 evaluator 生成的 archived best summary，不能当作 E0 修正后的 Table 2 数字。
- 下列顺序翻转仅作 strength sensitivity；它们不授权改变 selector、补跑或追加 seed。

## 📊 固定 checkpoint 强度读数

### Steam

| Arm | Validation selector | Best step | p2 HR / NDCG | p5 HR / NDCG | p10 HR / NDCG |
| --- | --- | ---: | ---: | ---: | ---: |
| host | `validation_p2_ndcg10` | 27000 | 0.029749503968254 / 0.0128958071557127 | 0.0302579365079365 / 0.0134969766449635 | 0.0307043650793651 / 0.0143765941649742 |
| full | `validation_p5_ndcg10` | 66000 | 0.034858630952381 / 0.0149110094568307 | 0.0343625992063492 / 0.0151400319447493 | 0.0340649801587302 / 0.0161657048436365 |
| u_shuffle | `validation_p5_ndcg10` | 50000 | 0.031969246031746 / 0.0138342611558862 | 0.031547619047619 / 0.0139561102623898 | 0.0311631944444444 / 0.0151413791907229 |
| text_anchor_only | `validation_p5_ndcg10` | 143000 | 0.06875 / 0.0301806370206853 | 0.0693080357142857 / 0.0320281214126964 | 0.0692584325396825 / 0.0355421845607946 |
| global_p | `validation_p5_ndcg10` | 40000 | 0.0306175595238095 / 0.0132437625525773 | 0.0314856150793651 / 0.013868768330687 | 0.0315600198412698 / 0.0151337721007417 |

### ML1M

| Arm | Validation selector | Best step | p2 HR / NDCG | p5 HR / NDCG | p10 HR / NDCG |
| --- | --- | ---: | ---: | ---: | ---: |
| host | `validation_p2_ndcg10` | 302000 | 0.165341122372372 / 0.0910217532578437 | 0.182526276276276 / 0.0999238750167939 | 0.186502909159159 / 0.102170742343752 |
| full | `validation_p5_ndcg10` | 405000 | 0.168883727477477 / 0.0758887081871195 | 0.180062875375375 / 0.088931624328109 | 0.178643487237237 / 0.0955967131461645 |

### Beauty

| Arm | Validation selector | Best step | p2 HR / NDCG | p5 HR / NDCG | p10 HR / NDCG |
| --- | --- | ---: | ---: | ---: | ---: |
| host | `validation_p2_ndcg10` | 20000 | 0.05224609375 / 0.0332948578036781 | 0.05126953125 / 0.0415990987190079 | 0.04931640625 / 0.0405393268224851 |
| full | `validation_p5_ndcg10` | 18000 | 0.052734375 / 0.0294359713347218 | 0.05029296875 / 0.0420298090977324 | 0.04736328125 / 0.0402986774632389 |
| u_shuffle | `validation_p5_ndcg10` | 20000 | 0.052734375 / 0.0330038892699236 | 0.05126953125 / 0.0421279328600941 | 0.04736328125 / 0.0403166632355644 |
| text_anchor_only | `validation_p5_ndcg10` | 23000 | 0.05224609375 / 0.0289886543061033 | 0.0498046875 / 0.040315700530138 | 0.0458984375 / 0.0389984919371437 |
| global_p | `validation_p5_ndcg10` | 18000 | 0.052734375 / 0.0294359713347218 | 0.05029296875 / 0.0420298090977324 | 0.04736328125 / 0.0402986774632389 |

### ATG

| Arm | Validation selector | Best step | p2 HR / NDCG | p5 HR / NDCG | p10 HR / NDCG |
| --- | --- | ---: | ---: | ---: | ---: |
| host | `validation_p2_ndcg10` | 39000 | 0.0485491071428571 / 0.0418775070198879 | 0.0491071428571429 / 0.0429923880630843 | 0.0502232142857143 / 0.0436486585405242 |
| full | `validation_p5_ndcg10` | 30000 | 0.046875 / 0.0304674016133804 | 0.0474330357142857 / 0.0406145939457253 | 0.0479910714285714 / 0.0412048820613679 |

## 🔍 Strength sensitivity

严格 pairwise 顺序翻转共 `8` 项。这里的“翻转”仅表示同一对既选 checkpoint 的差值在 p2/p5/p10 间出现严格正负号变化。

| Dataset | Metric | Comparison | p2 Δ | p5 Δ | p10 Δ |
| --- | --- | --- | ---: | ---: | ---: |
| Steam | HR@10 | u_shuffle − global_p | 0.0013516865079365 | 6.20039682538986e-05 | -0.000396825396825399 |
| ML1M | HR@10 | host − full | -0.00354260510510501 | 0.002463400900901 | 0.00785942192192202 |
| Beauty | HR@10 | host − full | -0.00048828125 | 0.0009765625 | 0.001953125 |
| Beauty | NDCG@10 | host − full | 0.0038588864689563 | -0.000430710378724497 | 0.000240649359246205 |
| Beauty | HR@10 | host − u_shuffle | -0.00048828125 | 0 | 0.001953125 |
| Beauty | NDCG@10 | host − u_shuffle | 0.000290968533754501 | -0.000528834141086197 | 0.000222663586920704 |
| Beauty | HR@10 | host − global_p | -0.00048828125 | 0.0009765625 | 0.001953125 |
| Beauty | NDCG@10 | host − global_p | 0.0038588864689563 | -0.000430710378724497 | 0.000240649359246205 |

## 📦 Provenance 与缺失字段

完整 checkpoint/summary/manifest 路径、SHA-256、git revision、split/bank hash 与 selector 证据见同目录 CSV 和 JSON。

既有工件缺失的 strength readout 已写为 `NA`：

- `Steam/host:manifest/path`
- `Steam/host:manifest/sha256`
- `Steam/host:manifest/provenance/git_head`
- `Steam/host:manifest/provenance/repo_root`
- `Steam/host:manifest/random_seed`
- `Steam/host:manifest/split_hash`
- `Steam/host:manifest/bank_hash`
- `ML1M/host:manifest/path`
- `ML1M/host:manifest/sha256`
- `ML1M/host:manifest/provenance/git_head`
- `ML1M/host:manifest/provenance/repo_root`
- `ML1M/host:manifest/random_seed`
- `ML1M/host:manifest/split_hash`
- `ML1M/host:manifest/bank_hash`
- `Beauty/host:manifest/path`
- `Beauty/host:manifest/sha256`
- `Beauty/host:manifest/provenance/git_head`
- `Beauty/host:manifest/provenance/repo_root`
- `Beauty/host:manifest/random_seed`
- `Beauty/host:manifest/split_hash`
- `Beauty/host:manifest/bank_hash`
- `ATG/host:manifest/path`
- `ATG/host:manifest/sha256`
- `ATG/host:manifest/provenance/git_head`
- `ATG/host:manifest/provenance/repo_root`
- `ATG/host:manifest/random_seed`
- `ATG/host:manifest/split_hash`
- `ATG/host:manifest/bank_hash`
