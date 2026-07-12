# r7 anchor-only gate-source repair test report

Date: 2026-07-12 (Asia/Shanghai)

Scope: adapter-only repair in `scripts/aaai27_adapters/pilot_adapters.py`. Production `model/text_side.py` was not edited.

## Root cause reproduced

The r6a anchor argv contained no explicit `text_side.gate_dataset_scale_override`. On a clean-`phi=0` path this allowed the builder's stored dataset scale to be zero. Although the `text_anchor_only` branch constructs `g=g_max`, the later production condition

```python
closed_gate = self.injection_mode == "kernel" and (
    self.gate_dataset_scale == 0.0 or self.ablation_mode == "global_p"
)
```

then replaced the final proposal with `p_core`. The same missing override also allowed automatic utility-report discovery and caused r6a's corrupted-bank/report hash mismatch before training.

## RED evidence

Before the adapter change, the two new tests were executed together:

```text
python -m unittest \
  tests.test_r6_launch_contract.R6LaunchContractTests.test_e1_pass_anchor_tasks_bind_one_full_scale_and_no_utility_report \
  tests.test_r6_launch_contract.R6LaunchContractTests.test_anchor_adapter_scale_prevents_phi_zero_final_proposal_core_override
```

Observed result: `Ran 2 tests`, `FAILED (failures=2)`.

- the first failure found no override token in `pilot.e1_pass.Beauty.anchor.c0`;
- the second failure observed `proposal == p_core`, with the explicit message `anchor final proposal was silently overwritten by p_core`.

After the first minimal insertion, a second RED test was added because full argv is cloned from anchor argv:

```text
python -m unittest \
  tests.test_r6_launch_contract.R6LaunchContractTests.test_e1_pass_full_tasks_retain_exactly_one_frozen_scale
```

Observed result: `Ran 1 test`, `FAILED (failures=1)`, because Beauty full c0 contained `['1.0', '1.0']`. This prevented a duplicate/ambiguous gate source from reaching r7.

## Minimal implementation

The adapter now:

1. appends exactly one `text_side.gate_dataset_scale_override=1.0` to anchor argv;
2. when deriving a full argv, replaces that token with the already frozen bank-specific `phi_R` token rather than appending a second source.

No production proposal formula, gate formula, model parameter, optimizer, selector, evaluator, seed, dataset, bank, or threshold changed.

## GREEN evidence

Targeted command:

```text
python -m unittest \
  tests.test_r6_launch_contract.R6LaunchContractTests.test_e1_pass_anchor_tasks_bind_one_full_scale_and_no_utility_report \
  tests.test_r6_launch_contract.R6LaunchContractTests.test_anchor_adapter_scale_prevents_phi_zero_final_proposal_core_override \
  tests.test_r6_launch_contract.R6LaunchContractTests.test_e1_pass_full_tasks_retain_exactly_one_frozen_scale
```

Observed result: `Ran 3 tests in 0.968s`, `OK`.

Regression command:

```text
python -m unittest \
  tests.test_r6_launch_contract \
  tests.test_risk04_08_queue_safe_adapters \
  tests.test_text_side_proposal \
  tests.test_aaai27_front_gate_adapters \
  tests.test_aaai27_queue_validation
```

Observed result: `Ran 63 tests in 9.607s`, `OK`.

## Seven acceptance checks

| Check | Evidence | Result |
|---|---|---|
| Six E1-pass anchor argv have one override 1.0 | manifest-level unit test | pass |
| Anchor argv have no utility-report token | manifest-level unit test | pass |
| Clean-phi-zero adapter fixture yields `g=g_max` | real production proposal builder probe | pass |
| Final anchor proposal differs from `p_core` | real production proposal builder probe | pass |
| Final proposal equals fixed anchor mixture | real production proposal builder probe | pass |
| Full c100 remains exact `p_core` | existing closed-gate gradient/identity tests plus unchanged production file | pass in tested scope |
| E1/global-p and queue regressions remain green | 63-test regression set | pass |

## Source boundary

- Local `git diff -- model/text_side.py`: empty.
- Frozen r6a server `model/text_side.py` SHA-256 before and after P0-0: `1975ec327c0d978e65764288690141c525de7de0257b28b1a036173c12fdda41`.
- The server has not yet received this patch. Production deployment remains P0-4 and is forbidden until P0-2/P0-3 also pass.
