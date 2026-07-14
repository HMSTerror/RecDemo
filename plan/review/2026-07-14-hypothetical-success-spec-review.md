# Hypothetical-success paper spec review

## Verdict

Pass. The package is physically and semantically separate from the active evidence manuscript. It contains the requested complete paper story, the approved original-paper-aligned baseline block, and blank tables for every result family.

## Checks

- Core baselines complete: SASRec, Caser, GRURec, DiffRec, PreferGrow host, Ours.
- Extended baseline present: BERT4Rec.
- Optional official-code block separated: DreamRec, PreferDiff, DDSR.
- DiffuRec absent from the confirmatory table.
- Main, corruption, ablation, uncertainty, efficiency and evaluator tables use `--`/`\blankcell` only.
- Scenario watermark states that blank is not zero and real dated artifacts are required.
- Theory remains kernel-scoped; c100 remains explicit phi_R=0 sanity evidence.
