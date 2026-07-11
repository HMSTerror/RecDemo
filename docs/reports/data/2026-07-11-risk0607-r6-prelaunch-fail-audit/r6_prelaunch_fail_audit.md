# RISK-06/RISK-07 r6 prelaunch fail-closed audit

**Date:** 2026-07-11 22:30+08:00  
**Attempt:** `2026-07-11-risk0607-6f0fa3c-r6`  
**Outcome:** `closed_prelaunch_root_created_before_builder`

The first r6 queue root was created before `build_risk0607_manifest()` was called.  The
builder requires a completely absent output root and therefore must not be pointed at
this directory.  The root is retained read-only for provenance; it is not a queue and
must not be reused, overwritten, or launched.

Read-only l20 evidence at 2026-07-11 22:25--22:30+08:00:

- root mode: `dr-xr-xr-x`;
- only three protocol files are present under `protocol/`;
- no `queue/queue_seed100.json`, `state/controller.json`, `runs/`, or task records;
- no r6/r6a controller and no `single_train.py` process;
- both GPUs report 0% utilization and 9 MiB used.

This is an engineering/prelaunch audit only.  It contains no training steps,
checkpoint, validation metric, or performance evidence.  The successor must use a new
source revision/archive and a never-used dated r6a root.

