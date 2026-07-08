# main\_v2 回填措辞补丁

_面向 `paper/main_v2.tex` 的英文可替换句块草案，基于 2026-07-09 当前 closeout 账本与已落地 artifact；目标是把仍然 claim-sensitive 的位置拆成可安全替换的最小句块_

---

## 📝 TL;DR

- 当前真正还敏感的回填位点只剩两处：`line 659` 的 ML1M / ATG 红灯归因，以及 `line 867` 的 limitations 对应句。
- setup 段的 external baseline 位置已经固定为 “DiffuRec 已选定，若结果窗关闭则显式报缺”，不再属于待替换占位。
- 我把 remaining 位点都拆成两类文案：
  - `default-safe`：在新 dated artifact 未落地前可直接保留
  - `conditional-upgrade`：只有在对应 closeout 行真正闭环后才允许替换

## 📍 适用范围

- 投稿母本：`paper/main_v2.tex`
- 中文镜像：`paper/main_v2_zh.md`
- 关联 closeout 行：
  - `CLOSE-02`
  - `CLOSE-05`
  - `CLOSE-07`

## ✅ 已完成位点：Setup 段 external baseline

当前 setup 段已经不再是空占位。

主稿现状：

- `DiffuRec` 被固定为选定的 single external baseline
- 如果四数据集 dated 结果表未落地，则显式报缺
- 不再出现 “DiffuRec 或 RecFormer 二选一” 这种未定口径

因此，baseline 这部分现在不再需要句块补丁，只需要等正式结果表或 documented-gap 收口。

## 🎯 位点 1：Validation 段 ML1M / ATG 红灯归因

**当前位置**

- `paper/main_v2.tex:657-662`

### `default-safe`

适用于 `CLOSE-02` 仍只有账本备注、没有新的 dated noise-floor artifact 时：

```text
We therefore treat the ML1M/ATG misses as an implementation red flag under investigation, with host run-to-run noise still awaiting a dated CLOSE-02 artifact, and we pause any claim that the exact reduction has been empirically demonstrated end-to-end.
```

### `conditional-upgrade`

适用于 `CLOSE-02` 给出 dated artifact，且结论支持 “within host noise floor” 时：

```text
We therefore read the ML1M/ATG misses against the measured host run-to-run noise floor: the dated CLOSE-02 artifact shows that deviations of this order are within the host's own stopping-time variance envelope, so we treat them as within-noise rather than as evidence against the reduction property.
```

### `conditional-negative`

适用于 `CLOSE-02` 给出 dated artifact，但结论支持 “outside noise / implementation issue” 时：

```text
We therefore treat the ML1M/ATG misses as remaining outside the currently measured host noise floor and keep them as an implementation red flag rather than as evidence in either direction about the reduction theorem itself.
```

### 写作约束

- `default-safe` 是当前唯一可以无风险保留在主稿里的版本。
- 只有 `CLOSE-02` 出现 dated artifact 后，才允许在 `conditional-upgrade` 和 `conditional-negative` 之间二选一。

## 🎯 位点 2：Limitations 段的对应红灯句

**当前位置**

- `paper/main_v2.tex:865-868`

### `default-safe`

```text
The frozen-gate validation returned a mixed verdict: the opened gate kept its sign but not its reference magnitude, one pre-registered out-of-sample prediction missed outright, and two closed-gate parity checks missed by margins whose attribution still awaits a dated host-noise-floor readout from CLOSE-02.
```

### `conditional-upgrade`

```text
The frozen-gate validation returned a mixed verdict: the opened gate kept its sign but not its reference magnitude, one pre-registered out-of-sample prediction missed outright, and two closed-gate parity checks missed by margins that the dated CLOSE-02 artifact places within the host's own run-to-run variance envelope.
```

### `conditional-negative`

```text
The frozen-gate validation returned a mixed verdict: the opened gate kept its sign but not its reference magnitude, one pre-registered out-of-sample prediction missed outright, and two closed-gate parity checks missed by margins that remain outside the currently measured host-noise-floor envelope.
```

## 🎯 位点 3：Gate-2 冻结时的最终升级句

**位置**

- `paper/main_v2.tex:668-671` 的注释区当前保留了 upgrade-only 位置

### 仅当 `CLOSE-02` 支持 upgrade 且 `CLOSE-05` 允许时使用

```text
Closed-gate runs are empirically indistinguishable from the host within the measured host noise floor, as the reduction theorem predicts.
```

### 如果 `CLOSE-05` 仍冻结为 weak

不要把这句话提到正文；保留在 comment / drafting memo 层即可。

## 📊 使用规则

| closeout 行 | 当前状态 | 可升级对象 | 禁止行为 |
| --- | --- | --- | --- |
| `CLOSE-02` | 仍用 `default-safe` | `conditional-upgrade` 或 `conditional-negative` | 没有 dated artifact 就写 “within noise” |
| `CLOSE-04` | setup 句已固定 | 只剩结果表能否进入正文/表格 | 没有结果表就写 baseline 已完成四数据集对照 |
| `CLOSE-05` | 保留弱口径 | 允许启用 upgrade-only 句 | 在 Gate-2 前偷改最终 claim |

## ✅ 推荐执行顺序

1. 保留当前已经固定的 external baseline setup 句，不再回滚成占位。
2. 等 `CLOSE-02` 出 dated artifact 后，只替换位点 1 和位点 2，不动其他段落结构。
3. 只有 `CLOSE-05` 真正冻结后，才判断 upgrade-only 句能否进入正文。

## 🔆 结论

当前真正值得提前准备的不是“大改稿”，而是剩余这两组三小块英文句子。只要它们先拆好，后面的 closeout 就会变成“替换哪一句”的问题，而不是“到 deadline 前临场重写整段论证”的问题。
