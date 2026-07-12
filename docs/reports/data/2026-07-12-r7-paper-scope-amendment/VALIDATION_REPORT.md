# P0-6 paper-scope integration validation report

Date: 2026-07-12 (Asia/Shanghai)

Validation scope: English/Chinese claim synchronization, SASRec citation and table integration, r7 runbook/deadline gates, LaTeX fallback build, and claim/evidence regression scans. This report does not validate an r7 performance result and does not close P0-5.

## 1. Citation and structure checks

A fresh static audit of `paper/main_v2.tex` and `paper/references.bib` returned:

| Check | Result |
|---|---:|
| unique cited keys | 23 |
| BibTeX keys | 24 |
| missing citation keys | 0 |
| duplicate BibTeX keys | 0 |
| unique labels | 49 |
| duplicate labels | 0 |
| missing reference labels | 0 |
| `begin` / `end` count | 50 / 50 |
| environment multiset match | true |
| `sasrec` present and cited | true / true |

Crossref verified DOI `10.1109/ICDM.2018.00035` as Wang-Cheng Kang and Julian McAuley, *Self-Attentive Sequential Recommendation*, ICDM 2018, pp. 197--206. The BibTeX entry contains those fields; Tectonic generated `\bibitem{sasrec}` and `\bibcite{sasrec}{12}`.

## 2. Fresh fallback LaTeX build

No TeX engine was initially present locally or on l20. A temporary, non-repository conda environment installed Tectonic `0.15.0`, after which the manuscript was built twice from `paper/` into:

~~~text
C:\Users\14466\AppData\Local\Temp\prefergrow-paper-build-20260712-p06-r2
~~~

Both fresh invocations returned exit code `0` and produced:

| Artifact | SHA-256 |
|---|---|
| `main_v2.pdf` | `4918D53673D03146367355A1C18911941F9F129895F49D2E0F9A549A6EC8A612` |
| `main_v2.log` | `53A06D38DE96F1DE491FB5FE4598D89C416DD2771C2BEC52C9041A0E26617FF3` |
| `main_v2.bbl` | `A52ACBB1F4DB883867B2D17305BA58C315488E43C719247845FF583C600A6EC2` |

The log contains no undefined citation, undefined reference, error, or overfull box. The first build exposed a 41.68 pt overfull TV formula; the formula was split and the second build removed that warning.

Remaining fallback-only warnings are explicit:

- Times/Courier font shapes are unavailable under the fallback XeTeX bundle, so substitutes are used;
- one underfull bibliography paragraph at `main_v2.bbl:9--13` comes from a long existing author entry;
- Tectonic reports an internal bbl consistency/rerun warning and stops after six passes even though repeated builds exit `0`, produce the same-sized PDF, and contain no undefined citations/references.

The repository does not contain `aaai27.sty` or `aaai27.bst`. This build therefore validates fallback article-mode syntax and bibliography resolution only. It does **not** establish AAAI-27 page count, official fonts, spacing, anonymity format, or camera/submission-style compliance.

## 3. Claim-boundary checks

Required positive probes were read in context and found:

- generalized gate `g=g_max s_D clip(u_tilde,0,1)` at `paper/main_v2.tex:96`, `:187`, `:306`, and `:419`;
- verified SASRec citation at `paper/main_v2.tex:654`;
- corrected-evaluator three-of-four disclosure, increasing-in-EPE `phi_R` disclosure, Beauty test-only caption, E7 zero executed bootstrap, development-time test logging, DiffuRec confirmatory exclusion, Chinese mirrors, and 7/16/7/18/submission-stop runbook gates.

An initial PowerShell `SimpleMatch` probe over-escaped the generalized-gate and citation strings and returned two false negatives. Corrected fixed-string `rg` probes found the exact lines above; those corrected outputs, the citation/label parser, and the successful BibTeX build are the acceptance evidence.

The manuscript-only forbidden-claim scan returned no hits for:

~~~text
significant | stable | statistically equivalent | within noise
u_tilde ... collapse | adaptive backoff | in all four cases
DiffuRec ... baseline
~~~

The r7-result scan found only one Chinese sentence that explicitly prohibits filling r7 performance/PASS before the immutable RISK-08 artifact. Runbook hits for the forbidden terms occur only in prohibition/withdrawal rules, not in result claims. Unconditional `4/4` wording is absent: every surviving 4/4 instance is explicitly archived/legacy and paired with corrected 3/4 arbitration.

`git diff --check` returned exit `0`; its only output was the configured Windows LF-to-CRLF warning, with no whitespace error.

## 4. P0-6 acceptance matrix

| Requirement | Evidence | Result |
|---|---|---|
| Distinguish `U_ds`, EPE/PNE@10, and `phi_R` | English method/abstract, Chinese mirror, evidence map | pass |
| Disclose frozen `phi_R` sign | method equation/algebra plus limitations in both languages | pass |
| c100 is explicit scale-zero fallback | val/test table, caption, best-summary/checkpoint boundary | pass |
| Beauty val/test co-located | r6a table and mandatory disclosure | pass |
| SASRec four-domain baseline and Beauty anomaly | cited English table and Chinese table | pass |
| DiffuRec absent from confirmatory comparison | setup exclusion; related work retained | pass |
| Validation-only selection and development test logging | setup, caption, reproducibility, Chinese/runbook | pass |
| Every seed-100 result scoped as one run | captions, contributions, runbook prohibition | pass |
| 7/16, 7/18, and submission-stop rules mechanical | freeze candidate and runbook branch tables | pass |
| No unfinished r7 result inserted | manuscript exclusion plus fresh remote status | pass |

## 5. Fresh server boundary at validation time

The detached controller remained live at PID `3277670`, `stop_requested=false`, with queue counts `14 ready / 8 inactive pending / 0 running / 0 passed / 0 failed`, no records, no RISK-08 exit, and `actual_gpu_hours=0.0`. GPU0 and GPU1 were still occupied by root PIDs `2987761` and `3072363`; no r7 child existed. Free disk was `76.145 GiB`. Therefore P0-5 remains `waiting_external_gpu` and cannot be closed by this report.

## 6. Remaining submission risks outside P0-6

- Three real figures are still represented by `\pfig{...}` at `paper/main_v2.tex:301`, `:489`, and `:921`.
- Official AAAI-27 style/page-count validation remains pending the author kit.
- r7 has no training result or RISK-08 exit yet.
- E7 user-level uncertainty remains not estimable without a separately authorized protocol amendment.

These gaps prevent a claim that the full AAAI submission is finished, but they do not invalidate the narrower P0-6 paper-scope amendment.
