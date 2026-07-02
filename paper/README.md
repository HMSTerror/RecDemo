# AAAI-27 论文草稿

- `main.tex` — 正文 + 附录(命题 1–6 与 TV 引理完整证明)。所有依赖实验的数字/图用红色 `\pending{...}` / `\pnum` / `\pfig{...}` 标出;**只允许用 `docs/reports/data/` 下带日期的 artifact 回填**(对应 issues CSV 的 SPRINT-13,回填时在 tex 注释里引用 artifact 文件名)。
- `references.bib` — 标注 `%% VERIFY` 的条目元数据未完全确认,投稿前必须逐条对 arXiv/DBLP 核实,严禁保留 TODO 作者字段。

## 编译

1. 下载 AAAI-27 author kit,把 `aaai27.sty`(和 `aaai27.bst`)放到本目录。缺 kit 时 `main.tex` 会退回普通双栏近似排版,仍可编译预览。
2. `pdflatex main && bibtex main && pdflatex main && pdflatex main`
3. 缺 kit 时把文末 `\bibliographystyle{aaai27}` 换成注释里的 `plain`。

## 写作纪律(冻结自 sprint spec §4.6)

- Gate 2 出口决定摘要/贡献的措辞档位;medium/weak 出口的降级写法已写在 `main.tex` 相应位置的注释里。
- 禁写:consistent gains across all datasets / uniform superiority / metadata sparsity 作正证据。
- ML1M 的角色是 parity 预测的实证,不是"差一点追平"。
