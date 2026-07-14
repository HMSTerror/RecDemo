## Task Packet

- Scope: create a separate English/Chinese hypothetical-success AAAI manuscript with blank result tables.
- Exclusive output: `paper/hypothetical_success/**`; the active evidence manuscript must not be overwritten.
- Baselines: SASRec, Caser, GRURec, DiffRec, matched PreferGrow and Ours; BERT4Rec extended; DreamRec/PreferDiff/DDSR optional after official-code audit; DiffuRec excluded.
- Required sections: abstract, introduction, related work, method/theory, protocol, main comparison, corruption response, ablation, uncertainty, efficiency, discussion, limitations, conclusion.
- Evidence boundary: no fabricated number, no “results show” assertion, all result cells `--`, prominent scenario watermark, dated-artifact replacement contract.
- Validation: table-row audit, forbidden-baseline audit, placeholder semantics, LaTeX structural/citation scan, English/Chinese scope parity, authored-path diff check.
