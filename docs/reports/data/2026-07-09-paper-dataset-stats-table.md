# Paper Dataset Stats Table

Date: `2026-07-09`

This artifact distills the row-level regenerated dataset statistics already archived in:

- `docs/reports/data/2026-07-02-gate0/gate0_failure_component_summary.csv`

It is intended for the paper-level setup table in `paper/main_v2.tex`.

## Table

| dataset | items | train rows | val rows | test rows | total rows |
| --- | ---: | ---: | ---: | ---: | ---: |
| ML1M | 3706 | 755782 | 98622 | 85405 | 939809 |
| Steam | 9265 | 988517 | 81695 | 80651 | 1150863 |
| Beauty | 12101 | 17890 | 2236 | 2237 | 22363 |
| ATG | 11921 | 15529 | 1941 | 1942 | 19412 |

## Note

These are regenerated-protocol row counts and item counts extracted from the archived Gate0 component summary artifact. They are suitable for the paper's setup-side dataset statistics table, but they are not a replacement for the full `paper_raw_v1` sidecar set.
