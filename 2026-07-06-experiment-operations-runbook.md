# 实验操作指南:新会话从零到跑通(2026-07-06)

> 目的:任何一次新会话(新电脑重启/断连恢复/隔天继续),按本文从第 0 步走到训练发射与读数,不需要重新摸索。综合自 `2026-07-04-l20-server-ops-note.md`(桌面)、SPRINT-04→07 账本证据链与脚本真实接口。**凡与本文冲突的,以最新 spec + 最新 CSV 为准。**

---

## 0. 新会话快速卡片(10 步,详情见对应章节)

```text
1. 确认 VPN 隧道通(本机有 10.7.7.x IP)………………§1
2. ssh l20 && hostname → ubuntu ……………………………§1
3. 远端 git 状态检查(勿盲目 pull)…………………………§4
4. 本地改动 → commit → push → 远端 ff-only pull ……§4
5. 确认数据集/bank/模型齐全(§5.6 自检命令)…………§5
6. tmux ls 看有没有跑着的会话(先接管再新开)………§6
7. 选发射方式:主表跑 / 消融对照 / 编排器 …………§7
8. 快照监控(sequential,别并行 summarize)…………§8
9. 读数回写 docs/reports/data/<日期>/ ……………………§9
10. 断连不慌:tmux 还在跑,用 retry helper 轮询 ……§10
```

## 1. 网络与连接

**前置:OpenVPN 隧道**(iKuai 服务端,客户端已装 openvpn-gui):

```powershell
# 本机是否拿到隧道 IP(应看到 10.7.7.x,例如 10.7.7.4)
ipconfig | findstr "10.7.7"
# OpenVPN 客户端日志(看最近一条是否 Initialization Sequence Completed / 每小时 soft reset)
Get-Content $env:USERPROFILE\OpenVPN\log\OpenVPN-Client.log -Tail 15
```

- 有 10.7.7.x 但 `ssh l20` 超时 → **远端问题**(L20 宕机或实验室内网故障),联系管理员,本地无解;
- 没有 10.7.7.x → 在 OpenVPN GUI 里重连;
- SSH 配置(`~/.ssh/config`,已配好):`Host l20 → 172.18.0.40, User zijian, Port 22, IdentityFile ~/.ssh/id_ed25519`。

**连接与一键体检**:

```powershell
ssh l20   # 登录后默认在 /home/zijian
# 一键检查远端关键状态(来自运维笔记 §10.1)
ssh l20 "cd /data/Zijian/goal/RecDemo && git branch --show-current && git rev-parse --short HEAD && git status --short | head -n 40 && echo '---DATASETS---' && ls -1 /data/Zijian/goal/RecDemo/dataset/paper_raw_v1 && echo '---TMUX---' && tmux ls 2>/dev/null || true"
```

⚠️ Windows 侧脚本发起的 ssh 一律走 **argv 形式、shell-free**(项目脚本已内置);手写命令时注意引号嵌套。ssh 会 flap(间歇超时),长任务永远放 tmux,轮询交给 retry helper(§10)。

## 2. 环境

### 2.1 本地(Windows,E:\PreferGrow)

- Python:`E:/anaco/python.exe`(Anaconda);跑单测遇到 OMP 报错时前置 `$env:KMP_DUPLICATE_LIB_OK='TRUE'`;
- 单测示例:`& 'E:/anaco/python.exe' -m unittest tests.test_run_text_side_main_table_tmux`;
- 本地只做:代码/测试/报告构建/发射器 `--print-only` 演练;**不跑训练**。

### 2.2 远端(l20)

- **Python 是 venv,不是 conda**;shell 默认 `python` 不可用,永远显式:
  ```bash
  /data/Zijian/goal/PreferGrow/.venv/bin/python   # Python 3.10.12
  # 或 source /data/Zijian/goal/PreferGrow/.venv/bin/activate
  ```
- GPU:两张 L20(48GB),`nvidia-smi` 看占用;GPU 0/1 由发射器的 `GPU_IDS_CSV` 或 `--gpu-id` 指定;
- **模型全部在 `/data/models/` 下**:
  - 文本编码器(t5):`/data/models/sentence-transformers/sentence-t5-xl`(已核实存在);
  - 图像编码器(siglip):同在 `/data/models/` 下,首次使用先 `ls /data/models/` 确认确切子目录名再填给脚本;
- 磁盘:`/data` 曾经写满导致脚本变 0 字节(FOLLOWUP-02 教训)——大任务前 `df -h /data` 检查,应急可用 `/tmp` 跑完再归档回仓库目录。

## 3. 目录地图

| 位置 | 路径 | 用途 |
|---|---|---|
| 本地仓库 | `E:\PreferGrow` | 开发/提交/报告 |
| 远端仓库(**dirty root**) | `/data/Zijian/goal/RecDemo` | 数据集、Gate0 工件、历史产物;工作区**长期是脏的** |
| 远端**clean root** | `/data/Zijian/goal/RecDemo_clean_main` | **官方跑唯一合法执行根**(见 §7.1 红线) |
| 运行产物根 | `/data/Zijian/goal/RecDemoRuns/main_table_text_side` | `<dataset>_proposal_adaptive_mainpath/{checkpoints,checkpoints-meta,logs}`;消融跑在 `<dataset>_proposal_adaptive_ablation_<mode>` |
| 数据集根 | `/data/Zijian/goal/RecDemo/dataset/paper_raw_v1/{ML1M,Steam,Beauty,ATG,ASO}` | 再生 split + 冻结 bank |
| 原始数据 | `/data/Zijian/goal/RecDemo/dataset/raw/amazon` 等 | wget 下来的原始压缩包 |
| Gate0/效用工件 | `/data/Zijian/goal/RecDemo/docs/reports/data/2026-07-02-gate0` | `gate0_text_utility_report.json`(U_ds,训练发射器要读它) |
| 腐蚀 bank | `/data/Zijian/goal/RecDemoRuns/beauty_corruptions` | 冻结 token-dropout bank,勿重生成 |
| 当前 SPRINT-07 读数目录 | `/data/Zijian/goal/RecDemo_clean_main/docs/reports/data/2026-07-06-sprint07` | `sprint07_control_table.csv` + `sprint07_control_report_zh.md` |
| 当前 CLOSE-02 读数目录 | `/data/Zijian/goal/RecDemo_clean_main/docs/reports/data/2026-07-06-close02-ml1m-noise-floor` | `close02_ml1m_noise_floor_{table,report}.csv/json/md` |

补充说明:
- `clean root` 表示**官方 provenance 根**;它应尽量保持干净,但不要假设服务器上的 `git status --short` 永远为空。
- 2026-07-06 实机检查显示,`/data/Zijian/goal/RecDemo_clean_main` 上可能暂存 `docs/reports/data/...`、`build_sprint07_control_report.py` 等运行时文件;`git pull --ff-only` 前必须先看状态。

### 3.1 2026-07-06 实机状态快照(带日期,别当成永恒真理)

- `ssh l20` 可通,`hostname=ubuntu`;
- `clean root` 当时位于 `main@74a7ea1`;
- 活跃 tmux 会话实测为 `sprint07_report_watch`、`sprint07_steam_ctrl`、`sprint07_steam_followup`;
- `/data/Zijian/goal/RecDemo_clean_main/docs/reports/data/2026-07-06-sprint07/` 已存在 live 表和 live 中文报告;
- `/data/Zijian/goal/RecDemoRuns/close02_ml1m_noise_floor/` 在真正发射 `CLOSE-02` 之前**不会自动出现**;
- `Steam/text_anchor_only` 已完成;`Steam/global_p` 在 GPU1 上继续跑(2026-07-06 22:31 左右已到 `step 10000`),因此 live 表里出现 `running` 是正常的。

## 4. 代码同步标准流(每次会话必做)

**原则:本地是唯一真源;远端只 ff-only 拉取;远端脏区先看后动。**

```powershell
# ① 本地:确认本次改动 → 提交 → 推送(不要把无关脏文件卷进来)
git status --short
git add <本次相关文件> ; git commit -m "..." ; git push origin main
```

```bash
# ② 远端 dirty root:先看再拉
cd /data/Zijian/goal/RecDemo && git status --short | head -30
git pull --ff-only origin main        # 仅在确认无冲突风险后

# ③ 远端 clean root:官方跑之前必须同步到目标提交(理想 clean,但先看状态再拉)
cd /data/Zijian/goal/RecDemo_clean_main && git status --short   # 理想为空;若有报告目录/临时脚本,先确认不会挡住 ff-only pull
git pull --ff-only origin main && git rev-parse --short HEAD    # 记下 HEAD,manifest 会记录它
```

⚠️ 如果远端已有**同路径未跟踪文件**(例如 live 期间手工放进去的 `scripts/build_sprint07_control_report.py` 这类文件),`git pull --ff-only` 也可能因为“would be overwritten”失败。先 `git status --short` 看清楚,再决定是挪走、提交、还是改用应急同步。

**应急通道**(git 不可用/只需送几个运行时文件):`& 'E:/anaco/python.exe' scripts/sync_remote_recdemo_code.py --print-plan` 先看计划,去掉 `--print-plan` 执行(单 ssh tar 流,同步+校验 21 个运行时文件)。注意:这只解燃眉之急,事后仍要补一次正规 git 同步,否则远端 HEAD 与文件不一致(SPRINT-04 曾因此踩坑)。

## 5. 数据集从零处理管线(raw-data-first 协议)

> 完整五步。已就绪的数据集跳到 §5.6 自检即可;**新数据集或怀疑污染时才全跑**。所有产物要求字节稳定(固定 seed)并记录 hash。

### 5.1 原始数据获取

```bash
# Amazon 系(Beauty/ATG/ASO):snap.stanford.edu 分类文件,断点续传
# 现成脚本(后台 fetch + 完成后自动 build,日志在 $ROOT/logs/):
bash scripts/prepare_aso_atg_and_build.sh          # ASO(Apps for Android)+ ATG(Toys and Games)
bash scripts/prepare_remaining_amazon_raw_and_build.sh
# ML1M / Steam:专用复现脚本(下载源与处理规则见脚本头注释)
/data/Zijian/goal/PreferGrow/.venv/bin/python scripts/reproduce_ml1m_raw.py
/data/Zijian/goal/PreferGrow/.venv/bin/python scripts/reproduce_steam_raw.py
```

### 5.2 构建 paper_raw_v1 数据集(split 再生)

```bash
cd /data/Zijian/goal/RecDemo
/data/Zijian/goal/PreferGrow/.venv/bin/python scripts/build_paper_datasets.py \
  --datasets <ML1M|Steam|Beauty|ATG|ASO> --skip-download --overwrite
```

产物:`dataset/paper_raw_v1/<DS>/` 下的交互序列 + train/val/test split + `protocol.json`(记录原始来源/映射/过滤/去重/切分规则)。**split hash 会进训练 manifest。**

### 5.3 文本 bank(冻结编码,一次性)

```bash
/data/Zijian/goal/PreferGrow/.venv/bin/python scripts/build_text_side_embeddings.py \
  --dataset <DS> --model-path /data/models/sentence-transformers/sentence-t5-xl
```

产物:`text_bank.csv`(每物品一行:题名/品牌/类目/描述)+ `sentence_t5_xl_item_emb.pt`(**bank hash 之源**)。编码器**从不微调**。图像侧同理用 `/data/models/` 下的 siglip 目录(管线脚本在用到时确认参数名)。

### 5.4 零点校准曲线

```bash
/data/Zijian/goal/PreferGrow/.venv/bin/python scripts/build_agreement_null_curves.py \
  --dataset-dir dataset/paper_raw_v1/<DS>
```

产物:`agreement_null_curves`(按历史长度分桶的 μ_null/σ_null,固定 seed,字节稳定,记录 bank hash)。注意:ML1M 是单长度桶(固定窗口),属已知事实,不是 bug。

### 5.5 U_ds 效用统计量(门控输入)

```bash
# 冻结估计量:4000 条 train 转移 / seed 7 / 100 个流行度负例(spec 7.3,参数不可动)
/data/Zijian/goal/PreferGrow/.venv/bin/python scripts/build_gate0_text_utility_report.py ...
# 产物并入 docs/reports/data/2026-07-02-gate0/gate0_text_utility_report.json(带 bank/split hash)
```

训练发射器默认读 `TEXT_UTILITY_REPORT_PATH=$REPO_ROOT/docs/reports/data/2026-07-02-gate0/gate0_text_utility_report.json`,新数据集必须先有此报告才能开 v2 门控跑。

### 5.6 就绪自检(每次发射前 30 秒)

```bash
for d in ML1M Steam Beauty ATG ASO; do
  echo "== $d =="; ls /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/$d | \
  grep -E "text_bank|sentence_t5_xl_item_emb|agreement_null|protocol" || echo "  !! 缺件"
done
```

⚠️ **ASO 历史教训**:曾缺 `sentence_t5_xl_item_emb.pt`,不要默认它像 Beauty 一样就绪。

## 6. tmux 标准操作与命名约定

```bash
tmux ls                                    # 永远先看有没有活会话(接管优先于新开)
tmux new -s <name> "cd /data/Zijian/goal/RecDemo_clean_main && <命令>"   # 一把启动
tmux attach -t <name>                      # 接管;退出不杀:Ctrl+b 再按 d
tmux capture-pane -pt <name> -S -200       # 抓最近 200 行(不打扰运行)
tmux list-panes -a -F '#S | dead=#{pane_dead} | current=#{pane_current_command} | pid=#{pane_pid} | cmd=#{pane_start_command}'
tmux kill-session -t <name>                # 确认无用后再杀
```

**命名约定(沿用历史)**:`gate0_utilde`、`textside_main_table_gpu0/1`、`sprint05_backfill_gpu1`、`sprint05_official_orchestrator`、`sprint05_watchdog`、`sprint07_beauty_ctrl`/`sprint07_steam_ctrl`、`sprint07_report_watch`、`close02_ml1m_noise_floor`、`aso_validation_gpu0`。新任务照 `<行号>_<对象>_<gpu>` 起名。
补充:像 `sprint07_steam_followup` 这类名字通常是**手工补单时临时开的 relay session**,不是 `launch_sprint07_control_tmux.py` 的默认产物;看到它说明有人在把剩余 arm 串行接力跑完。
⚠️ tmux 内启动脚本**一律绝对路径**(曾因 cwd 漂移到 /home/zijian 找不到相对路径脚本,SPRINT-04 教训)。

## 7. 训练/评估发射

### 7.1 官方纪律红线(先读)

1. **官方跑只认 clean root**:`run` 的 manifest 记录 `provenance.repo_root`,不是 `/data/Zijian/goal/RecDemo_clean_main` 的一律判 `invalid_stale`,白跑;
2. **冻结参数零改动**:`v2 / g_max=0.5 / k=2.0 / τ0=0.2 / φ(0.70,0.10) / U_ds 工件 hash 对齐`;
3. **存储纪律**:`WRITE_BEST_CHECKPOINT=True`、`WRITE_SNAPSHOT_CHECKPOINT=False`(只留 best);
4. **选择器**:early stop = `val ndcg10 @ p5`,patience 5,min_step 5000;
5. 每跑必产 `frozen_run_manifest.json`(config/seed/bank/null/split/U_ds 五 hash),读数前先核 manifest。

### 7.2 主表/验证跑(标准发射器)

```bash
# 在 tmux 内、clean root 下:
cd /data/Zijian/goal/RecDemo_clean_main
FORCE=1 SKIP_EXISTING=0 DATASETS_CSV=ML1M,ATG GPU_IDS_CSV=1 \
  bash scripts/run_text_side_main_table_tmux.sh /data/Zijian/goal/RecDemo_clean_main
```

关键环境变量(默认值即冻结值,勿随意覆盖):

| 变量 | 默认 | 说明 |
|---|---|---|
| `DATASETS_CSV` | 空=Steam,ML1M,Beauty,ATG | 逗号分隔选数据集(含 ASO 需显式写) |
| `FORCE` / `SKIP_EXISTING` | 0 / 1 | ⚠️ 默认会**跳过已有 summary 的数据集**;强制重跑要 `FORCE=1 SKIP_EXISTING=0`(曾因默认值意外触发 Beauty 新跑) |
| `GPU_IDS_CSV` / `SESSION_PREFIX` | 0,1 / textside_main_table | 卡与会话名 |
| `MODEL_PATH` | /data/models/sentence-transformers/sentence-t5-xl | t5 位置 |
| `TEXT_KERNEL_VERSION` | v2 | 门控核版本 |
| `TEXT_UTILITY_REPORT_PATH` | gate0 U_ds json | φ(U_ds) 数据源 |
| `TEXT_ABLATION_MODE` | none | `u_shuffle` / `text_anchor_only` / `global_p`(消融跑自动用独立 run_dir `*_ablation_<mode>`) |
| `TEXT_INJECTION_MODE` | kernel | encoder/loss/kernel 三位置 |
| `DRY_RUN` | 0 | 演练不落盘 |

每数据集固化超参(脚本内置勿改):Steam lr=1e-3/npr=0.05;ML1M lr=1e-4/npr=0.1/score;Beauty lr=1e-4/npr=0.1;ATG lr=1e-3/npr=0.2/score。

### 7.3 编排器模式(多波次自动接力)

```powershell
# 本地生成远端命令先演练,确认后去掉 --print-only 真发射
& 'E:/anaco/python.exe' scripts/launch_sprint05_official_tmux.py --print-only
# 远端产生两个会话:sprint05_official_orchestrator(等待/接力发波)+ sprint05_watchdog(自动快照)
```

### 7.4 对照/消融臂(SPRINT-07 型)

```powershell
& 'E:/anaco/python.exe' scripts/launch_sprint07_control_tmux.py --print-only          # Beauty gpu0 + Steam gpu1 全臂队列
& 'E:/anaco/python.exe' scripts/launch_sprint07_control_tmux.py --datasets Steam --ablation-modes text_anchor_only global_p   # 补剩余两臂(参数用空格分隔,不是逗号)
```

如果当时网络不稳、或你不想手工盯 `Steam/global_p` 结束,可以直接挂本地 watcher:

```powershell
& 'E:/anaco/python.exe' scripts/retry_sprint07_when_l20_ready.py `
  --log-path E:/PreferGrow/logs/sprint07_to_close02_chain.log `
  --local-python E:/anaco/python.exe `
  --local-report-dir E:/PreferGrow/docs/reports/data/2026-07-06-sprint07 `
  --launch-close02-on-complete `
  --close02-seeds 100 101 102
```

它会做三件事:
1. 轮询远端 `sprint07_control_table.csv` 是否八行全 completed;
2. 一旦完成,把远端 `sprint07_control_table.csv` 和 `sprint07_control_report_zh.md` 拉回本地同 dated 目录;
3. 然后自动发 `CLOSE-02` 的 `launch_close02_ml1m_noise_floor_tmux.py`;
4. `CLOSE-02` 发出后继续轮询远端 `close02_ml1m_noise_floor_table.csv`,等 2-3 个种子都 completed 后,再把 `close02_ml1m_noise_floor_{table,report}.csv/json/md` 拉回本地 dated 目录。

### 7.5 CLOSE-02 宿主噪声地板(ML1M core 多种子)

> 用途:给 `CLOSE-02` 跑 2-3 个 **host/core** 种子,量化 ML1M 的 run-to-run noise floor。这里不是 text-side,而是 `graph.type=hybrid` + `text_side.enabled=False` 的宿主线。

```powershell
# 本地先看远端命令,确认 GPU 空出来再真发射
& 'E:/anaco/python.exe' scripts/launch_close02_ml1m_noise_floor_tmux.py --print-only --seeds 100 101 102
```

```text
远端默认:
- session: close02_ml1m_noise_floor
- run root: /data/Zijian/goal/RecDemoRuns/close02_ml1m_noise_floor
- repo root: /data/Zijian/goal/RecDemo_clean_main
- dataset: /data/Zijian/goal/RecDemo/dataset/paper_raw_v1/ML1M
- selector: val ndcg10 @ p5
- checkpoints: best only (no snapshot)
```

发射后读数:

```powershell
ssh l20 "cd /data/Zijian/goal/RecDemo_clean_main && /data/Zijian/goal/PreferGrow/.venv/bin/python scripts/build_close02_ml1m_noise_floor_report.py --output-dir /data/Zijian/goal/RecDemo_clean_main/docs/reports/data/2026-07-06-close02-ml1m-noise-floor"
```

⚠️ `build_close02_ml1m_noise_floor_report.py` 的默认 `--run-root` 是 **L20 上的 Linux 路径**;在 Windows 本地直接运行默认参数读不到 `/data/...`。正常做法有两种:

1. 让 `retry_sprint07_when_l20_ready.py --launch-close02-on-complete` 自动在远端刷新报告并 `scp` 回本地;
2. 或者像上面这样在 `l20` 上执行报告脚本,再手工 `scp` 三个工件回 `E:/PreferGrow/docs/reports/data/2026-07-06-close02-ml1m-noise-floor/`。

固定产物目录:

```text
docs/reports/data/<today>-close02-ml1m-noise-floor/
- close02_ml1m_noise_floor_table.csv
- close02_ml1m_noise_floor_report.json
- close02_ml1m_noise_floor_report_zh.md
```

## 8. 监控与读数

```powershell
# 顺序快照(status+compare 一条命令,防竞态)——首选
& 'E:/anaco/python.exe' scripts/capture_text_side_main_table_snapshot.py
```

```bash
# 远端手动看:训练日志尾部(EARLY_STOP_MONITOR 行 = step/metric/wait_counter/NEW_BEST)
tail -50 /data/Zijian/goal/RecDemoRuns/main_table_text_side/<run>/logs/*.log
# 选中 checkpoint 摘要
cat /data/Zijian/goal/RecDemoRuns/main_table_text_side/<run>/checkpoints-meta/<DS>/best_summary_proposal_adaptive.json
```

⚠️ **并行竞态**:`summarize_text_side_main_table_runs.py` 与 `compare_text_side_main_table_to_core.py` 同时打同一 /tmp 目录会读到 stale status——**永远顺序执行**或直接用快照脚本。
⚠️ compare 的 live 值:运行中的跑会忽略尾部不完整 test 块(已修复),live 列为空先怀疑跑还没进入 test 阶段。
⚠️ `build_sprint07_control_report.py` 和 `build_close02_ml1m_noise_floor_report.py` 对 `status!=completed` 的行**隐藏 provisional metrics**;live 期间只读 `status`、`last_logged_step`、日志尾部,不要把半跑出的 summary 数字当 final。
对照臂报告:`build_sprint07_control_report.py` 以**日志完成标记**判 completed,live 跑不会被误报为完成。
`CLOSE-02` 的 watcher 也是通过**远端先刷新 report,再同步 dated artifact**的方式工作,不是在 Windows 上直接读 `/data/...`。
SPRINT-07 的当前固定文件名就是:
- `docs/reports/data/2026-07-06-sprint07/sprint07_control_table.csv`
- `docs/reports/data/2026-07-06-sprint07/sprint07_control_report_zh.md`

## 9. 读数回写

1. 远端产物落 `RecDemo_clean_main/docs/reports/data/<日期>-<主题>/`;
2. 拉回本地同路径,构建报告(如 `build_sprint05_gate1_report.py`)——报告脚本会自动核 manifest 五 hash;
3. 本地 `git add docs/reports/data/<...> && git commit`;
4. 论文数字**只准**从这些带日期工件回填(tex 注释里引用工件路径)。

## 10. 断连/故障手册

| 症状 | 处置 |
|---|---|
| ssh 超时但 VPN 正常(有 10.7.7.x) | 远端宕机/内网故障 → 等待或联系管理员;tmux 里的跑**在服务器活着时不受影响**,恢复后先 `tmux ls` 清点 |
| ssh 间歇 flap | 长任务全走 tmux;本地起 retry helper 轮询:`retry_gate0_when_l20_ready.py` / `retry_sprint07_when_l20_ready.py`(后台跑,日志在 `logs/*_retry_l20.log`);`retry_sprint07_when_l20_ready.py --launch-close02-on-complete` 现在会一路盯到 `CLOSE-02` 报告也同步回来;注意默认 240 次后仍会自行退出,超时后要手工重启 |
| VPN 掉线 | OpenVPN GUI 重连;看 `%USERPROFILE%\OpenVPN\log\OpenVPN-Client.log` |
| /data 写满 | `df -h /data`;清理或临时到 /tmp 执行,完成后把产物归档回仓库目录(FOLLOWUP-02 先例) |
| 脚本 0 字节/缺失 | 磁盘满时期的产物,重新同步代码(§4 应急通道) |
| 意外触发默认全量跑 | 检查 `FORCE/SKIP_EXISTING/DATASETS_CSV` 三件套;误跑的 run_dir 若污染官方位,判 invalid_stale 并删除后重跑 |
| 结果"完成"但可疑 | 先核 manifest:repo_root 是否 clean_main、五 hash 是否对齐、kernel_version/selector 是否冻结值 |

## 11. 新会话 Checklist(可打印)

```text
□ VPN:ipconfig 有 10.7.7.x
□ ssh l20 通,hostname=ubuntu
□ 远端 git status 看过,ff-only pull 完成(dirty root + clean root 各一次)
□ clean root HEAD 与本地 push 的一致
□ 数据集自检(§5.6)无缺件;df -h /data 余量够
□ tmux ls 清点存量会话,该接管的接管
□ 发射:clean root + FORCE/SKIP_EXISTING/DATASETS_CSV 显式写 + tmux 绝对路径
□ 快照脚本轮询;retry helper 已挂(若 ssh 不稳)
□ 读数:manifest 五 hash 核过才算数
□ 回写:产物→docs/reports/data/<日期>/→commit
```
