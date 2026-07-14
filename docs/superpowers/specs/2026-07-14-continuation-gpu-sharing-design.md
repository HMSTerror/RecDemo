# Continuation GPU 共享调度修正案

## 状态与授权

本修正案只作用于 r7 完成并由冻结的 RISK-08 出口授权后的 continuation 队列。用户于 2026-07-14 明确授权：后续任务采用与当前共卡运行相同的策略，在显存允许时一张 GPU 最多同时容纳两个训练进程。r7 manifest、RISK-08 判据、seed、训练参数、任务依赖和既有 artifacts 均不修改。

## 方案比较

1. 保持一进程一卡：最保守，但在每个任务只使用约 1.5 GiB、L20 有 46 GiB 显存时浪费资源。
2. 仅按显存无限并发：吞吐可能最高，但忽略算力竞争、CUDA 瞬时峰值和未知任务，可能 OOM 或使结果耗时不可解释。
3. 固定进程上限并叠加显存门：每卡最多两个 GPU 计算进程，启动前要求至少 8192 MiB 空闲显存；外部进程与本控制器进程一并计数。该方案可利用显存，同时保留明确、可测试的硬边界，因此采用本方案。

## 调度合同

- `QueueRuntime` 的默认值仍为每卡最多一个计算进程，避免改变旧队列行为。
- continuation CLI 显式设置 `max_processes_per_gpu=2` 与 `min_free_memory_mib=8192`。
- `nvidia-smi` 中的外部计算进程计入两进程上限；本控制器已启动但尚未完成 CUDA 初始化的任务也作为预留插槽计入。
- 本地监督进程与其后代 GPU PID 视为同一个任务，避免父 wrapper 与训练子进程被重复计数。
- GPU PID、进程树或显存探针失败时 fail-closed，不启动新任务。
- `kind` 为 `efficiency`、`profile` 或 `efficiency_gpu` 的任务必须独占 GPU；当前冻结 continuation manifest 不包含此类任务。
- 调度器每轮最多提供 `GPU 数 × 每卡插槽数` 个 GPU 候选；最终分配仍由运行时按实时进程与显存状态裁决。
- 每个共享插槽使用独立锁；默认单插槽运行仍沿用旧锁名，保持兼容。
- 40 GiB 磁盘 hard stop、维护窗口、GPU-hour 预算、RISK-08 授权、attempt-once、空日志失败和 artifact 校验全部保持原样。

## 安全切换

本地红—绿测试和全回归通过后，创建新的不可变 source bundle。先验证旧 continuation 尚未启动任何科学任务，再停止旧 continuation controller 并启动新 controller；不停止 r7，不停止 root ACTRec，不改 continuation manifest。切换前后记录 PID、tmux、source revision、source manifest SHA、queue manifest SHA 和 r7 manifest SHA。

## 验收标准

1. 一张卡已有一个外部计算进程且空闲显存足够时，可启动一个 continuation 任务。
2. 一张卡已有两个计算任务时，第三个任务不得启动。
3. 空闲显存低于 8192 MiB 或探针失败时不得启动。
4. 两张卡独立分配；一张卡满时可使用另一张卡。
5. 独占任务在任一现有计算进程存在时不得启动，且独占任务运行时不得同卡启动其他任务。
6. 原有单进程默认、磁盘门、维护门、RISK-08 门与冻结 manifest 哈希不变。

