# AAAI submission build

## Current local state

- Entry point: `aaai_submission.tex`.
- Manuscript: `main_v2.tex`.
- Bibliography: `references.bib`.
- Official `aaai27.sty`/`aaai27.bst`: not present locally on 2026-07-14.
- Local `pdflatex`, `latexmk`, and `tectonic`: not present.

The manuscript contains a plain two-column fallback solely for structural checking. A fallback PDF is not evidence of AAAI format compliance and its page count must not be used for the submission decision.

## Required author-kit build

Place the official, current AAAI-27 `aaai27.sty` and bibliography style beside `main_v2.tex`, then run:

```bash
pdflatex -halt-on-error aaai_submission.tex
bibtex aaai_submission
pdflatex -halt-on-error aaai_submission.tex
pdflatex -halt-on-error aaai_submission.tex
```

Before submission verify anonymization, page limit, reference allowance, supplementary policy, all figure paths, and that no conditional RISK-08 result file is included without the matching immutable marker. The official author kit remains the source of truth; this repository does not manufacture a replacement style file.
