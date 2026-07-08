# AAAI-27 论文概念图生图提示词(2026-07-08)

- 对应图位:`paper/main_v2.tex` 中 `fig:method`(§3 开头)与 `fig:inversion`(§4 开头),caption 已写好,生成后用 `\includegraphics[width=\linewidth]{...}` 替换 `\pfig` 占位框即可
- 尺寸要求:单栏宽(AAAI 双栏,约 3.3 in / 1000px 以上),**300 DPI 起**,白底,PNG 或 PDF
- 推荐工具:Nano Banana(学术图表)首选,DALL-E 3 备选
- ⚠️ camera-ready 建议:生图 AI 的数学符号渲染不可靠,生成结果**作为布局初稿**;定稿前最好照着它在 draw.io / PowerPoint / TikZ 里矢量重绘一遍,保证 $g_{\max}\phi(U_{ds})\tilde{u}$ 这类记号逐字正确。所有标签用英文。

---

## 图 1(fig:method)· 方法总览

```
Draw an academic-paper-quality method overview diagram, flat vector style,
white background, clean sans-serif English labels, no photorealism, no 3D.

[Overall layout] Left to right, three stages connected by arrows.

[Stage 1, left, blue rounded boxes (#457B9D)]
- Box "User history h = (i1, ..., iL)" with 4-5 small item icons in a row.
- Below it a cylinder "Frozen text bank (encoder never fine-tuned)".
- Two thin arrows from these into Stage 2.

[Stage 2, middle, two stacked orange rounded boxes (#F18F01), bold borders]
- Upper box "Content anchor c_h : softmax of text similarity to history mean".
- Lower box "Two-factor gate  g = g_max * phi(U_ds) * clip(u~, 0, 1)" with two
  small input tags attached:
  tag A (light blue) "u~ : per-user coherence, calibrated against a
  length-matched random-history null";
  tag B (light blue) "phi(U_ds) : frozen dataset-level utility hinge,
  train-only".

[Stage 3, right, one large box showing the kernel mixing]
- A horizontal interpolation bar: left end labeled "host proposal p_core
  (learned)", right end labeled "text anchor c_h (frozen)", a slider at
  position g labeled "(1-g) p_core + g c_h".
- From this bar an arrow down to a green rounded box (#59A14F)
  "Personalized corruption kernel p_u : forward fading, score-entropy
  weights, analytic reversal".

[Safety callouts, bottom, two red-dashed outline boxes (#E63946), white fill]
- "g = 0  =>  kernel EXACTLY equals the host (fallback safety)"
- "any g :  TV(p_u, p_core) <= g  (bounded deviation)"
Connect both callouts to the Stage-3 box with thin dashed red arrows.

[Style] Rounded rectangles, 2px outlines, generous white space, arrowheads
filled, all text horizontal and legible at single-column width, no emojis,
no gradients, no shadows.
```

## 图 2(fig:inversion)· 反转机制(为什么证据太好反而有害)

```
Draw an academic-paper-quality two-panel conceptual diagram, flat vector
style, white background, clean sans-serif English labels, no photorealism.

[Overall layout] Two side-by-side panels of equal width separated by a thin
vertical divider, plus a narrow bottom strip.

[Left panel, green theme (#59A14F), header "Low U_ds : text does NOT predict
the next item  ->  tilt helps"]
- Center: a user's preferred item as a filled blue circle labeled "preferred
  item".
- Around it: 5-6 gray circles labeled "text neighbors = hard negatives".
- The user's TRUE next item drawn as a blue star placed FAR from the
  neighbor cluster, labeled "true next item (far in text space)".
- A wide green arrow from the preferred item toward the gray cluster labeled
  "corruption fades toward text anchor"; small caption under the panel:
  "corruption lands on informative hard negatives".

[Right panel, red theme (#E63946), header "High U_ds : text DOES predict the
next item  ->  tilt hurts"]
- Same preferred-item circle and gray neighbors, but the blue star "true
  next item" sits INSIDE the text-neighbor cluster, close to the center.
- The same wide arrow now colored red, labeled "corruption fades toward text
  anchor"; the arrowhead overlaps the blue star with a small collision burst
  mark; caption: "corruption lands on likely future positives = manufactured
  false negatives".

[Bottom strip, spanning both panels]
- A horizontal axis labeled "U_ds (train-only text utility)" from 0.5 to 0.8
  with a hinge curve phi(U_ds): flat at 1 until 0.60, sloping down to 0 at
  0.70, flat at 0 after; label "frozen hinge phi closes the gate exactly in
  the harmful regime".
- Mark four ticks on the axis: Steam 0.570, ATG 0.688, Beauty 0.712,
  ML1M 0.754 (small labels).

[Style] Rounded shapes, 2px outlines, no gradients, no shadows, all text
horizontal, sized to stay legible at single-column width.
```

---

## 使用流程

1. 把提示词整段贴给生图工具,生成 2-3 个变体挑布局最清晰的;
2. 检查数学记号(g_max、phi(U_ds)、u~、TV ≤ g、p_core、c_h)是否逐字正确——不对就矢量工具里改;
3. 导出单栏宽 300+ DPI PNG/PDF,放 `paper/figures/`,在 tex 里替换对应 `\pfig` 框(caption/label 已就位,不用动);
4. 图 2 底部的铰链曲线与四个数据集刻度也可以改用 `figures-python`/matplotlib 精确绘制后拼接,数字必须与 Table 1 冻结值一致(0.570/0.688/0.712/0.754)。
