# Gate0 全局校准修复审计（中文）

## 1. 这份审计要回答什么

`FOLLOWUP-01` 已经把 Gate0 失败的主驱动收束到了 `null_curve_spread_or_scaling_mismatch`，也就是：

- `ML1M` 的原始 residual 并不算离谱；
- 更像是 `sigma_null` 太紧，或者当前全局缩放太激进；
- 因而下一个最自然的问题不是“要不要立刻重开主表训练”，而是：

1. 只改全局校准旋钮，能不能把 `ML1M` 拉回 Gate0 阈值内？
2. 在把 `ML1M` 拉回来的同时，还能不能保住 `Steam / Beauty > ML1M` 这两个排序门？
3. 如果连这种最保守、最接近原设计的修复都做不到，那是不是应该停止把 `SPRINT-05` 当成默认下一步？

这份审计就是专门回答这三个问题的。

## 2. 这次没有改模型主体，只审计三类“全局修复”

这次不是重新训练，也不是改 `v2 kernel` 的结构。审计只在现有生产 bank 路径上，离线重算三类全局修复候选：

- `agreement_k`
- `sigma_scale`
- `sigma_floor`

也就是说，本次检查的是：

> 如果问题只是“标准化太紧”或“全局缩放不合适”，那么只靠这几个全局旋钮，能不能把 Gate0 救回来？

这很关键，因为它仍然属于最接近原始设计主路径的修复方式：

- 仍是 `history-only`
- 仍是同一个 `u_tilde = residual / (k * sigma)` 结构
- 仍是同一套 production sentence-t5-xl bank
- 没有偷偷改 `proposal` 形式，也没有换训练目标

## 3. 实际运行环境

这次正式审计依然是跑在服务器 `l20` 上，不是在本地伪复盘。

- 服务器：`l20`
- 远端仓库：`/data/Zijian/goal/RecDemo`
- 正式数据目录：`/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/{ML1M,Steam,Beauty,ATG}`
- 文本 bank：各数据集当前 production `sentence-t5-xl` bank
- 正式归档目录：`/data/Zijian/goal/RecDemo/docs/reports/data/2026-07-02-gate0`

我在本轮继续核查时，远端目录仍能看到以下正式产物：

- `gate0_calibration_repair_audit.md`
- `gate0_calibration_repair_audit.json`
- `gate0_calibration_repair_candidates.csv`

对应时间戳为 `2026-07-03 02:03 +0800`，说明这批产物确实留在服务器正式目录里。

## 4. 为什么这轮先从 `/tmp` 起跑

这轮有一个很实际的服务器侧插曲：当时 `/data` 盘一度满了，直接导致两件事：

1. 正常的远端代码同步不稳定；
2. 远端 `/data` 下的 `build_gate0_utilde_report.py` 曾变成了 `0` 字节坏文件。

所以这轮 FOLLOWUP-02 不是一开始就直接在正式仓库目录里开跑，而是先走了一个保守恢复路径：

1. 在远端临时目录下建立最小工作区；
2. 只拷入本次审计真正需要的少量脚本；
3. 从 `/tmp` 运行审计脚本，但读取的仍是 `/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/...` 下的正式数据与 Gate0 工件；
4. 用户清理完 `data` 盘以后，再把完整代码重新同步回 `/data/Zijian/goal/RecDemo`；
5. 最后把产物归档回正式目录，并拉回本地项目目录保存。

所以这里要区分两件事：

- **运行数据和证据边界** 没变，始终是正式生产 bank 路径；
- **脚本最初的执行落点** 为了避开满盘损坏，先临时放在了 `/tmp`；

这不算换实验口径，而是一次服务器侧恢复动作。

## 5. 审计到底扫了什么

这轮总共审计了 `96` 个全局候选：

- `agreement_k`: `2.0, 2.5, 3.0, 4.0`
- `sigma_scale`: `1.0, 1.25, 1.5, 2.0`
- `sigma_floor`: `0.0, 0.0045, 0.0050, 0.0055, 0.0060, 0.0070`

形式上就是穷举三类旋钮的组合，然后在现有 Gate0 同一条生产 bank 路径上重新计算：

- `ML1M median_u_tilde`
- `Steam median_u_tilde`
- `Beauty median_u_tilde`
- Gate0 三个 margin 是否同时转正

Gate0 仍按同一判据评估：

1. `abs(median_u_tilde(ML1M)) < 0.5`
2. `median_u_tilde(Steam) > median_u_tilde(ML1M)`
3. `median_u_tilde(Beauty) > median_u_tilde(ML1M)`

## 6. 结果很硬：96 个候选，0 个通过

这轮最重要的结果非常直接：

- `candidate_count = 96`
- `passing_candidate_count = 0`

也就是说，**没有任何一个全局 `k / sigma_scale / sigma_floor` 修复候选，能同时满足 Gate0 的三个条件。**

正式结论是：

> No audited global k/sigma_scale/sigma_floor repair candidate directionally passes Gate0 on the current production-bank path, so SPRINT-05 must remain blocked.

## 7. 最好的候选也没救回来

这轮最好的候选是：

- `candidate_id = k4_scale2_floor0`
- `agreement_k = 4.0`
- `sigma_scale = 2.0`
- `sigma_floor = 0.0`

它的效果是：

- `ML1M median_u_tilde = 0.356886`
- `Steam median_u_tilde = 0.026823`
- `Beauty median_u_tilde = 0.199542`

这说明了一个非常关键的结构性事实：

- 它确实把 `ML1M` 从 `1.427543` 拉回到了 `0.5` 阈值以内；
- 但它**没有**把 `Steam` 和 `Beauty` 的排序门救回来；
- 结果仍然是 `Steam < ML1M`、`Beauty < ML1M`。

换句话说：

> 最优的全局修复候选只能修到“ML1M 不那么离谱”，但修不到“ML1M 重新成为最低、证据贫数据集自动回退”的原始 Gate0 结构。

## 8. 这说明原来的“先做 calibration repair”需要再收紧

`FOLLOWUP-01` 给出的建议是：

- `recommended_next_path = calibration_repair_first`

而这次 `FOLLOWUP-02` 进一步把这句话收紧成了：

- `recommended_next_path = downgrade_claim_or_design_deeper_repair`

两者并不矛盾，关系是这样的：

1. 前一轮追因告诉我们，问题更像校准，不像 raw agreement 本体崩掉；
2. 这一轮再往前推一步，告诉我们：**简单的全局校准修复不够**；
3. 因此“修 calibration”这件事如果还要继续，下一步就不能再是简单全局缩放，而必须是更深层的 repair。

所以这轮真正新增加的不是“又一次 fail”，而是把修复路径切得更细了：

- 可行的简单全局修复路径：目前没有证据支持；
- 若还想继续修：必须进入更深层、非简单全局旋钮的 repair 设计；
- 若时间和风险不允许：就该走 claim downgrade。

## 9. 这和你的原始 idea 是否一致

如果把你的原始 idea 摘成一句话，它大致是：

> 文本证据贫的 regime 应该在零点校准后自动贴近核心核，文本证据富的 regime 则保留更强的正向锚点，因此 `ML1M` 应靠近 null，而 `Steam / Beauty` 应高于 `ML1M`。

这次结果对这个 idea 的回答是：

- **方向上没有支持。**
- 当前 production-bank 路径下，真实观察到的是：
  - baseline：`ML1M = 1.427543`，`Steam = 0.107291`，`Beauty = 0.798168`
  - best global repair：`ML1M = 0.356886`，`Steam = 0.026823`，`Beauty = 0.199542`

也就是说：

1. `ML1M` 的确可以被拉低一些；
2. 但“ML1M 成为最低、Steam/Beauty 在它之上”这个更核心的排序预期没有恢复；
3. 所以当前证据**不支持**“只要做简单全局校准，就能回到原始主张”。

## 10. 这算不算偏离原实验设计

如果只问“这次 FOLLOWUP-02 审计本身是不是偏离”，答案是：

- **不算。**

原因是它仍然严格受限在原设计主路径最关心的边界里：

- 没有绕开 Gate0
- 没有偷开 `SPRINT-05`
- 没有改模型主体再来重写结论
- 没有换数据、换 bank、换评价门
- 只是把“全局校准修复是否足够”这件事做成了一个明确可证伪的审计

真正发生变化的，是**我们对主路径可恢复性的判断**：

- 之前还能说“先试 calibration repair”
- 现在必须说“简单 global repair 不够，要么 deeper repair，要么降主张”

## 11. 对后续主路径的直接影响

这轮结论会直接改变后续顺序：

1. `SPRINT-05` 继续阻塞；
2. 不能因为 `ML1M` 阈值被某个候选局部拉回，就误以为可以直接重开主表；
3. 下一步如果继续做技术修复，必须是**更深层的 calibration repair design**；
4. 下一步如果优先考虑论文路径，就应该开始**冻结更弱、更诚实的 claim 边界**。

所以从工程和论文两个角度看，这轮 FOLLOWUP-02 的意义都很明确：

- 它不是在“补更多数字”；
- 它是在**正式关掉一条原本看起来最可能成功的简单修复路径**。

## 12. 当前最稳妥的结论

一句话总结这轮审计：

> Gate0 失败后，简单的全局 `k / sigma_scale / sigma_floor` 修复并不能把生产路径拉回原始预期；因此当前不能直接重开 `SPRINT-05`，更合理的下一步是“降主张或设计更深层修复”，而不是继续把简单 calibration repair 当成默认答案。
