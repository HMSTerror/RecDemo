# Spec compliance review — AAAI local integration

## Verdict

Conditional pass. The manuscript, tables, conditional exits, supplement, figures, build note, and read-only synchronizer exist. No partial r7 metric was inserted.

## Checks

- Three-layer U_ds/EPE/phi_R account: present in English and Chinese.
- Strict 4/4 claim: removed from the active English/Chinese claim text.
- c100 adaptive-collapse claim: absent.
- SASRec: four domains, validation/test jointly reported, adapted common-contract label present.
- DiffuRec: excluded from confirmatory comparison; retained only in related work/archive wording.
- Figures: method and mechanism placeholders replaced by editable TikZ; phi_R PDF/PNG generated from the frozen six-row CSV.
- Conditional exits: external files exist and are not included by the active manuscript.
- AAAI build: official style and TeX engine absence documented; no replacement style fabricated.
- Synchronizer: remote operations are ssh/scp reads and local writes only.

## Open compliance item

The terminal synchronizer still delegates to the production artifact validator, whose clean-null path check refers to the original Linux absolute path. A Windows terminal snapshot will therefore fail closed until external null-curve provenance is copied and path-mapped. Nonterminal status synchronization is usable; terminal paper release remains intentionally blocked rather than weakened.
