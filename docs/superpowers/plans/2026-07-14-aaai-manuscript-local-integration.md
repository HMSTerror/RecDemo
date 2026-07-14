# AAAI Manuscript Local Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a locally verifiable AAAI manuscript package whose only blocked empirical component is terminal r7 evidence.

**Architecture:** Evidence-constrained manuscript edits consume the dated amendment and claim map. Figures and tables consume immutable CSV/JSON sources. A read-only synchronizer copies terminal evidence into a new dated directory and delegates publication authorization to the existing fail-closed builder.

**Tech Stack:** LaTeX, Markdown, Python, PowerShell, pytest, Git.

---

### Task 1: Freeze integration controls

**Files:**
- Modify: `plan/progress.md`
- Create: `plan/task-packets/2026-07-14-aaai-manuscript-local-integration.md`

- [ ] Record S2/S3/S4/S5 stages and the user-approved L9--L16 scope.
- [ ] List immutable inputs, editable files, rejection checks, and verification commands.
- [ ] Confirm the worktree branch is `codex/aaai-local-fixed-disk` and r7 remains read-only.

### Task 2: Integrate the evidence amendment

**Files:**
- Modify: `paper/main_v2.tex`
- Modify: `paper/main_v2_zh.md`

- [ ] Replace strict `4/4` language with endpoint-plus-adjacent-swap language.
- [ ] Introduce the `U_ds` discovery → EPE measurement → `phi_R` intervention distinction.
- [ ] Replace the c100 collapse interpretation with explicit `phi_R=0` sanity-check wording.
- [ ] Update E1 from the obsolete hard-stop-only account to the scoped R12 2,986/0 account while retaining the historical failure.
- [ ] Retain kernel/one-step theory boundaries and test-logging disclosure.

### Task 3: Integrate evaluator and SASRec tables

**Files:**
- Modify: `paper/main_v2.tex`
- Modify: `paper/main_v2_zh.md`
- Read: `docs/reports/data/2026-07-13-aaai-local-fixed-disk/table1_evaluator_arbitration.csv`
- Read: `docs/reports/data/2026-07-13-aaai-local-fixed-disk/sasrec_four_domain_source.csv`

- [ ] Add legacy/corrected evaluator arbitration with all four domains.
- [ ] Replace DiffuRec confirmatory setup with adapted common-contract SASRec.
- [ ] Report SASRec four-domain test NDCG@10 atomically and Beauty validation/test jointly.
- [ ] Preserve the statement that this is not an official-protocol reproduction.

### Task 4: Prepare conditional exits and supplement

**Files:**
- Create: `paper/conditional_results/risk_gated_method.tex`
- Create: `paper/conditional_results/audit_only.tex`
- Create: `paper/conditional_results/submission_stop.tex`
- Create: `paper/supplement_v2.tex`

- [ ] Write evidence-bounded prose for each RISK-08 exit without metric placeholders.
- [ ] Keep conditional files outside the compiled manuscript until a real terminal marker selects one.
- [ ] Add evaluator, implementation, R12, SASRec, E7, single-seed, and artifact-inventory details to the supplement.

### Task 5: Replace non-performance figure placeholders

**Files:**
- Create: `paper/figures/method_architecture.tex`
- Create: `paper/figures/risk_mechanism.tex`
- Create: `scripts/build_phi_r_figure.py`
- Create: `tests/test_build_phi_r_figure.py`
- Modify: `paper/main_v2.tex`

- [ ] Write a failing test that checks the six frozen `phi_R` rows and output provenance.
- [ ] Run the test and observe the expected missing-module failure.
- [ ] Implement a deterministic publication-ready PDF/PNG plot from `risk_response_source.csv`.
- [ ] Run the focused test to green.
- [ ] Use TikZ schematics for the method and risk mechanism so text remains editable and no synthetic performance metric is introduced.

### Task 6: Prepare the AAAI compilation wrapper

**Files:**
- Create: `paper/aaai_submission.tex`
- Create: `paper/AAAI_BUILD.md`

- [ ] Detect locally available official AAAI style/class files and TeX engines.
- [ ] If the style exists, compile the anonymous wrapper and record page count.
- [ ] If it does not exist, create a wrapper that fails with a documented missing-author-kit blocker; do not fabricate a style file.
- [ ] Run static checks for unresolved `pfig`, citation, and conditional-result inclusions.

### Task 7: Implement read-only r7 synchronization with TDD

**Files:**
- Create: `scripts/sync_and_build_r7_paper_evidence.ps1`
- Create: `tests/test_sync_and_build_r7_paper_evidence.py`

- [ ] Write failing tests for nonterminal status-only behavior, new dated-directory creation, remote-write prohibition, and terminal builder invocation.
- [ ] Run tests and observe the missing-script failure.
- [ ] Implement the minimal PowerShell synchronizer using `ssh`/`scp` read operations and local hash verification.
- [ ] Run focused tests to green; never execute it against the live server during unit tests.

### Task 8: Review, verify, and hand off

**Files:**
- Create: `plan/review/2026-07-14-aaai-integration-spec-review.md`
- Create: `plan/review/2026-07-14-aaai-integration-quality-review.md`
- Modify: `plan/progress.md`
- Modify: `HANDOFF.md`

- [ ] Run manuscript claim scans and English/Chinese parity checks.
- [ ] Run focused and regression tests, JSON/CSV parsers, Python compilation, and authored-path diff checks.
- [ ] Record capability-use audit, artifacts, unused inputs, compilation status, and remaining r7 blocker.
- [ ] Commit and push only after fresh verification.
