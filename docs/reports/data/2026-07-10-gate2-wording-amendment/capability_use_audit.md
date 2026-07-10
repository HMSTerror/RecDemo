# Capability-use audit: Gate-2 wording amendment

## Required and used capabilities

The task packet required `using-research-writing`, `paper-orchestration`, `writing-core`, `latex-output`, and `verification`. All five were read and used. The repository's fast-context MCP search was used before document and code exploration. The active mission ledger remained the execution boundary.

No literature search, statistical recomputation, image generation, or new experiment was needed. The amendment consumes only already archived evidence and the completed E1/CLOSE-10 closeout artifacts.

## Inputs consumed

- E0 corrected evaluator amendment, including unchanged gate decisions and DiffuRec scope
- E1 production-path hard-stop report and source trace
- E7 bootstrap evidence hard stop
- CLOSE-02 ML1M host-floor report
- CLOSE-10 provenance-limited ATG observed-spread report and raw source archive
- English and Chinese paper sources at repository HEAD `d110a33`
- User-approved wording, frozen-number, single-run, and no-launch constraints

## Outputs

- Applied English revision: `paper/main_v2.tex`
- Applied Chinese mirror revision: `paper/main_v2_zh.md`
- Executed amendment memo and task packet
- Actual replay-oriented patch built from the current paper diff
- Machine-readable claim-family inventory
- Provenance manifest and package checksums
- Persistent planning packet and progress record

## Spec-compliance review

The review checked the requested claim families against both manuscript files. The TV statement is limited to proposal and one-step transition-row kernels. The `1/24` statement is descriptive under exchangeability. ATG is identified as barely-open at `phi=0.117`. DiffuRec is limited to corrected-test evaluator comparability. The development-time test-logging disclosure is present. E1 and CLOSE-10 limitations appear in the abstract, experiment interpretation, and limitations. Final-v2 corruption-response evidence is not claimed because E3 did not launch.

A structured comparison against repository HEAD found all four frozen Table 2 metric rows unchanged in English and Chinese. The ATG interpretation label changed, but its numeric cells and rounded `0.12` display did not.

## Quality review

The paper diff was converted into 20 English and 7 Chinese replay blocks. Every old block was found in the HEAD version and every new block was found in the edited version. Claim scans found no inferential/equivalence noise-band upgrade wording. English and Chinese required-phrase checks both passed. Basic LaTeX validation found balanced braces and matched abstract, itemize, figure, table, tabular, proposition, and lemma environments.

The research-writing style checker exited successfully for the Chinese paper and the amendment memo. It reported existing deliberate bold markers, theorem lists, and table-line spacing for manual review; it found no banned transition phrases, subjective first-person phrasing, or leaked process instructions.

## Validation limitation

No local `tectonic`, `pdflatex`, `xelatex`, or `latexmk` executable is available, and the AAAI style files are not present. The revision therefore has structural LaTeX verification but not a fresh compiled PDF. No remote compilation was attempted because this sprint's server operations are read-only.

## Remaining risks

- The ATG comparison remains provenance-limited because all three run manifests are absent.
- E1's step-0 optimizer-ownership divergence prevents an end-to-end exact-reduction claim and blocks E2/E3/E4/E5/E8 launches in this sprint.
- Camera-style page count and layout remain unverified until the AAAI author kit and a LaTeX engine are available.

