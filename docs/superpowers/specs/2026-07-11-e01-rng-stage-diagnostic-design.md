# E1 RNG stage diagnostic design

## Motivation

R2 proved that all arms enter the comparable trace with the same normalized RNG state. R3 corrected the host/proposal graph sampling helper and passed CPU equivalence tests, but the remote trace still ended with different post-validation RNG hashes and later gradient/loss differences. The next action must localize the remaining consumption boundary before another behavior change.

## Instrumentation

Wrap the existing initial validation evaluator at the trace harness boundary without changing its input, output, or RNG stream. For each arm record:

1. RNG metadata immediately before `iter(val_loader)`;
2. RNG metadata immediately after iterator creation;
3. for every p2 sampler call, metadata before and after the production sampler plus batch shape;
4. metadata after `evaluate_loader` and before the runtime state is captured.

The wrapper records metadata only. It must not call any random operation, alter the sampler, or run a second evaluation. The report should identify the first arm/stage with an unequal post-state while retaining the existing trace result as fail-closed.

## Success criteria

- instrumentation unit test proves the wrapper does not advance a synthetic RNG state and records the expected call count;
- all existing E1/front-gate/controller tests remain green;
- one isolated seed-100 remote diagnostic run yields a first divergent stage;
- no pass marker or training launch is allowed from this row.
