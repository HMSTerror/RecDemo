# Capability-use audit

## Required and actual capabilities

- Required: worktree isolation, research-writing orchestration, experiment result planning, statistical scope control, test-driven development, fast-context search, and verification-before-completion.
- Used: all listed capabilities. Fast-context located the production RISK-08 artifact validator and summary schema; TDD established a failing import before implementation and then exercised five release-gate behaviors.

## Inputs consumed

- Gate0/Gate1/E0/E1/E7 dated artifacts.
- r6a compact implementation snapshot.
- r7 queue/protocol/task snapshot and exact production source copies.
- E5 four-domain manifests, results, and exact runner sources.
- Production queue, wrapper, artifact-validator, continuation, selector, and summary code.

## Inputs intentionally not consumed

- Checkpoint binaries: unnecessary for provenance and wording closure.
- Partial r7 metrics: excluded from paper tables because r7 is nonterminal.
- DiffuRec artifacts: excluded from confirmatory comparison by user decision.
- Newly regenerated E7 records: forbidden without a dated protocol amendment.
- GPU state mutation: outside the local fixed-disk scope.

## Produced artifacts

The complete list is maintained in `HANDOFF.md` and the dated directory. The only new executable is `scripts/build_r7_paper_evidence.py`; it writes outside the queue root and emits performance only after the frozen terminal contract passes.

## Verification record

- RED: `python -m pytest tests/test_build_r7_paper_evidence.py ...` failed with `ModuleNotFoundError` before production code existed.
- GREEN: the same focused suite passed 5/5 after implementation.
- Final: focused suite 5/5; continuation/queue regression 87 passed with 1 Windows-inapplicable skip; 52 JSON and 5 CSV files parsed; 70-input inventory regenerated; encoding scan and authored-path `git diff --check` passed. Immutable source snapshots were excluded from the whitespace check because byte preservation is part of their evidence contract. Forbidden-phrase hits occur only in prohibition/disclosure fields or immutable input artifacts.

## Remaining risks

- r7 terminal exit is unknown in the frozen local snapshot.
- All performance evidence remains single seed.
- E5 Beauty has a large validation-to-test decline.
- The method amendment increases manuscript integration work before abstract freeze.
- Final paper figures and AAAI template compilation are not performed by this package.
