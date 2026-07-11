# CLOSE-02 ML1M checkpoint cleanup

**Date:** 2026-07-11 23:43+08:00  
**Scope:** only `close02_diag_ml1m_ours/ml1m_proposal_adaptive_mainpath/checkpoints/**/*.pth`  
**Outcome:** deleted after a pre-delete per-file inventory; no training process referenced the run.

The pre-delete manifest is retained on l20 at:

```text
/data/Zijian/goal/cleanup_manifests/2026-07-11-close02-ml1m-checkpoint-cleanup/manifest.json
```

Manifest SHA-256:

```text
e6b3e7a7dd1be565bca0a59eb639053739c1bf797098a213009d4984328a9245
```

It records 410 candidate files, each path, byte size, and SHA-256, plus the retained
best checkpoint, summary, and frozen run manifest.  The deletion result is recorded at:

```text
/data/Zijian/goal/cleanup_manifests/2026-07-11-close02-ml1m-checkpoint-cleanup/deletion_result.json
```

Deletion result:

- 410 files removed;
- 19,938,406,190 bytes removed;
- zero `.pth` files remain under the candidate `checkpoints/` tree;
- `checkpoints-meta/ML1M/checkpoint_proposal_adaptive_best.pth` retained with SHA-256
  `e1bdf6555040d7588d56ad8191bb42f42dad529f1573b67fcbb2628b52dc0d30`;
- `best_summary_proposal_adaptive.json` retained with SHA-256
  `3f64d85d9599994fd5de20cf4ba8ba92c239163de58115e874efe48f5a0cf9b4`;
- `frozen_run_manifest.json` retained with SHA-256
  `a9394fe36e2a775dfca2b06401d12b1b952581e4d656c100d434c5b1fc0de01d`;
- `/data` free space increased from approximately 49 GiB to 68 GiB;
- r6a seed-100 Steam/host remained running on GPU1 throughout.

No `checkpoints-meta`, logs, summaries, frozen manifests, RISK-04/RISK-05 assets, or
active r6a files were touched.

