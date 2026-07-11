# Host/core v2 artifact audit — 2026-07-11

This dated attempt audits existing l20 artifacts as a preflight dependency. It
does not overwrite the source runs and it does not launch a GPU process.

## Acceptance

- Beauty and Steam manifests state `random_seed=100` and `kernel_version=v2`.
- The best checkpoint exposes `text_side_builder.p1` with a finite vector of
  length `item_count + 1` (Beauty 12,102; Steam 9,266).
- Checkpoint and manifest SHA-256 values are recorded in `attempt_manifest.json`.
- The existing run logs terminate with a real `BEST_RESULT` and an early-stop
  marker; no copied metric is used.
- The v2 p1 checkpoint is passed to `proposal_records.py` unchanged; it is not
  relabelled as `RISK-09` (that ledger row is reserved for classic baselines).

## Key read-only commands executed on l20

```bash
ssh -n -T -o BatchMode=yes -o ConnectTimeout=10 l20 hostname
ssh -n -T -o BatchMode=yes -o ConnectTimeout=10 l20 nvidia-smi --query-gpu=index,name,memory.total,memory.used,memory.free,utilization.gpu --format=csv,noheader,nounits
ssh -n -T -o BatchMode=yes l20 find /data/Zijian/goal/RecDemoRuns/main_table_text_side -maxdepth 5 -type f -name frozen_run_manifest.json -print
ssh -n -T -o BatchMode=yes l20 python3 - <<'PY' ... torch.load(...)["model"]["text_side_builder.p1"] ... PY
```

The exact command outputs and source paths are retained in the session audit;
the immutable hashes are in `attempt_manifest.json`.

## Next gate

Run train-only proposal records over every Beauty/Steam corruption level using
the approved RISK-04 bank hashes. Then run the preflight report and evaluate the
fixed severe gate. A pending/failed severe gate remains a hard stop and does
not authorize RISK-05 or any pilot training.
