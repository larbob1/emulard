# Documentation index

This is the project-level navigation on main. Runtime-specific documents are maintained on the [cumulative development branch](https://github.com/larbob1/emulard/tree/dev/performance-phase6) and may describe experimental or historical candidates. Check the branch/commit before executing commands.

## Getting started

- [Main README](../README.md)
- [Beginner's getting-started guide](GETTING-STARTED.md)
- [Short performance test](PLAYTEST.md)
- [Developer guide and build instructions](DEVELOPMENT.md)
- [30 FPS roadmap](ROADMAP-30FPS.md)
- [Branch policy](BRANCHES.md)
- [Contributing](../CONTRIBUTING.md)
- [Canonical deferred-work register](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/performance-deferred.md)

## Build and development

| Document | Topic |
| --- | --- |
| [Runtime compilation](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/runtime-compile.md) | Pinned source and build workflow |
| [First launch readiness](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/first-launch.md) | Synthetic probes, Wine/Proton and smoke checks |
| [Runtime bring-up](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/runtime-bringup.md) | Initialization and diagnostics |
| [Upstream integration](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/upstream-integration.md) | Source integration approach |
| [Automated checks](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/automated-checks.md) | Baseline synthetic probes |
| [Paired-wave tile replay](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/paired-tile-replay.md) | Local mapping traces and regression fixtures |

## Performance phases

| Phase | Notes |
| --- | --- |
| 1 | [Mapping fast path](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/performance-phase1.md) |
| 2 | [Range-diff mapping](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/performance-phase2.md) |
| 3 | [Short-lock snapshots](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/performance-phase3.md) |
| 4 | [Copy-back and memory budget](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/performance-phase4.md) |
| 5 | [Pipeline scheduling and cache](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/performance-phase5.md) |
| 6 | [Acceptance and advanced optimization](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/performance-phase6.md) |
| Isolated | [Reverse-alias index](https://github.com/larbob1/emulard/blob/dev/performance-phase6-alias-index/docs/performance-alias-index.md) |

## Technical research

- Memory: [GPU memory integration](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/gpu-memory-integration.md), [dirty policy](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/dirty-policy.md), [dirty feedback](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/dirty-feedback.md), [descriptor ownership](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/descriptor-ownership.md), [snapshot coverage](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/snapshot-coverage.md), [memory budget](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/memory-budget.md).
- Shaders: [wave translation](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/wave-translation.md), [split-wave synchronization](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/split-wave-sync.md), [wave budget](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/shader-wave-budget.md), [group uniform control](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/group-uniform-control.md).
- Graphics research: [lighting memory](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/lighting-memory.md), [fault bitmap](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/fault-bitmap.md), [ray feedback compatibility](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/ray-feedback-compatibility.md).

[All development documents](https://github.com/larbob1/emulard/tree/dev/performance-phase6/docs) · [CI results](https://github.com/larbob1/emulard/actions)

## Development tree

`tools/` holds preparation, patcher, test, report and launch scripts. `patches/` holds reviewed upstream transformations. `probes/` holds synthetic fixtures. `docs/` holds design and experiment notes. `.github/workflows/` holds CI definitions. These directories exist on development branches; main is currently documentation-only.
