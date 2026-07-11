# E1/R12 版本绑定后的 RISK-04～08 seed-100 实验手册

_PreferGrow AAAI-27；日期：2026-07-11（Asia/Shanghai）；本手册定义修复后新 dated attempt 的可审计资产、checkpoint 与队列边界。_

---

## 🧭 当前状态与授权边界

E1 在 R12 dated attempt 的指定 revision `0338cc2…` 上通过：`random_seed=100`，trace steps 为 `0,1,100,1000`，FP32 tolerance 为 `1e-6`，`comparisons=2986`，`failed_comparisons=0`，`first_divergence=null`。证据位于 [R12 trace report](../reports/data/2026-07-11-e01-gzero-production-trace-r12/e01_gzero_trace.json)、[RISK-02 pass marker](../reports/data/2026-07-11-e01-gzero-production-trace-r12/RISK-02_PASS.json) 和 [R12 attempt manifest](../reports/data/2026-07-11-e01-gzero-production-trace-r12/attempt_manifest.md)。R12 只证明该 revision、Beauty、指定三臂在内存训练路径上的 trace contract；不证明任意后续 revision、standalone checkpoint replay、推荐指标等价或 RISK-08。

r3 队列已 fail closed，详见 [r3 audit](../reports/data/2026-07-11-risk0607-r3-fail-closed-audit/risk0607_r3_fail_closed_audit.md)。r3 从 pre-repair `e63193f…` dirty source 运行，出现错误 bank path、full/anchor `work_dir` 碰撞及 full 缺少 `phi_R`；它的 2 个 host summary 不进入修复后证据链。当前修复还把 graph-owned host `p1` 纳入显式 checkpoint state 和 common evaluator EMA 恢复，范围说明见 [E1/R12 amendment](../reports/data/2026-07-11-e01-r12-ownership-scope-amendment/e01_r12_ownership_scope_amendment.md)。新训练授权已存在，但只有本手册全部 prelaunch gate 通过后才能执行。

r5 attempt 已在真实训练循环前 fail closed，根因为 Hydra 从只读 source-root 初始化 `single_train.log`；r5 的 7 个失败任务、0 steps、0 checkpoints、0 summaries 不进入性能证据，也不得 retry、resume 或进入 RISK-08。r5 根目录保持不可变：`/data/Zijian/goal/aaai27_queue/2026-07-11-risk0607-6f18b3d-r5`。

GPU0 上的 CLOSE-10 PID `2568867` 历史上已在动态探针前自然消失，未被干预；这不授权使用 GPU0。r6 即使 GPU0 空闲也只允许 `gpu_ids=[1]`，每张卡同时最多一个新增训练进程。所有新增实验固定 `seed=100`，每个 dated root 只允许一次 attempt，`failure_policy=fail_closed`，不得静默 retry、改 seed、改阈值、改 corruption 或使用 adaptive backoff。DiffuRec 不进入本队列；本手册也不把任何历史 DiffuRec 工件称为 DiffRec。

## 🔒 r6 runtime launch contract

r6 只能从全新的 immutable source root 和 dated queue root 启动。代码身份来自绝对路径（Python 与 `single_train.py`/controller entry），GPU task 的 `cwd` 必须与其唯一 `run_dir` 相等且位于 queue root；因此 Hydra 的相对日志、checkpoint、summary 和 marker 写入不会落入 source root。method-pass continuation adapter 也强制 `gpu_ids=[1]`。唯一例外是 `gpu_slots=0` 的 CPU `contract_gate`：它可从 immutable source cwd 执行，用于启动前契约检查，不是训练任务。

真实启动前必须在独立 probe `run_dir` 执行 Hydra 入口，加载 logging、dataset reconciliation、graph/model/noise、optimizer/EMA 以及严格 text-bank/null/`phi_R` 资产，然后在 dataloader、optimizer step、validation/test、sampling、checkpoint、summary 和 metrics 之前返回，并只写 `startup_probe.json` 与 `STARTUP_PROBE_PASS`。科学 queue manifest 禁止携带 `training.startup_probe_only` override。

### 流程图

```mermaid
flowchart TB
    accTitle: RISK-04 to RISK-08 Gate Flow
    accDescr: Train-only corruption assets are built and hashed first, then a severe-corruption gate and prospective freeze authorize a dated pilot manifest; only artifact-backed RISK-08 can unlock later work.

    r3[Failed r3 audit] --> stop_r3[(Keep r3 stopped)]
    e1([Revision-scoped E1 pass]) --> checkpoint[Verify checkpoint contract]
    checkpoint --> banks[Bind 12 dated banks]
    banks --> severe{Steam 60% gate >= 20% drop?}
    severe -->|No or pending| stop[(Stop; no training)]
    severe -->|Yes| freeze[Freeze RISK-05 protocol]
    freeze --> manifest[Build 14 plus 8 queue manifest]
    manifest --> validate[Controller validate and no-training smoke]
    validate --> pilot[Conditionally authorized seed-100 pilot]
    pilot --> decision[RISK-08 artifact decision]
    decision -->|risk_gated_method| continuation[Unlock only approved continuation]
    decision -->|audit_only or submission_stop| stop

    classDef gate fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#78350f
    classDef action fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#1e3a5f
    classDef stop fill:#fee2e2,stroke:#dc2626,stroke-width:2px,color:#7f1d1d
    classDef success fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#14532d
    class e1,continuation success
    class checkpoint,banks,freeze,manifest,validate,pilot,decision action
    class severe gate
    class r3,stop_r3,stop stop
```

## 🧱 RISK-04 资产生成

### 输入契约

配置 JSON 必须只列 `Beauty` 和 `Steam`，并为每个数据集提供 clean item embeddings、train transitions、冻结 split SHA-256；`strata_count` 和 `corruption_seed` 分别固定为配置值与 `100`。transition 文件名或路径不得包含 `val`、`validation`、`test` 或 `testing` 组件。builder 只读 train transitions 和 clean embedding，不读取任何验证或测试目标。

### 生成命令

```powershell
$Root = 'E:\PreferGrow\.worktrees\aaai27-seed100-controller'
$Config = "$Root\tmp\risk04-2026-07-11-config.json"
$Risk04 = 'E:\PreferGrow\dated\risk04-2026-07-11'
python "$Root\scripts\build_risk04_corruption_banks.py" `
  --config-json $Config `
  --output-dir $Risk04 `
  --generated-at '2026-07-11T09:00:00+08:00'
```

builder 会在 `<Risk04>/banks/{Beauty,Steam}/level-{000,020,040,060,080,100}/` 写入 `embeddings.npy`、训练兼容的 `embeddings.pt`、`item_ids.json`、`bank_manifest.json` 和 `SHA256SUMS`，并写入 `risk04_bundle.json`、`RISK-04_ASSETS_READY.json` 以及唯一的 `RISK-04_PASS.json`、`RISK-04_STOP.json` 或 `RISK-04_PENDING.json`。如果 dated root 已存在，命令立即失败，不覆盖已有内容。

Steam severe corruption 必须是 popularity-stratified 的 **60% item-embedding permutation**。资产生成先于门判定，因此即使门失败，资产 hash 仍保留；门失败时不得删除旧资产、不得启动训练、不得在论文中写 adaptive-backoff 经验。

### 只读验证与门判定

```powershell
python "$Root\scripts\validate_risk04_banks.py" `
  --bundle-dir $Risk04
```

通过条件是：12 个 bank 均存在且 hash 可复算；六个 corruption level 完整；seed、item-ID 顺序、row norm 和 train-only provenance 一致；`severe_gate.status=pass` 且 `relative_clean_drop >= 0.20`。`pending` 或 `stop` 都是硬停止，不得把它们解释成“接近通过”。

## 🔒 RISK-05 预注册冻结

RISK-05 只能绑定已经验证的 RISK-04 bundle、train-only preflight 报告和一个终态且 revision 明确的 E1 marker。preflight 必须携带 Beauty/Steam 六个 level 的 bank hashes；builder 会拒绝缺失或不匹配的 bank hash。冻结协议包含 EPE/PNE@10、`phi_R`、相邻 reversal、Spearman 和 worst-delta 的阈值，且不写入 validation/test metric；阈值一旦写入 dated root，不得根据 pilot 结果回改。

这里的 `phi_R` 是 Beauty/Steam controlled-corruption pilot 的预注册实验 gate：`clip((R_100-R_D)/(R_100-R_clean),0,1)`。它不替换论文主方法的 `phi(U_ds)`，也不能直接冒充四域 final-v2 efficacy。若论文最终采用 EPE risk gate，必须另行重写方法与创新叙事；本轮只把 `phi_R` 解释为受控风险实验中的操纵变量。

```powershell
$Preflight = "$Risk04\risk_preflight_report.json"
$E1 = "$Root\docs\reports\data\2026-07-11-e01-gzero-production-trace-r12\RISK-02_PASS.json"
$Risk05 = 'E:\PreferGrow\dated\risk05-2026-07-11'
python "$Root\scripts\build_risk05_preregistration.py" `
  --risk04-dir $Risk04 `
  --preflight-json $Preflight `
  --e1-marker-json $E1 `
  --output-dir $Risk05 `
  --generated-at '2026-07-11T10:00:00+08:00'
```

输出包括 `protocol/risk05_preregistration.json`、`markers/RISK-05_PASS.json` 或 `RISK-05_STOP.json`、`markers/RISK-02_PASS.json`、`manifests/source_hashes.json` 和 `risk05_bundle.json`。只有 `RISK-05_PASS.json` 才能进入 RISK-06/RISK-07 manifest builder；`RISK-05_STOP.json` 只记录 no-go，不解锁训练。

## 🧪 RISK-06/RISK-07 dated pilot manifest

### 固定矩阵

| 分支 | Beauty | Steam | 总数 | 允许的 arm |
|---|---:|---:|---:|---|
| `e1_pass` | 7 | 7 | 14 | 一个 host；`text_anchor_only` 与 `risk_gated_full` 在 0/60/100 |
| `e1_fail_audit` | 4 | 4 | 8 | 一个 host；仅 `text_anchor_only` 在 0/60/100 |

每个任务都必须是 seed 100、`max_attempts=1`、`failure_policy=fail_closed`、一个 GPU slot、独立 run directory、common evaluator `e0_full_tail_v2` 和 validation-only selector `validation-ndcg10-rowweighted-v1`。四个 host task 必须使用 `graph.type=adaptive` 并等待 `best_summary_adaptive.json`；其 learned proposal 是 graph-owned `p1`。18 个 evidence-conditioned task 必须使用 `graph.type=proposal_adaptive` 并等待 `best_summary_proposal_adaptive.json`。manifest builder 不创建 checkpoints，不启动 controller，也不创建 tmux。

r4 manifest SHA-256 `8d5989f6e91006b0ab7ffe0e3326945719964d9ffec98e4f2742450723801838` 因把 host 错绑为 `graph.type=hybrid` 而在训练前 STOP；`controller=null`、`record_count=0`、`actual_gpu_hours=0.0`，且没有 `runs/` 目录。r4 不得恢复、覆盖或进入 RISK-08。任何后继 attempt 必须使用修复后的新 commit、immutable source 和 never-used dated root。

### 构建与验证命令

先准备只包含 queue 运行时位置、immutable source revision、source manifest、ledger hash、evaluator/selector 配置、精确 RISK-04 root 和 Beauty/Steam 数据位置的 protocol JSON。`run_root_posix` 必须与 `queue_root_posix` 完全相等；不得使用旧 `bank_root_posix` 猜路径。再执行：

```powershell
$Queue = 'E:\PreferGrow\dated\queue-2026-07-11'
$PilotProtocol = "$Root\tmp\risk0607-protocol-2026-07-11.json"
python "$Root\scripts\build_risk0607_pilot_manifest.py" `
  --risk05-dir $Risk05 `
  --e1-marker-json $E1 `
  --output-dir $Queue `
  --protocol-json $PilotProtocol

python -m scripts.aaai27_queue.cli validate `
  --queue-root $Queue `
  --manifest "$Queue\queue\queue_seed100.json" `
  --json

python -m scripts.aaai27_queue.cli dry-run `
  --queue-root $Queue `
  --manifest "$Queue\queue\queue_seed100.json" `
  --e1-outcome pass `
  --risk08-exit pending
```

在 Linux/l20 上，`--queue-root` 必须等于 manifest 中的绝对 POSIX `run_root`/queue containment root；不能把 Windows 路径或工作站路径混入远端 manifest。r6 manifest 必须固定 `gpu_ids=[1]`，并逐任务满足 `cwd==run_dir`。`validate` 和 `dry-run` 不启动训练。用户已授权“全部 gate 通过后继续”，但任一 gate 未通过仍必须 fail closed。

生成后必须逐任务核验：`argv work_dir == task.run_dir`；4 个 host 使用 `graph.type=adaptive` 和 `best_summary_adaptive.json`；18 个 evidence arm 使用 `graph.type=proposal_adaptive`；6 个 full 使用独立 `full_c{0,60,100}`；embedding 路径来自 RISK-04 的 `level-000/060/100`；embedding SHA 可复算；full 的 `gate_dataset_scale_override` 与冻结 `phi_R` 精确相等；evidence task 带 RISK-04/RISK-05 hash；strict full 能加载 null curve 且不会自动回退到默认 U_ds report。

## 🧾 训练授权、监控与产物要求

controller 只能消费已验证的 r6 `queue/queue_seed100.json`，并在 GPU1 上最多保持一个新增训练进程。GPU0 的 CLOSE-10 历史任务若仍存在不得杀进程、抢卡或删除目录；即使 GPU0 空闲也不进入 r6 allowlist。新 queue 必须重新跑完整 branch；不得把 r3 的两个 hybrid host summary、r4/r5 的任何 manifest/task identity 或失败日志跨 manifest 拼入 RISK-08。

每个成功任务必须产生：task artifact manifest、validation-selected best checkpoint、真实 stdout/stderr log、summary、split/bank/config/evaluator/selector hashes。当前协议显式设置 `write_snapshot_checkpoint=False`，因此不得把 periodic/latest checkpoint 当作成功前置；best checkpoint 仍由 `write_best_checkpoint=True` 保留。日志必须是实际文件，不得使用没有落盘内容的 `pipe-pane` 代替 structured heartbeat。缺失 summary、非零退出、OOM、hash mismatch 或 run directory 越界均写 terminal fail，不触发 retry。

状态审计命令（只读）：

```bash
# Set this to the absolute POSIX run_root recorded in the new r6 queue_seed100.json.
QUEUE_RUN_ROOT=/data/Zijian/goal/aaai27_queue/<new-dated-r6-root>
python -m scripts.aaai27_queue.cli status --queue-root "$QUEUE_RUN_ROOT" --json
```

需要记录 queue manifest hash、controller PID/session、当前 GPU/PID/elapsed、task counts、实际/预测 GPU-hours、`/data` 剩余空间、最近 heartbeat、log/summary/marker 路径和每个 blocked/failed reason。

## 🚪 RISK-08 判定与 method-pass 边界

RISK-08 输入必须是：一个无歧义的 E1 marker、RISK-05 PASS 及其 preregistration、经过 controller validator 的 queue manifest、完整分支的 pilot report，以及每个 completed task 对应的 artifact manifest。artifact manifest 必须用 `metrics_provenance.path` 和 SHA-256 指向真实 metrics 文件；pilot report 不得手填 `metrics`。

```powershell
python "$Root\scripts\run_risk08_decision.py" `
  --queue-dir $Queue `
  --e1-marker-json $E1 `
  --risk05-dir $Risk05 `
  --pilot-report-json "$Queue\pilot-report.json"
```

输出是唯一的 `markers/RISK-08_EXIT.json`：

| exit | 条件 | 后续动作 |
|---|---|---|
| `risk_gated_method` | E1 pass 且冻结 phenomenon criteria 全部满足 | 仅解锁批准的 seed-100 continuation |
| `audit_only` | E1 terminal fail 但诊断现象满足 | 保留证据，停止 downstream training |
| `submission_stop` | 现象失败、输入缺失、hash/selector/evaluator/kernel mismatch | 保留证据，停止并回到 Gate-2 决策 |

`E1 pass` 不能单独产生 `risk_gated_method`；没有 artifact-backed RISK-08 就没有 method-pass。RISK-08 写 marker 使用原子创建，重复执行或同时存在多个互斥 marker 会 fail closed。

## 🧯 停止与恢复

### 硬停止

- RISK-04 severe gate 为 `pending` 或 `stop`
- RISK-05 preregistration 与 bank/E1 hash 不一致
- pilot matrix 不是完整的 14/8 分支
- task `code_revision` 与 immutable source 不一致，或 source worktree 非 clean
- 任一 `argv work_dir` 与 `task.run_dir` 不相等
- 任一 embedding 路径/hash 不等于冻结 RISK-04 记录
- full 缺少或改变冻结 `phi_R`，或 strict gate/null-curve 构造失败
- host 不是 `graph.type=adaptive`、summary 不是 `best_summary_adaptive.json`，或 host graph `p1` 不在 optimizer/EMA/checkpoint/common-evaluator 的同一参数合同中
- 出现 seed 101/102、retry、DiffuRec/BERT4Rec、destructive argv 或不在 dated root 下的 run directory
- GPU 被未知进程占用、`/data` 小于 40 GiB 或预算 forecast 超过 168 GPU-hours
- RISK-08 输入缺失、重复、手工 metrics 或 artifact provenance 无法复算

硬停止时不删除旧资产、不杀正在运行的外部任务、不放宽阈值、不改 corruption、不启动备用 seed。需要重新尝试时，必须取得新的明确授权并创建新的 dated root；原 root 只读保留。

### 交接与审计

每一步把命令、exit code、生成路径和 SHA-256 写入唯一执行账本 `issues/2026-07-11_host-core-v2-preflight.csv`。论文 reproducibility 声明必须保留原句：`model selection used validation only; test metrics were logged during development`；本轮不宣称 test 是 untouched final holdout。

## 🔍 复盘清单

| 项目 | 通过证据 |
|---|---|
| E1 implementation | R12 report、E01 pass、RISK-02 pass、source revision `0338cc2…` |
| Checkpoint contract | graph state、training parameter names、EMA shape/count round-trip、common evaluator replay |
| RISK-04 | 12 bank manifests、`SHA256SUMS`、severe gate pass marker |
| RISK-05 | preregistration、freeze marker、RISK-04/E1/preflight hashes |
| RISK-06/07 | 22-task queue manifest、controller `validate`、pass/audit 分支计数 |
| RISK-08 | artifact-backed pilot report、唯一 `RISK-08_EXIT.json` |

## E5：SASRec 四域 atomic baseline（GPU0，seed=100）

本节是 2026-07-11 dated implementation amendment 的执行入口，设计约束见
[`2026-07-11-e05-sasrec-seed100-gpu0-design.md`](../superpowers/specs/2026-07-11-e05-sasrec-seed100-gpu0-design.md)。E5 的作用是给
PreferGrow 提供一个非扩散 sequential-recommendation 外部参照；它不是新的方法调参，也不改变 Gate-2 的前置关系。

### 固定身份与数据协议

- 方法身份固定为最小标准 SASRec：item embedding（含 padding row）、absolute position embedding、causal Transformer encoder 和 full-catalog score head；不复用外部项目的预处理或 checkpoint。
- 只读 l20 的 `dataset/paper_raw_v1/{Steam,ML1M,Beauty,ATG}`，直接消费各目录的 `train_data.df`、`val_data.df`、`test_data.df`、`item_mapping.csv` 和 `protocol.json`；禁止 native resplit、重映射和 sampled-candidate evaluator。
- 四域属于同一个 `E05.SASRec.four-domain` atomic group，必须同时出现在同一 `manifest.json`。任一域失败、缺 artifact 或行数/hash 不一致时，整个组标记 `failed_incomplete_atomic_group`，不报告有利子集。
- 所有任务 `seed=100`、`gpu_ids=[0]`、`max_attempts=1`、`failure_policy=fail_closed`、`cwd==run_dir`；GPU1 上的 r6a 不修改、不抢占、不并入 E5 queue。
- evaluator 固定 `e0_full_tail_v2`，selector 固定 `validation-ndcg10-rowweighted-v1`。checkpoint 只由 validation NDCG@10 选择；test 只在选定 checkpoint 后记录开发期 readout，论文保留：`model selection used validation only; test metrics were logged during development`，不得称 untouched final holdout。

### 代码、manifest 和启动门

以下命令只在新的 immutable source root 和从未使用过的 dated queue root 上执行；根目录已存在时命令必须失败，不得覆盖：

```bash
python3 /data/Zijian/goal/<immutable-source>/scripts/build_e05_sasrec_manifest.py \
  --queue-root /data/Zijian/goal/aaai27_queue/2026-07-11-e05-sasrec-seed100-gpu0 \
  --source-root /data/Zijian/goal/<immutable-source> \
  --dataset-root /data/Zijian/goal/RecDemo/dataset/paper_raw_v1 \
  --ledger-path /data/Zijian/goal/<immutable-source>/issues/2026-07-11_host-core-v2-preflight.csv \
  --code-revision <40-char-immutable-revision>
```

manifest 生成后必须只读核验：任务数为 4、数据集恰为 Steam/ML1M/Beauty/ATG、seed 集合为 `{100}`、GPU 集合为 `{0}`、四个 `atomic_group` 相同、每个 `cwd` 等于自己的 `run_dir`，并且每个 `split_sha256` 与 `protocol.json` 行数契约绑定。正式任务 argv 禁止携带 `--startup-probe-only`。

在正式 queue 前，先使用同一 source 和一个新的 `probe` 目录执行一次 GPU0 startup probe：它必须构造模型并完成一个前向 batch，写出 `startup_probe.json` 的 `STARTUP_PROBE_PASS`，且 optimizer steps、checkpoint 和 metrics 均为 0。随后再读取 `nvidia-smi`、`ps`、`df -h /data`；GPU0 必须无 compute PID、GPU1 的 r6a PID/session 不变、`/data` 可用空间必须大于 40 GiB。任何 probe、hash、PID 或磁盘检查失败均硬停止。

### 正式启动、保留物和审计

```bash
python3 /data/Zijian/goal/<immutable-source>/scripts/run_e05_sasrec_queue.py \
  --manifest /data/Zijian/goal/aaai27_queue/2026-07-11-e05-sasrec-seed100-gpu0/manifest.json
```

queue runner 串行执行 GPU0 上的四个任务，不启动第二个 GPU0 进程；它在每个任务前后检查 GPU occupancy，在非零退出、缺 artifact、hash mismatch 或 GPU 残留时 fail closed，不 retry。每个域必须产生 `sasrec_best.pt`、`best_summary_sasrec.json`、`metrics_sasrec.json`、`artifact_manifest.json` 与真实 `stdout.log`；只保留 best checkpoint，不写周期快照。

最终回读并存档：`manifest_sha256`、`queue_status.json`、四个 task 的 PID/argv/cwd/elapsed、首次 training-loop 日志行、validation-selected epoch、test readout、row counts、split/config/evaluator/selector hashes、GPU0/GPU1 前后快照和磁盘余量。结果在手册和论文中只能标为 `single-run observation`；未完成四域时写 `incomplete/NA`，不得推断或补数字。
| 论文措辞 | 单 seed 只写 observation；不写 significant/stable/statistically equivalent/within noise |

本手册没有把计划数字、unit test 或 no-training smoke 当作性能结果；如果某个产物不存在，论文表格应写 `NA` 和原因，不能推断或补造数值。单 seed 结果只能写 single-run result/observation，不能使用 significant、stable、statistically equivalent 或 within noise。
