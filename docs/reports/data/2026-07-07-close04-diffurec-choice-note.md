# CLOSE-04 Baseline Choice Note

- Date: 2026-07-07
- Scope: `CLOSE-04` external baseline choice for `issues/2026-07-06_evidence-priced-schedule-and-closeout.csv`

## Decision

Choose `DiffuRec` as the single external baseline for the first closeout round.

## Why DiffuRec

1. Official code is publicly released:
   - `https://github.com/WHUIR/DiffuRec`
2. The method family is closest to the current host narrative:
   - it is still a diffusion-style sequential recommender
   - it uses behavior history only, which keeps the comparison cleaner than adding a large text-model stack first
3. `Recformer` is weaker as the first closeout choice from an execution standpoint:
   - the official repository states that the code cannot currently be released
   - it points users to an unofficial replication instead
   - that adds extra protocol risk for a time-boxed closeout run

## Repo Reality Check

Current repo scan shows no existing:

- `DiffuRec` wrapper
- `Recformer` wrapper
- third-party subtree for either baseline
- shared baseline runner already wired to `paper_raw_v1`

So `CLOSE-04` is not blocked by baseline selection anymore; it is blocked by missing integration work.

## Integration Finding

The upstream `DiffuRec` code expects dataset files in the form:

- `datasets/data/<dataset>/dataset.pkl`

with dictionary keys such as:

- `train`
- `val`
- `test`
- `smap`
- `umap`

and the default pipeline uses per-user next-item style splits inside that pickle.

Our regenerated protocol is different. The authoritative builder in [scripts/build_paper_datasets.py](/E:/PreferGrow/scripts/build_paper_datasets.py) writes:

- `train_data.df`
- `val_data.df`
- `test_data.df`
- `train_data.txt`
- `valid_data.txt`
- `test_data.txt`

under `dataset/paper_raw_v1/<dataset>/`, and those artifacts come from disjoint user-group splits plus row-level examples.

That means we should not claim protocol parity by dropping `paper_raw_v1` directly into upstream `dataset.pkl` format without an explicit adapter.

## Next Step

Build an independent `DiffuRec` wrapper that:

1. reads the regenerated `paper_raw_v1` artifacts
2. preserves the shared split/selector discipline
3. reuses the upstream `DiffuRec` model core where practical
4. emits a summary/table in the same closeout reporting style as the host runs
