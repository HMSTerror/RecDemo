# RISK-05 Freeze Template Status

## ⚠️ Stale Runtime Template

`risk0607_protocol_template.json` is retained for audit and must not be used to generate or launch another queue. It points to the failed r3-era mutable source layout, uses `run_root_posix=<queue>/runs`, and guesses `bank_root_posix`; these assumptions are rejected by the repaired adapter.

The frozen train-only RISK-05 EPE values, thresholds, corruption levels, seed, and `phi_R` values are not deleted or retroactively changed. A new dated implementation amendment must reference them while updating only the source revision, exact RISK-04 paths/hashes, checkpoint contract, E1 revision scope, and queue containment contract.

See:

- [r3 fail-closed audit](../2026-07-11-risk0607-r3-fail-closed-audit/risk0607_r3_fail_closed_audit.md)
- [E1/R12 ownership amendment](../2026-07-11-e01-r12-ownership-scope-amendment/e01_r12_ownership_scope_amendment.md)
- [revised experiment manual](../../../runbooks/2026-07-11-e1-pass-risk04-08-experiment-manual.md)
