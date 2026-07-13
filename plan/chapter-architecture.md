# AAAI-27 manuscript integration architecture

This task does not redraft the full paper. It prepares evidence-bounded amendments and integration
packets for the existing English and Chinese manuscripts.

## Required integration targets

- `paper/main_v2.tex` | role: authoritative English manuscript | direct editing deferred until the
  dated Gate-2 amendment passes both reviews | planning placeholders forbidden.
- `paper/main_v2_zh.md` | role: synchronized Chinese manuscript | direct editing deferred until the
  same amendment passes both reviews | planning placeholders forbidden.
- `docs/reports/data/2026-07-13-aaai-local-fixed-disk/` | role: authoritative dated evidence,
  schemas, amendments, reviews, and handoff | `NA` plus reason allowed; invented values forbidden.

## Argument chain to preserve

1. U_ds is a train-only discovery statistic, not a universal predictor.
2. EPE is the primary observed next-positive exposure proxy; PNE@10 is a mechanism/sensitivity
   readout.
3. The r6a/r7 intervention uses frozen condition-level `phi_R`, not the legacy U_ds hinge alone.
4. The only nonzero user factor is history-only, null-calibrated coherence.
5. Exact fallback and TV claims are kernel-scoped; empirical performance is separately measured.
6. Single-seed outcomes remain observations, with validation and test shown together.
