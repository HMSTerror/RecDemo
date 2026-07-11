# RISK-04--RISK-08 adapter dated manifest

_Generated 2026-07-11; local adapter implementation evidence only; no bank generation, remote deployment, queue creation, tmux session, or training was performed._

## Scope

The manifest binds the queue-safe implementation for RISK-04, RISK-05, RISK-06, RISK-07, and RISK-08 to the E1 R12 pass evidence. It freezes seed `100`, six corruption levels, pilot levels `0/60/100`, `max_attempts=1`, `failure_policy=fail_closed`, the common evaluator/selector identities, and the Steam severe gate. The machine-readable source is [adapter_manifest.json](adapter_manifest.json); its self-hash is recorded in that JSON file.

## Verification snapshot

| Check | Evidence |
|---|---|
| E1 R12 | 2,986 comparisons; 0 failed; first divergence `null` |
| New adapter tests | 5 passed |
| Existing front-gate tests | 16 passed |
| Queue model/validation/scheduler/CLI/controller tests | 59 passed |
| Compile and whitespace | `compileall` and `git diff --check` passed |
| Mutation boundary | no remote deployment, no GPU launch, no frozen-artifact overwrite |

The dated manifest is an implementation/readiness record, not a pilot result. A future RISK-04 asset bundle, RISK-05 freeze, RISK-06/RISK-07 queue root, and RISK-08 exit must each receive its own dated hash manifest after real inputs are supplied.
