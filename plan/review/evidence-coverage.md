# Evidence-coverage review: r7 paper-scope integration

Status after manuscript synchronization: claim-level edit complete; compile and final hash validation pending.

| Required claim boundary | Evidence ID | Required location | Coverage and exact references | Status |
|---|---|---|---|---|
| `U_ds` is legacy discovery, not the r7 intervention | EV-U1, EV-R3, EV-R5 | Abstract, Introduction, Method | General `s_D` and three generations: `paper/main_v2.tex:89`, `paper/main_v2.tex:193`, `paper/main_v2.tex:365`; Chinese mirror: `paper/main_v2_zh.md:8`, `paper/main_v2_zh.md:36` | covered |
| Corrected evaluator does not support unconditional 4/4 wording | EV-E0 | Abstract, Table 1 caption, limitations | Archived-scale 4/4 plus corrected 3/4 adjacent swap: `paper/main_v2.tex:89`, `paper/main_v2.tex:527`, `paper/main_v2.tex:1050`; Chinese: `paper/main_v2_zh.md:18`, `paper/main_v2_zh.md:64` | covered |
| EPE/PNE@10 is observed next-positive exposure proxy | EV-R3 | Method, experiment context | Definition/boundary: `paper/main_v2.tex:383`; six-point table: `paper/main_v2.tex:805`; Chinese: `paper/main_v2_zh.md:38`, `paper/main_v2_zh.md:102` | covered |
| `phi_R` sign inconsistency is disclosed | EV-R5 | Method amendment, limitations | Increasing-in-EPE algebra and evidence-retention scope: `paper/main_v2.tex:405`, `paper/main_v2.tex:1072`; Chinese: `paper/main_v2_zh.md:40`, `paper/main_v2_zh.md:148` | covered |
| c100 is explicit `phi_R=0` | EV-R6A | Controlled pilot, caption, limitations | Same val/test table and best-summary/checkpoint boundary: `paper/main_v2.tex:824`, `paper/main_v2.tex:847`; Chinese: `paper/main_v2_zh.md:117`, `paper/main_v2_zh.md:128` | covered |
| Beauty gain is test-only | EV-R6A, EV-TEST | Same results table and caption | Validation/test co-located and selector/test disclosure: `paper/main_v2.tex:824`, `paper/main_v2.tex:837`; Chinese: `paper/main_v2_zh.md:117`, `paper/main_v2_zh.md:128` | covered |
| SASRec is the external confirmatory baseline | EV-E5, EV-SAS-LIT | Setup and results table | Verified citation, four-domain table, anomaly: `paper/main_v2.tex:654`, `paper/main_v2.tex:700`; Chinese: `paper/main_v2_zh.md:78`, `paper/main_v2_zh.md:80` | covered |
| DiffuRec excluded from confirmatory comparison | EV-E0 plus user decision | Setup | Related-work/evaluator-provenance only: `paper/main_v2.tex:656`; Chinese: `paper/main_v2_zh.md:78` | covered |
| E7 actual bootstrap count is zero | EV-E7 | Limitations/reproducibility | `paper/main_v2.tex:808`, `paper/main_v2.tex:1289`; Chinese: `paper/main_v2_zh.md:113`, `paper/main_v2_zh.md:148` | covered |
| r7 metrics are unfinished | EV-R7P, EV-R7L | Runbook/reproducibility only | No r7 result in manuscript; explicit exclusion: `paper/main_v2.tex:857`; run state/terminal rule: `docs/runbooks/2026-07-11-e1-pass-risk04-08-experiment-manual.md:392`, `docs/runbooks/2026-07-11-e1-pass-risk04-08-experiment-manual.md:410` | covered |
| Deadline downgrade is mechanical | approved design | Runbook/freeze candidate | `docs/runbooks/2026-07-11-e1-pass-risk04-08-experiment-manual.md:421`; `docs/reports/2026-07-09-abstract-freeze-candidate-cn.md:48` | covered |

The exact references above were read in context, not accepted from keyword hits alone. Final acceptance still requires compile/static validation and an affected-file hash manifest.
