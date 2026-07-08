# main\_v2 回归措辞审计

_日期：2026-07-09_
_用途：审计当前 `paper/main_v2.tex` 源文件与已编译 `paper/main_v2.pdf` 是否仍符合 Family D 禁写边界和当前 Gate-2 弱口径；服务 `CLOSE-07` 的回归审查_

---

## 📝 一句话结论

截至 2026-07-09，去掉 LaTeX 注释后的最新 `paper/main_v2.tex` 未出现 Family D 冻结备忘录中的禁写短语；当前可读的 fallback `paper/main_v2.pdf` 仍能检出 `weak-default` 所需的关键边界短语。需要诚实说明的是：PDF 的时间戳早于最近几次 source 回填，因此本审计证明的是“最新 source 边界安全 + 现有 fallback PDF 仍在弱口径轨道内”，而不是“最新 source 已重新编译为最新 PDF”。

## 📍 审计对象

- 源文件：`paper/main_v2.tex`
- 已编译 PDF：`paper/main_v2.pdf`
- 冻结边界：`docs/reports/2026-07-04-family-d-claim-freeze-cn.md`
- 当前 Gate-2 证据包：`docs/reports/2026-07-09-gate2-evidence-packet-cn.md`

## 🕒 时间戳现实

本轮 fresh 取证结果：

- `paper/main_v2.tex`: `2026-07-09 04:03:51`
- `paper/main_v2.pdf`: `2026-07-07 20:32:58`

因此：

- source 层审计覆盖的是**最新**主稿
- PDF 层审计覆盖的是**旧于当前 source 的 fallback 编译产物**

## 🔍 审计方法

### Source 层

- 读取 `paper/main_v2.tex`
- 先剔除以 `%` 开头的注释行
- 再扫描 Family D freeze memo 明确禁止的英文短语

### PDF 层

- 使用 `pypdf` 读取 `paper/main_v2.pdf`
- 对以下边界短语做宽松匹配：
  - `margins comparable to run-to-run noise`
  - `open implementation question`
  - `safety, not improvement`

## 🚫 禁写短语扫描结果

下列短语在**去掉注释后的源文件**中均未出现：

| 短语 | Source（去注释后） |
| --- | --- |
| `consistent gains across all datasets` | `False` |
| `uniform superiority` | `False` |
| `kernel consistently outperforms encoder and loss injection` | `False` |
| `first multimodal` | `False` |
| `first uncertainty-aware` | `False` |
| `first trustworthy` | `False` |
| `nearly closes the gap` | `False` |
| `within the measured host noise floor` | `False` |

说明：

- 源文件里确实还有 `within the measured host noise floor` 的**注释**，用于 upgrade-only 提示。
- 但正文 source 在去掉注释后没有这类升级措辞。

## ✅ 当前弱口径短语检出结果

在当前可读的 `paper/main_v2.pdf` 中，下面这些关键短语都能检出：

| 短语 | PDF 检出 |
| --- | --- |
| `margins comparable to run-to-run noise` | `True` |
| `open implementation question` | `True` |
| `safety, not improvement` | `True` |

这说明当前已编译 fallback PDF 至少仍然处于 `weak-default` 叙事轨道内；但由于 PDF 旧于最新 source，它不能单独证明最新 `.tex` 已被重新编译。

## ⚠ 本审计的边界

这份审计**不**证明：

1. camera-style AAAI 版式 PDF 已通过同样检查
2. `CLOSE-02` 已经支持 within-noise 升级
3. `CLOSE-05` 的最终出口已经冻结

因此它只能支持下面这个更精确的判断：

> 当前最新 source 的文案边界是安全的，而现有 fallback PDF 也仍处于 `weak-default` 轨道内；但在 source 再次编译为最新 PDF 之前，以及在 camera-style PDF 可编译之后，仍需各补一次最终回归检查。

## 📦 对 `CLOSE-07` 的意义

这份审计可以支撑：

- `review_regression_state` 在**受限验证**前提下推进

前提是账本中如实注明：

- `validation_limited:camera-style pdf not yet available locally; current fallback pdf predates latest source edits`

而不能支撑：

- full paper 已完全通过最终回归

## 🔆 结论

当前 closeout 的真正风险已经不在“稿子会不会偷偷越界”，而在“剩余 artifact-sensitive 占位什么时候落地”与“camera-style PDF 什么时候能做最终检查”。这意味着 `CLOSE-07` 的回归风险可以被更精确地表述成：**文本边界已过、版式边界待补。**
