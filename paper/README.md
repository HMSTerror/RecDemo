# AAAI-27 论文草稿

- `main.tex` — 正文 + 附录(命题 1–6 与 TV 引理完整证明)。所有依赖实验的数字/图用红色 `\pending{...}` / `\pnum` / `\pfig{...}` 标出;**只允许用 `docs/reports/data/` 下带日期的 artifact 回填**(对应 issues CSV 的 SPRINT-13,回填时在 tex 注释里引用 artifact 文件名)。
- `references.bib` — 标注 `%% VERIFY` 的条目元数据未完全确认,投稿前必须逐条对 arXiv/DBLP 核实,严禁保留 TODO 作者字段。

## 编译

1. 下载 AAAI-27 author kit,把 `aaai27.sty`(和 `aaai27.bst`)放到本目录。缺 kit 时 `main.tex` 会退回普通双栏近似排版,仍可编译预览。
2. `pdflatex main && bibtex main && pdflatex main && pdflatex main`
3. 缺 kit 时把文末 `\bibliographystyle{aaai27}` 换成注释里的 `plain`。

## 写作纪律(冻结自 sprint spec §8.1,2026-07-04 重写版)

- 当前正文是 **Family D 基线档位**:安全性定理 + 效用反转分析(表 1,真实数字已填)+ 机制证据链 + 诚实边界。
- SPRINT-05 验证跑四条预测全中时,才允许按 `main.tex` 中标注 `GATE-2 UPGRADE` 的注释升级措辞(有记录修订,只升不降)。
- 已填数字均在 tex 注释中引用了 `docs/reports/data/` 带日期产物;剩余 34 个 `\pending` 只可用同类产物回填。
- 禁写:consistent gains across all datasets / uniform superiority / metadata sparsity 作正证据(负结果已如实写进附录 E)。
- 第一代(v1)数字只作为机制证据与失败模式呈现,归属已在附录 D 说明,不得当成最终系统的 benchmark。
