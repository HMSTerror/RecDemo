# Gate0 文本效用诊断（中文）

日期：2026-07-03

## 1. 这一步为什么改成做 `U_ds`

按最新冲刺文档 §7 的修订，Gate0 失败后，主问题不再被视为一个

- `sigma_null` / `k` / `floor`

这类 spread-scaling 修补问题，而是一个

- `gate` 在跨数据集上到底测到了什么

的构念问题。

因此 `FOLLOWUP-05` 不再继续做 Family A 的局部 spread repair，而是先冻结

- 生产 bank 上的 train-only 文本效用统计量 `U_ds`

作为 Gate0-v2 的输入证据。

这里的 `U_ds` 定义与文档 §7.3 一致：

1. 只读 `paper_raw_v1` 的 `train_data.df`
2. 每个数据集采样 `4000` 条转移
3. seed 固定为 `7`
4. 每条转移用生产 `t5-xl` bank 中有效历史物品 embedding 的归一化均值构造 history 向量
5. 主统计量：
   `U_ds = P(sim(h, next) > sim(h, neg_pop))`
6. 每条转移采样 `100` 个负例，负例按 train split 的 next-item 频率采样
7. 额外输出：
   uniform negatives 与 coherence quartile breakdown

这一步**只负责冻结输入，不负责下 Gate0-v2 的 pass/fail 判定**；正式判定归 `FOLLOWUP-07`。

## 2. 本次实际是在服务器 `l20` 上完成的

执行位置：

- 服务器：`l20`
- 仓库：`/data/Zijian/goal/RecDemo`
- 产物目录：
  `/data/Zijian/goal/RecDemo/docs/reports/data/2026-07-02-gate0`

本次先同步了新脚本：

- `scripts/build_gate0_text_utility_report.py`
- `scripts/launch_gate0_text_utility_tmux.py`

另外修了一个这轮服务器侧真实问题：

- 远端 `torch` 导入时，因为 `/tmp` / `/var/tmp` / `/home/zijian` 都不可用，直接报
  `FileNotFoundError: No usable temporary directory found`

所以本轮 launcher 额外固定了：

- `TMPDIR=/data/Zijian/goal/RecDemo/.tmp`

并在 tmux 启动前先 `mkdir -p /data/Zijian/goal/RecDemo/.tmp`。

这不是实验设计变更，只是把远端 Python / torch 运行环境补到可执行状态。

## 3. 服务器侧产物

本轮在 `l20` 上落下了四个正式产物：

- `gate0_text_utility_summary.csv`
- `gate0_text_utility_coherence_quartiles.csv`
- `gate0_text_utility_report.json`
- `gate0_text_utility_report.md`

对应的本地回填文件也已经同步到：

- `docs/reports/data/2026-07-02-gate0/`

## 4. 核心结果

### 4.1 主表

| 数据集 | `U_ds(popularity)` | `U_ds(uniform)` | `phi(U_ds)` |
| --- | ---: | ---: | ---: |
| ML1M | 0.753539 | 0.798526 | 0.000000 |
| Steam | 0.569566 | 0.565079 | 1.000000 |
| Beauty | 0.712428 | 0.717204 | 0.000000 |
| ATG | 0.688262 | 0.692013 | 0.117375 |

### 4.2 冻结输入读法

按 `gate0_text_utility_report.json` 中的 frozen inputs：

- `U_ds` 降序排序：
  `ML1M > Beauty > ATG > Steam`
- `ML1M` 的 `U_ds` 排名是 `1`
- `ML1M` 的 `phi(U_ds) = 0.0`
- 非 `ML1M` 中，满足 `phi(U_ds) >= 0.5` 的数据集数是 `1`

也就是说，这轮输入证据非常明确地支持了两件事：

1. `ML1M` 的文本效用确实最高，门应该基本关闭；
2. `Steam` 的文本效用确实低，门应该打开。

但它同时也给出一个新的压力点：

3. `Beauty` 与 `ATG` 没有一起落到“门应明显打开”的区间里；
4. 其中 `Beauty` 的 `U_ds = 0.712428`，直接落在关闭侧，而不是 legacy 预检里更接近随机的那一边。

所以这轮证据并不是“全面确认 legacy 预检”，而是：

- **确认了 ML1M / Steam 这条主排序**
- **没有确认“至少两个非 ML1M 数据集应明显开门”这一部分**

## 5. 这一步能下什么结论，不能下什么结论

### 5.1 这一步已经能确定的

`FOLLOWUP-05` 已经完成了它自己的职责：

1. `U_ds` 的生产 bank 数字已经冻结；
2. bank hash 与 split hash 已归档；
3. 后续 `FOLLOWUP-06` 可以直接把这份 artifact 当作 gate 常数输入；
4. `FOLLOWUP-07` 已经有足够输入去做 Gate0-v2 的正式判定。

### 5.2 这一步还不能正式宣告的

这一步**不应自己宣布**：

- Gate0-v2 pass
- Gate0-v2 fail
- `SPRINT-05` reopen
- Family D downgrade 已定

这些都属于 `FOLLOWUP-07` 的职责。

不过，单看输入形状，当前信号已经表明：

- 新的 utility-gated 路线比旧的 spread repair 更贴近构念解释；
- 但它未必能完整满足文档 §7.4 想要的“至少两个非 ML1M 数据集应明显开门”条件。

## 6. 对后续主线的直接影响

这轮结果把后续主线压缩成两步：

1. `FOLLOWUP-06`
   把 `g = g_max * phi(U_ds) * clamp(u_tilde, 0, 1)` 真正写进代码与文稿；
2. `FOLLOWUP-07`
   按冻结标准正式判断：
   - 是否允许重开 `SPRINT-05`
   - 或者是否应进入 Family D 降主张

也就是说，`FOLLOWUP-05` 的价值不是“已经修好 Gate0”，而是：

- 把争论从“还要不要继续调 `sigma`”彻底转成了
- “utility-gated 的冻结判据到底过不过”

这正是最新 spec 想要的主路径。
