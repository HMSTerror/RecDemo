# ADAPT-04 method-pass continuation runbook

This runbook describes the queue contract for the next seed-100 wave. The
adapter is build-only: it writes a new dated manifest and never starts a
trainer, SSH session, tmux session, or deletion operation.

## Preconditions

The controller may select continuation only when all of these are present in
the same dated queue root:

1. E1 `RISK-02_PASS.json` with seed 100 and trace steps `0,1,100,1000`.
2. RISK-04 assets and severe-corruption PASS, followed by the train-only RISK-05
   preregistration and PASS marker.
3. The complete E1-pass RISK-06/RISK-07 pilot artifact set.
4. Exactly one artifact-backed `RISK-08_EXIT.json` whose `exit` is
   `risk_gated_method` and whose E1/RISK-05 hashes match the dated inputs.
5. At least 40 GiB free under `/data`, no unknown GPU process, and no more than
   one training process per GPU. GPU0 CLOSE-10 remains untouched.

An E1 PASS alone does not authorize continuation. A local adapter manifest is
queue-readiness evidence, not a method result and not remote launch authority.

## Frozen seed-100 matrix

- RISK-13: eight matched host/`risk_gated_full` tasks, one pair per
  Steam/ML1M/Beauty/ATG. The result is labelled `partial_seed100` and cannot
  close the original three-seed ledger row.
- RISK-14: the six frozen arms (`host`, `text_anchor_only`, `global_p`,
  `dataset_gate_only`, `full`, `u_shuffle`) for one train-only selected
  high-risk condition and one train-only selected low-risk condition.
- RISK-10: SASRec, Caser, and GRURec, each as an atomic all-four-domain group.
- RISK-11: four DiffRec tasks only after a passing identity/memory audit.
  DiffuRec is a different model and is never substituted.

Every GPU task has `seed=100`, `max_attempts=1`, `failure_policy=fail_closed`,
the common evaluator and validation selector, and an isolated run directory
under the dated root. Each depends on `continuation.method_pass_gate`, which
rechecks the immutable marker hashes.

## Build and verify locally

```powershell
python scripts/build_method_pass_manifest.py `
  --protocol-json <protocol.json> `
  --base-manifest <pilot-queue.json> `
  --output-root <new-dated-root> `
  --e1-marker-json <RISK-02_PASS.json> `
  --risk08-marker-json <RISK-08_EXIT.json> `
  --risk05-preregistration-json <risk05_preregistration.json> `
  --diffrec-audit-json <optional-diffrec-audit.json>

python -m scripts.aaai27_queue.cli validate `
  --queue-root <new-dated-root> `
  --manifest <new-dated-root>/queue/queue_seed100_method_pass.json
```

The output must report `training_started=false`, a high forecast no greater
than 168 GPU-hours, and the exact task counts. If the DiffRec audit is absent
or fails, RISK-11 is omitted and the metadata says `diffrec_blocked`; this is a
fail-closed decision, not permission to substitute DiffuRec.

## Remote launch boundary

Before any remote launch, repeat read-only checks:

```bash
ssh -n -T -o BatchMode=yes l20 hostname
ssh -n -T -o BatchMode=yes l20 "nvidia-smi --query-gpu=index,name,memory.total,memory.used,memory.free,utilization.gpu --format=csv,noheader,nounits"
ssh -n -T -o BatchMode=yes l20 "df -h /data"
ssh -n -T -o BatchMode=yes l20 "ps -eo pid,ppid,user,stat,lstart,etime,%cpu,%mem,args --sort=pid"
```

Do not launch if `/data` is below 40 GiB, GPU0 is not solely the known
CLOSE-10 process, a marker/hash differs, or a previous dated root exists. The
controller is detached only after the exact manifest passes `validate` and
`dry-run`; all commands, exit codes, PID/session, manifest hash, and first
task are appended to the execution ledger. No test metric is used to select a
checkpoint; the manuscript retains: “model selection used validation only;
test metrics were logged during development”.
