# RISK-05 implementation amendment — r6a successor

**Date:** 2026-07-11 22:40+08:00  
**Predecessor:** r6 `6f0fa3c-r6`, closed because its queue root was created before the builder  
**Source revision:** `946a167cf53209566acb52365dba40a9c0836185`  
**Archive:** `/data/Zijian/goal/prefergrow_source_946a167.tar`  
**Archive SHA-256:** `bb0ef40b67125338c0e61ee65fd1d046b1322b1a12e4fd2bd208e719475b35de`  
**Source root:** `/data/Zijian/goal/RecDemo_aaai27_risk0607_946a167`  
**Queue root:** `/data/Zijian/goal/aaai27_queue/2026-07-11-risk0607-946a167-r6a`

This is an implementation-only successor.  It preserves seed 100, the Beauty/Steam
pilot levels, frozen RISK-04/05 hashes and `phi_R`, `e0_full_tail_v2`, validation-only
selection, GPU1-only scheduling, one attempt, and fail-closed semantics.  It changes
only the source/archive identity and the dated queue root.  The previous r6 root is
retained read-only and is not reused.

Before the resident controller is created, the following gates are mandatory:

1. verify the archive and immutable source hashes;
2. call production `probe_gpu_pids(0/1)` with a short GPU1-only diagnostic and wait for
   natural exit;
3. run a real Hydra `training.startup_probe_only=True` in an isolated writable
   `run_dir`, with no dataloader, optimizer step, checkpoint, summary, validation, or
   test metric;
4. confirm `/data` remains above 40 GiB and no r3/r5 process is resumed.

The startup probe is an engineering gate, not performance evidence.  Only after it
passes may the 22-task seed-100 manifest be built and the resident controller be
started.

