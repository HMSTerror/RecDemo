# r7 resident controller live-start verification

At 2026-07-12 17:02:15 Asia/Shanghai, the detached session `aaai27_r7_seed100_987eb19` started the immutable r7 resident entry. The controller PID is `3277670`, its Linux process-start token is `71220858`, and a second read after the launching SSH client had disconnected still reported the same live PID and token.

The controller is currently in `waiting_external_gpu`, not `training`. GPU 0 still contains root PID `2987761`; GPU 1 still contains root PID `3072363`. The runtime therefore created no task record and no run directory. Queue status remained 14 ready, 8 inactive/pending, 0 running, 0 passed, 0 failed, `actual_gpu_hours=0.0`, `stop_requested=false`, and no RISK-08 exit.

The controller state binds:

- queue manifest SHA-256 `387636c8c5dc5b09bb9c509db26b0f335ecac3ed1525e3c4bee3289612bb966e`;
- finalizer config SHA-256 `1796f59f9ed1c4b9a984ae0ed8a8d3d9e8e8164d1ea2bba90166353412c3ab86`;
- source manifest file SHA-256 `38e448dc26a11b785363fff076bd389fd3543189e5fedf9de75b65aa92b4b513`;
- source revision `987eb1957cf74528ef81f2fd673aabb5a25e42f7`.

No root process was stopped, signalled, reniced, or colocated. P0-5 remains in progress until either a fail-closed task terminal occurs or all fourteen active tasks produce valid artifacts and the original RISK-08 finalizer writes its immutable exit. Machine-readable launch evidence is in `r7_live_start_verification.json`.
