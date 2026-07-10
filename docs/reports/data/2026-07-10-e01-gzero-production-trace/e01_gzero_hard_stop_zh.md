# E01 生产路径 g-zero 轨迹——HARD STOP

## 判定

`AAAI-E01` 已触发预注册的 **HARD STOP**。Beauty 的生产路径在 `g=0` 下不具备确定性等价：最早的已跟踪差异出现在 step 0，具体为 canonical core proposal 参数的 optimizer membership 不同。因此，`downstream_launch_authorized=false`，本轮不得启动 E2、E3、E4、E5 和 E8。

这是 `random_seed=100` 的单次生产路径轨迹，不是训练 seed 方差研究；不得据此使用“显著”“稳定”“统计等价”或“噪声范围内”等措辞。

## 范围与协议

- 数据集：仅 Beauty。它是冻结工件中唯一同时具备 `AdaptiveWise host`、`final-v2 closed-gate full` 与 `global_p` 的匹配生产三元组；ML1M 的 host 使用 hybrid graph，不在本等价性结论范围内。
- 路径：`host`、`final_v2_closed_gate_full`、`global_p`。
- 跟踪步：0、1、100、1000。
- 预先冻结的 FP32 容差：`1e-6`。
- 训练前 canonical 初始化参数值一致：`canonical_parameter_sha256=9f34d3c821bc073668cbf8784a3e5ffa619415c715a2798867cbf5738ef85320`。
- E0 前置条件、Beauty 资产哈希、标准化配置合同和各 checkpoint 的 batch order 检查均通过。

## 最早差异与根因

最早失败项为：

```json
{
  "step": 0,
  "category": "optimizer",
  "key": "core_proposal_logits.in_optimizer",
  "reference_arm": "host",
  "arm": "final_v2_closed_gate_full",
  "max_abs_diff": 1.0,
  "status": "fail"
}
```

虽然复制后的初始参数值一致，但生产参数归属不同：

| 路径 | core proposal 参数归属 | optimizer 后果 |
|---|---|---|
| `host` | `graph.p1` | canonical proposal 参数不归 model optimizer 管理 |
| `final_v2_closed_gate_full` | `model.text_side_builder.p1` | canonical proposal 参数归 model optimizer 管理 |
| `global_p` | `model.text_side_builder.p1` | canonical proposal 参数归 model optimizer 管理 |

本轮没有在观察结果后修改 optimizer ownership。若为追求“等价”而修改它，将改变生产路径，不能作为预注册归约的有效证明。

## 差异演进

| Step | 失败项计数 | 代表性最大绝对差 |
|---:|---|---|
| 0 | optimizer 18；RNG 6 | optimizer membership `1.0` |
| 1 | gradient 46；loss term 16；optimizer 72；RNG 6 | core proposal gradient `0.1586687267` |
| 100 | gradient 46；loss term 16；optimizer 74；parameter 46；RNG 6；sampling 2 | core proposal parameter `0.0001971722`；p5 logits `3.4511e-05` |
| 1000 | gradient 46；loss term 16；optimizer 74；parameter 48；RNG 6；sampling 10 | core proposal gradient `3.1849598885`；core proposal parameter `0.0113682747`；p5 logits `0.9984807372` |

证据链表明：step 0 已存在生产拓扑差异，随后梯度、loss、参数与采样轨迹发生分离。不得把该结果解释为 seed noise。

## 启动与论文后果

- E2 / E3 / E4 / E5 / E8：均不获启动授权。
- 本轮 48 小时冲刺不允许 rescue tuning、第二个 seed 或 optimizer ownership 修补。
- 论文不得声称已经演示端到端精确归约。
- bounded downside 仅限 proposal / 单步 transition-row 的 kernel-level TV bound；不覆盖训练 loss、排序指标、完整轨迹或端到端性能。

## 溯源与审计限制

- 远端运行根：`/data/Zijian/goal/RecDemoRuns/aaai27_e01_gzero_trace_20260710_50e8e7b`
- 源轨迹 SHA-256：`1ca4972357afb860f7e4b99b60711f28dc41ccd7e3192ae7aeff6351dc3cb70c`
- 轨迹生成时间：`2026-07-10T18:08:17+08:00`
- 相邻 execution log 已按原样归档，但其长度为 0 字节，不能作为正向执行证据；可审计证据来自结构化轨迹、pass marker 缺失、源文件哈希与远端文件系统时间戳。
- 远端运行目录中不存在 `E01_PASS.json`，符合 fail-closed 设计。

从 execution log 创建时间（`18:06:30 +08:00`）到轨迹生成时间（`18:08:17 +08:00`）的文件系统时间差约为 1 分 47 秒。该值是基于时间戳的耗时估计，不是日志内计时器。
