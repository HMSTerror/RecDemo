# AAAI-27 r7 atomic queue prelaunch report

Date: 2026-07-12  
Execution state: `prelaunch_pass_no_training_started`

## Scope and conclusion

The r7 source and the 22-task atomic queue have been created in new dated roots and validated without launching a scientific child process. The active E1-pass branch contains exactly fourteen seed-100 tasks; the eight E1-fail audit tasks remain schema-only and inactive. GPU 0 and GPU 1 were both occupied by root-owned non-r7 jobs at the final prelaunch snapshot, so the production queue still had zero task records, no `runs/` directory, no controller state, and no r7 training PID.

This report establishes only launch-contract readiness. It does not establish an r7 result, a RISK-08 exit, performance improvement, statistical stability, or multi-seed evidence.

## Immutable roots and identities

- Source root: `/data/Zijian/goal/RecDemo_aaai27_risk0607_987eb19_r7`
- Source revision: `987eb1957cf74528ef81f2fd673aabb5a25e42f7`
- Queue root: `/data/Zijian/goal/aaai27_queue/2026-07-12-risk0607-987eb19-r7`
- Source manifest logical SHA-256: `33d7e35ec11d27bbbffafa186ac8776408ca83ae0a7eaf31e443e14436512dea`
- `SOURCE_MANIFEST.json` file SHA-256: `38e448dc26a11b785363fff076bd389fd3543189e5fedf9de75b65aa92b4b513`
- Queue manifest SHA-256: `387636c8c5dc5b09bb9c509db26b0f335ecac3ed1525e3c4bee3289612bb966e`
- Finalizer config SHA-256: `1796f59f9ed1c4b9a984ae0ed8a8d3d9e8e8164d1ea2bba90166353412c3ab86`
- Protocol SHA-256: `0ea14f6100beb899597047ce47aa0ebb9771bb532719441a295d75ad50dcccf4`

All 45 source-manifest entries were compared against the LF bytes from the Git revision and passed `sha256sum -c`. The source tree was then frozen read-only; `find ... -perm /222` returned no writable entry.

## Queue-contract results

| Check | Observed result | Verdict |
|---|---|---|
| Queue schema | 22 unique tasks | Pass |
| Active branch | 14 `pilot/e1_pass` tasks | Pass |
| Inactive branch | 8 `pilot/e1_fail_audit` tasks | Pass; no task record |
| Seed | every task has `seed=100` | Pass |
| GPU allowlist | physical cards `[0,1]` | Pass |
| Host identity | Beauty and Steam host use `graph.type=adaptive` | Pass |
| Anchor identity | six active anchors each contain exactly one `gate_dataset_scale_override=1.0` | Pass |
| Full scales | Beauty `1.0/0.1366311174092942/0.0`; Steam `1.0/0.05808110271503808/0.0` | Pass |
| Wrapper | absolute r7 wrapper and child-source paths | Pass |
| Success evidence | selected summary plus `artifact_manifest.json` for every task | Pass |
| Null reference | evidence arms bind frozen clean calibration, clean-bank hash, current embedding hash, and null-curve hash | Pass |
| Run isolation | 22 unique run directories below the dated queue root; `cwd=run_dir` | Pass |
| Retry policy | `max_attempts=1`, `failure_policy=fail_closed` | Pass |
| RISK-08 finalizer | 14 active IDs, 8 inactive IDs, source revision, E1, RISK-05, preregistration, and train-only preflight hashes rebound successfully | Pass |

The generic validator returned `status=valid`, `task_count=22`, `gpu_ids=[0,1]`, and `seed_values=[100]`. The E1-pass dry run selected fourteen training tasks but did not execute them. A separate absent-root no-op smoke emitted `training_started=false`; it was not run against the production queue root.

## GPU and process snapshot

At 2026-07-12 16:55 Asia/Shanghai:

- GPU 0 probe returned PID `2987761`, owner `root`, a Sports SlowFast job;
- GPU 1 probe returned PID `3072363`, owner `root`, a Beauty frozen-LLM-memory SlowFast job;
- production queue status was 14 ready, 8 pending, 0 running, 0 passed, 0 failed;
- actual r7 GPU time was `0.0 h`;
- no root process was stopped, signalled, reniced, or colocated.

The manifest's 88 GPU-hour status forecast sums both active and inactive schema tasks at their conservative per-task high bound; it is not the r7 active-branch runtime estimate. The approved active-branch planning estimate remains 12–16 GPU-hours, conditional on card release.

## Frozen-asset non-modification audit

The following r6a hashes were recomputed after r7 construction and remained identical to the pre-copy values:

```text
1975ec327c0d978e65764288690141c525de7de0257b28b1a036173c12fdda41  model/text_side.py
c52654e3bd77a90f98ebd05ded19258eacc3a1bc9ff4beac6f9ac38cda980257  scripts/aaai27_adapters/pilot_adapters.py
50e64e455865ceb3893e94a558adda156bc1301df8eb86fe188df3dbd5a45e84  scripts/aaai27_adapters/risk_report.py
84ef807495379ea4e2aa5831543710437e15b5d703a9e288b652041ed9b5a81e  scripts/aaai27_adapters/risk04_08.py
```

The production `model/text_side.py` remains unchanged; the anchor correction is confined to the queue adapter.

## Verification commands retained for audit

```bash
/data/Zijian/goal/PreferGrow/.venv/bin/python3 -m unittest \
  tests.test_r7_resident_controller tests.test_r7_pilot_report \
  tests.test_aaai27_pilot_task_wrapper tests.test_r6_launch_contract \
  tests.test_risk04_08_queue_safe_adapters tests.test_text_side_proposal \
  tests.test_aaai27_front_gate_adapters tests.test_aaai27_queue_validation \
  tests.test_aaai27_queue_runtime tests.test_aaai27_queue_controller \
  tests.test_aaai27_queue_cli tests.test_launch_aaai27_seed100_queue

/data/Zijian/goal/PreferGrow/.venv/bin/python3 \
  scripts/build_risk0607_pilot_manifest.py \
  --risk05-dir /data/Zijian/goal/RecDemoRuns/aaai27_risk05_2026-07-11_332efb8 \
  --e1-marker-json /data/Zijian/goal/aaai27_queue/2026-07-11-risk0607-946a167-r6a/markers/RISK-02_PASS.json \
  --output-dir /data/Zijian/goal/aaai27_queue/2026-07-12-risk0607-987eb19-r7 \
  --protocol-json /tmp/risk0607_protocol_r7_987eb19.json

/data/Zijian/goal/PreferGrow/.venv/bin/python3 \
  scripts/aaai27_r7_resident_queue.py validate-finalizer \
  --queue-root /data/Zijian/goal/aaai27_queue/2026-07-12-risk0607-987eb19-r7 \
  --manifest /data/Zijian/goal/aaai27_queue/2026-07-12-risk0607-987eb19-r7/queue/queue_seed100.json
```

Machine-readable evidence is in `r7_prelaunch_manifest.json` in this directory.

## Next authorized action

P0-5 may start only through the detached tmux entry with `scripts/aaai27_r7_resident_queue.py` as the controller entry. While both GPU probes return compute PIDs, the expected state is a live waiting controller and zero r7 training PID. A task failure, empty log, artifact/hash mismatch, inactive-branch record, or RISK-08 `submission_stop` is terminal and authorizes no rescue run.
