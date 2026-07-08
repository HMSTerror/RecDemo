# PreferGrow 项目深度理解与当前优先级地图

日期: 2026-07-09

配套执行文档:

- `docs/reports/2026-07-09-7day-training-writing-execution-timeline-cn.md`
- `docs/reports/2026-07-09-close02-artifact-arrival-playbook-cn.md`

## 1. 这是什么项目

这不是一个单纯的推荐模型代码仓库，而是一个四层耦合的研究交付系统:

1. 模型内核层: 离散扩散推荐模型 PreferGrow 及其 text-side 条件化 proposal 变体。
2. 数据协议层: 从原始数据重建 `paper_raw_v1` 协议数据集与 sidecar。
3. 实验与证据层: 大量 `launch/run/build/analyze/sync` 脚本、dated artifacts、回填表格与审计报告。
4. 论文与 closeout 层: AAAI-27 稿件、claim freeze 纪律、closeout 台账、投稿前验收。

当前真正的项目控制中心不是根目录 `README.md`，而是:

- `issues/2026-07-06_evidence-priced-schedule-and-closeout.csv`
- `docs/superpowers/specs/2026-07-06-evidence-priced-schedule-design.md`
- `docs/reports/2026-07-07-aaai27-handoff-playbook.md`
- `paper/main_v2.tex`

## 2. 当前论文叙事已经发生过一次重定位

根目录 `README.md` 仍在讲原始 PreferGrow 叙事: 离散偏好扩散、preference fading / growing、跨数据集稳定增益。

但当前 AAAI-27 主稿 `paper/main_v2.tex` 与中文对照 `paper/main_v2_zh.md` 已经切换到更保守也更可信的 `fallback-safe` 叙事:

- 中心问题不是“文本一定帮忙”，而是“更强的文本证据可能反而有害”。
- 中心构件不是泛化增强模块，而是对 proposal kernel 的受控门控。
- 中心证据不是“全面领先”，而是 `U_ds` 与倾斜收益的逆序、以及 `g=0` 时的宿主回退安全性。
- 写作纪律受 `Family D` 冻结备忘约束，禁止无证据升级措辞。

所以后续任何训练、分析、写稿，必须以 `main_v2` 体系为准，不能再回到 README 的旧口径。

## 3. 代码主干怎么跑

### 3.1 训练入口

训练入口是 `single_train.py`:

- Hydra 配置入口: `single_train.py:134`
- 运行时数据集 item 数校正: `dataset_runtime.py:49`
- graph 构建: `graph_lib.get_graph`
- 模型构建: `model/transformer.py:592` 的 `SEDD4REC`
- 损失构建: `losses.py:9`
- 采样与评估: `sampling.py:125`

训练循环做四件事:

1. 加载 `train/val/test_data.df`
2. 训练 score model + noise model
3. 定期做 snapshot evaluation
4. 根据 validation selector 维护 `best_summary_*.json` 与 best/latest checkpoint

### 3.2 数据格式

运行数据以 `train_data.df / val_data.df / test_data.df` 为核心，列为:

- `seq`
- `len_seq`
- `next`

`data.py` 只是把这些 pickle 文件直接读成 `DataLoader`，因此数据协议是否一致极其关键。

### 3.3 图与扩散核

`graph_lib.py` 中最重要的不是旧的 `pair/point/hybrid`，而是:

- `AdaptiveWise`
- `ProposalAdaptiveWise`

前者学习全局 `nonpreference_probs`，后者要求显式传入用户级 `proposal`，并把它写入:

- 前向转移
- 反向概率比
- 极限分布采样
- score entropy

也就是说，当前研究主线不是“在 encoder 上加文本”，而是“把文本影响推进核本身”。

### 3.4 text-side 条件化

`model/text_side.py` 是现在最值得读的文件之一。

它做的不是一个大而泛的文本模块，而是一套非常克制的 proposal builder:

1. 从 `item_metadata.csv` 生成 `text_bank.csv`
2. 从 item embedding 与历史序列构造 content anchor
3. 计算用户级信号:
   - agreement
   - completeness
   - history reliability
4. 从数据集级 `U_ds` 读出 `phi(U_ds)`
5. 组合出门值 `g`
6. 在宿主 `p_core` 与 content anchor 之间插值，输出 proposal

支持三种注入方式:

- `kernel`
- `encoder`
- `loss`

但当前论文的理论安全性和核心主张只真正绑定 `kernel` 注入。

## 4. 数据与实验主线怎么落地

### 4.1 论文协议数据集

`scripts/build_paper_datasets.py` 负责从原始数据生成 `dataset/paper_raw_v1/*`。

它会统一落下:

- `train_data.df / val_data.df / test_data.df`
- `data.txt`
- `item_mapping.csv`
- `item_metadata.csv`
- `protocol.json`
- `items_pop.npy`
- `data_statis.df`

这意味着:

- 当前论文实验并不应该直接依赖旧 `dataset/*` 的偶然状态
- 后续 baseline、reproduction、审计都应尽量统一到 `paper_raw_v1`

### 4.2 Gate-0 / text utility 证据

`scripts/build_gate0_text_utility_report.py` 负责在生产 bank 上计算:

- `u_ds_popularity`
- `u_ds_uniform`
- `phi(U_ds)`
- coherence quartile diagnostics

它是当前门控设计的“数据集级定价器”，不是可有可无的分析脚本。

### 4.3 外部 baseline 接线

`scripts/run_close04_diffurec.py` 已经把 DiffuRec 接到了共享协议数据上:

- 直接读 `protocol.json`
- 直接读 `train/val/test_data.df`
- 不走上游原始预处理路径
- 输出统一的 summary 与 manifest

这一步很关键，因为它把“baseline 复现”纳入了和 PreferGrow 相同的 split / selector / artifact 体系。

### 4.4 噪声地板 closeout

`scripts/build_close02_ml1m_noise_floor_report.py` 的作用不是普通汇总，而是回答当前论文最敏感的问题:

- `ML1M` 的红旗差距到底是实现问题，还是宿主 run-to-run noise floor 内的波动?

这决定:

- `main_v2.tex` 中两个剩余关键占位是否能安全回填
- `CLOSE-05` 的 Gate-2 是否还能从 `weak` 升到 `medium-conditional`
- abstract 中那句 close02-sensitive 句子能否冻结

## 5. 真实项目状态

### 5.1 closeout 台账是当前唯一可信状态源

当前主台账是 `issues/2026-07-06_evidence-priced-schedule-and-closeout.csv`。

按 2026-07-09 本地状态:

- `CLOSE-02`: 进行中，初审与回归审查已完成，未提交
- `CLOSE-04`: 初审已完成，回归审查未开始
- `CLOSE-05`: 初审已完成，回归审查未开始
- `CLOSE-06`: 初审已完成，回归审查未开始
- `CLOSE-07`: 进行中，初审与回归审查已完成，未提交

### 5.2 当前真正的 blocker

当前最硬的 blocker 仍然是 `CLOSE-02`。

本地 dated close02 artifact 目录只有:

- `docs/reports/data/2026-07-06-close02-ml1m-noise-floor`
- `docs/reports/data/2026-07-07-close02-ml1m-noise-floor`

尚未看到更新到 2026-07-09 的正式 dated close02 报告目录。

这意味着:

- 可以记录晚到的 operational evidence
- 不能把它冒充为新的 dated authoritative artifact
- 不能升级为 “within noise floor” 强措辞

### 5.3 论文占位剩余状态

`paper/main_v2.tex` 当前扫描结果:

- `\pending{...}` 剩余 2 处: 659, 867
- `\pfig{...}` 剩余 3 处: 277, 429, 731
- `\pnum` 当前为 0

其中 2 处 `\pending` 都依赖 `CLOSE-02`。

### 5.4 PDF 与源码不同步

当前时间戳显示:

- `paper/main_v2.tex`: 2026-07-09 04:30:26
- `paper/main_v2.pdf`: 2026-07-07 20:32:58

因此任何“PDF 已反映最新源码”的说法都不成立。

### 5.5 本地编译现实

本机未检测到:

- `pdflatex`
- `tectonic`
- `xelatex`

所以本地现在只能对源码做诚实审计，不能宣称完成了最新 camera-style PDF 验证。

## 6. 未来 7 天的真实关键路径

### P0

1. `CLOSE-02`
   - 找到或同步新的 dated close02 artifact
   - 决定 ML1M 红旗归因
   - 回填 `main_v2.tex` 的两处核心占位

2. `CLOSE-05`
   - 在 2026-07-14 冻结 Gate-2 结论
   - 默认保持 `weak`
   - 只有 close02 新 artifact 支持时才考虑 `medium-conditional`

3. `CLOSE-06`
   - 抽象句已经几乎冻结
   - 只剩一条 close02-sensitive 句子需要最终拍板
   - 2026-07-18 前必须完成 title/abstract freeze

4. `CLOSE-07`
   - close02 结果落地后做最后的 artifact-driven sync
   - 然后再谈完整 PDF 与 supplementary 打包

### P1

5. `CLOSE-04`
   - DiffuRec 作为 protocol-context baseline 继续推进
   - 但它现在不是正文硬阻塞项

6. `CLOSE-03`
   - Beauty corruption rerun 是条件分支
   - 不应阻塞投稿主路径

## 7. 建议的 48 小时执行顺序

### 第一优先级

- 只盯 `CLOSE-02`
- 确认是否有新的正式 dated artifact 同步到本地
- 如果仍没有，就保持所有文本为 conservative branch

### 第二优先级

- 预先准备 `CLOSE-05` Gate-2 冻结包
- 明确默认出口仍是 `weak`
- 不等待 close02 才开始整理材料

### 第三优先级

- 继续保持 `CLOSE-06` abstract freeze 候选与 `main_v2.tex` 同步
- 防止 close02 外的措辞漂移

### 第四优先级

- 让 `CLOSE-04` 继续跑，但不为它牺牲 close02 的注意力

## 8. 建议阅读顺序

如果要重新接手项目，建议按以下顺序读:

1. `docs/superpowers/specs/2026-07-06-evidence-priced-schedule-design.md`
2. `issues/2026-07-06_evidence-priced-schedule-and-closeout.csv`
3. `docs/reports/2026-07-07-aaai27-handoff-playbook.md`
4. `docs/reports/2026-07-04-family-d-claim-freeze-cn.md`
5. `paper/main_v2.tex`
6. `paper/main_v2_zh.md`
7. `single_train.py`
8. `model/text_side.py`
9. `graph_lib.py`
10. `scripts/build_paper_datasets.py`
11. `scripts/build_gate0_text_utility_report.py`
12. `scripts/build_close02_ml1m_noise_floor_report.py`
13. `scripts/run_close04_diffurec.py`

## 9. 一句话结论

当前项目最重要的事实是:

PreferGrow 的“研究价值”已经从原始 README 的模型宣称，转移为一套围绕 `fallback-safe kernel conditioning`、`U_ds` 定价、和 AAAI closeout 纪律组织起来的证据系统；眼下真正卡住全文冻结的，不是模型代码本身，而是 `CLOSE-02` 是否能提供一个新的、带日期的、可引用的噪声地板工件。
