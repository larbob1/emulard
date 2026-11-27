# Developer guide

**Experimental x86-64 console compatibility-layer development, with a goal of sustained, correctly rendered 30 FPS gameplay.**

Emulard is a source-only integration project for the [VIctory fork](https://github.com/fxceless/victory-fork). It maintains reproducible upstream revisions, source patches, preparation/build scripts, regression fixtures and performance diagnostics. It is not a standalone emulator, a finished compatibility product, or a binary distribution.

> **Status: early experimental development.** The initial six performance phases are implemented as candidates, not a validated release. Sustained visible gameplay at 30 FPS has not been demonstrated.

## Project navigation

| Start here | Description |
| --- | --- |
| [30 FPS roadmap](ROADMAP-30FPS.md) | Prioritized engineering work, measurable milestones and acceptance criteria |
| [Development branches](BRANCHES.md) | Branch roles, stacked pull requests and integration policy |
| [Documentation index](README.md) | Build, launch, diagnostics, graphics and memory documentation |
| [Deferred-work register](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/performance-deferred.md) | Canonical live register of P01–P24 and test evidence |
| [Contributing](../CONTRIBUTING.md) | Source-only workflow, testing requirements and reporting policy |
| [GitHub Actions](https://github.com/larbob1/emulard/actions) | Current validation results |

## Current status

The compatibility branch has documented Windows-target builds and Linux/Proton launch experiments. The historical runs reached GPU submission and partial scene output, but also showed black frames, missing pipelines, and multi-second stalls. The project owner reported roughly 1–3 FPS; this is an observed starting point, not a standardized benchmark.

The cumulative performance branch adds candidates for memory mapping, shorter texture locks, CPU-side copy-back work, pipeline scheduling, and storage worker tuning. It retains the production mapping safety guard and the existing GPU fence semantics. Several candidates remain opt-in.

| Area | Evidence / status |
| --- | --- |
| Runtime source preparation | Passed on Linux and Windows in previous CI runs |
| Synthetic regression suite | [107 Python tests and 4 standalone Rust tests](https://github.com/larbob1/emulard/actions/runs/45937706891) passed at commit `8956a8e` |
| Portable copy-back helpers | Same CI: 5 Rust tests in each of two modes (10 executions); not full GPU validation |
| Isolated reverse-alias index | [Synthetic CI passed](https://github.com/larbob1/emulard/actions/runs/45937502413); native verification pending |
| Windows runtime tests / full build | [All 21 selected suite invocations and both build profiles passed](https://github.com/larbob1/emulard/actions/runs/45937702602) at `8956a8e`; newer candidate validation and Proton gameplay remain separate |
| Correct rendering and sustained FPS | Unverified |

CI status changes over time; follow the linked runs rather than treating this snapshot as a live badge. No FPS improvement or playable release is claimed.

## How the project works

```text
Emulard integration repository
  ├─ pinned upstream checkout (outside Emulard)
  ├─ apply source patches and regression fixtures
  ├─ build Windows-target runtime
  ├─ validate synthetic tests and runtime behavior
  └─ measure authorized local software under Windows or Wine/Proton
```

The runtime is an x86-64 compatibility layer with CPU/HLE services, virtual physical-page mapping, graphics/shader translation to D3D12, pipeline compilation, and presentation. Linux execution currently uses a Windows-target runtime under Wine/Proton, not a native Linux backend.

The main performance concern is host virtual memory mapping/unmapping and synchronization. Copy-back, texture processing and shader/pipeline stalls are also important. Historical measurements include multi-second remapping and hundreds of milliseconds of copy-back on individual frames; overlapping worker timings must not be added as though they were wall time.

## Development branch layout

| Branch | Purpose |
| --- | --- |
| `main` | Documentation and project entry point (no runtime scripts yet) |
| [`dev/compatibility-baseline`](https://github.com/larbob1/emulard/tree/dev/compatibility-baseline) | Preserved compatibility reference |
| [`dev/performance-phase6`](https://github.com/larbob1/emulard/tree/dev/performance-phase6) | Cumulative six-phase candidate and current stabilization work |
| [`dev/performance-phase6-alias-index`](https://github.com/larbob1/emulard/tree/dev/performance-phase6-alias-index) | Isolated ordered-set alias indexing experiment |
| `dev/performance-phase1` through `dev/performance-phase5` | Historical stacked implementation checkpoints |

Use the cumulative Phase 6 branch for the latest experimental code. Earlier branches are intentionally preserved until the pull request chain is validated and integrated. See the [branch policy](BRANCHES.md) before merging or deleting branches.

## Prepare and build the experimental runtime

For a controlled first comparison, prefer the Windows-validated revision in the [short playtest guide](PLAYTEST.md) rather than automatically building the newest experimental commit.

These are developer instructions, not an installation guide for a finished product. Use Git, Python 3, the upstream pinned Rust toolchain, and a suitable build environment. A Linux cross-build additionally needs cargo-xwin, Clang, LLD and Windows SDK support. Review the upstream dependencies and build scripts before execution; the preparation tool fetches the pinned public upstream source.

### 1. Clone the integration branch

```sh
git clone --branch dev/performance-phase6 https://github.com/larbob1/emulard.git
cd emulard
python3 tools/build_runtime.py ../runtime-perf6 --paired-wave-refresh
```

Use a fresh external directory. Do not patch the integration checkout itself. The runtime preparation disables pushes to the upstream checkout.

### 2. Build

On Windows, instead of the preparation command above, use a fresh target directory and:

```sh
python tools/build_runtime.py ../runtime-perf6-win --paired-wave-refresh --build
```

On Linux, after preparation:

```sh
python3 tools/cross_build.py ../runtime-perf6 --diagnostics --jobs 2
```

For the release profile omit `--diagnostics`. Linux cross-build output is under `../runtime-perf6/target/x86_64-pc-windows-msvc/diag/victory.exe` or `release/victory.exe`. The Windows native output layout differs. Builds can fail while the experimental candidate is being stabilized; consult [runtime compilation](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/runtime-compile.md) and [first launch](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/first-launch.md).

### 3. Launch (after smoke checks)

Use a dedicated initialized Wine/Proton prefix and authorized locally supplied software. Replace the placeholders with actual local paths. If using Proton, configure the executable adapter as described in the first-launch guide.

```sh
env WINEPREFIX=/path/to/prefix VICTORY_FRAME_LOG=1 bash tools/run_wine.sh \
  /path/to/victory.exe /path/to/title.exe --console series-s
```

The helper maps the supplied software directory to G: in that prefix and refuses to replace a different existing mapping. No title files are included. Use a release build for normal timing and a diagnostic build for matched diagnostic comparisons. Never compare different profiles as though they were the same experiment.

## Performance development

| Phase | Candidate |
| --- | --- |
| 1 | Exact unchanged physical mapping fast path and diagnostic reporting |
| 2 | Range-diff mapping, scatter grouping and placeholder batching |
| 3 | Bounded texture snapshots, mapping epochs and standalone range-gate prototype |
| 4 | AVX2 comparison, sparse merge and idle CPU snapshot budgets |
| 5 | Pipeline worker scheduling and cache save/retry fixes |
| 6 | Storage concurrency controls, reporting and cumulative validation |

These are implementation checkpoints. Production software GPU tile tables, range-based synchronization, backing-view retirement, completion-scoped GPU dirty tracking, asynchronous readbacks and missing shader operations remain outstanding. The [roadmap](ROADMAP-30FPS.md) prioritizes them by correctness dependencies and measured bottlenecks.

### Experimental settings

Start with optional optimization flags unset; change one factor at a time. The paired-wave candidate includes these environment options:

| Setting | Purpose |
| --- | --- |
| `VICTORY_MAP_SKIP_SAME=1` | Exact unchanged mappings |
| `VICTORY_MAP_DIFF=1` | Range-diff mapping |
| `VICTORY_MAP_RUNS=1` | Contiguous alias mapping |
| `VICTORY_CACHE_PAGE_PLACEHOLDERS=1` | Reuse vacant single-page placeholders |
| `VICTORY_TEXTURE_SHORT_LOCK=1` | Bounded texture snapshots |
| `VICTORY_BACK_AVX2=1` | Exact vectorized difference scans |
| `VICTORY_BACK_SPARSE_MERGE=1` | Sparse CPU merge |
| `VICTORY_BACK_IDLE_MB=128` | Example idle snapshot capacity (not a total RAM cap) |
| `VICTORY_PIPELINE_WORKERS=4` | Example compiler worker count |
| `VICTORY_PIPELINE_GRAPHICS_BURST=8` | Example requested-graphics claim limit |
| `VICTORY_DISK_WORKERS=4` | Example storage worker cap |
| `VICTORY_FRAME_LOG=1` | Diagnostic performance logging |

Settings are experiments, not recommendations to enable all at once. See the [phase notes](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/performance-phase6.md) and [deferred register](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/performance-deferred.md) for limitations. Do not bypass synchronization or drop required rendering work to increase an FPS counter.

### Testing and reporting

From the development branch:

```sh
python3 -m unittest discover -s tools -p 'test_*.py'
python3 tools/frame_report.py candidate.log --baseline baseline.log --skip 5
python3 tools/benchmark_pairs.py --pair baseline1.log candidate1.log \
  --pair baseline2.log candidate2.log --pair baseline3.log candidate3.log --skip 5
```

Keep raw logs local. Check visual correctness, failed/dropped draws, shader cache state and scene equivalence before interpreting speedups. A successful synthetic test, pipeline creation or present call does not establish gameplay correctness.

## Licensing and scope

Existing patcher and regression sources carry GPL-3.0-or-later notices where indicated. Respect upstream and third-party licenses and attribution. A repository-wide license has not been separately declared on main; see individual source notices and upstream terms. Do not distribute proprietary executables, game data, keys, private logs or credentials. No official affiliation with Microsoft or other console vendors is implied.

For development questions and reproducible reports, use [GitHub Issues](https://github.com/larbob1/emulard/issues) and follow [CONTRIBUTING.md](../CONTRIBUTING.md).
