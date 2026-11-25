# Emulard

Experimental x86-64 console compatibility-layer development. **Not a standalone emulator or a playable release.** The project builds on public upstream implementations instead of rewriting working components.

[Build and test status](https://github.com/larbob1/emulard/actions)

## Architecture and reuse

- [Victory Fork](https://github.com/fxceless/victory-fork): pinned runtime baseline; loader, system shims, graphics translation, shader compiler, input, audio, streaming, caching and existing ray-intersection implementation are retained.
- [VIctory](https://github.com/Marvisak/VIctory): upstream/reference for improved shader coverage, ahead-of-time pipeline preparation, and synthetic GPU memory tests.
- [Five Star Recomp](https://github.com/ThatRecompDev/five-star-recomp): independent reference for shader compiler behavior, memory-aware pipeline compilation, and synthetic tests.

These projects are read-only. The latter two are references, not merged runtimes. See [integration notes](docs/upstream-integration.md) for pinned revisions and boundaries.

## Status

This is a source-only development branch. Implemented means source lowering or integration exists, not verified gameplay.

| Area | State |
| --- | --- |
| Source preparation and synthetic probes | Implemented |
| Shader integer arithmetic and packed raw-address loads/stores | Expanded; latest compilation pending |
| 32-bit global and buffer atomics | Expanded with wrap counters, conditional subtraction, compare-exchange and buffer float min/max candidates |
| LDS shared-memory atomics | Expanded with reverse subtraction, bounded counters and mask-or, including returning variants |
| Wave64 translation | Partial; divergent cross-wave behavior remains unresolved |
| Dynamic BVH | Partial; all-or-none pipeline gate retained |
| Shadow-mask and ray-traced lighting | Unresolved; actual shader rejection diagnostics needed |
| GPU residency, fault recovery and dirty-page writeback | Partial; dirty filtering not activated |
| RAM and VRAM budgets | Experimental source patches |
| Full Windows runtime compilation | Both configurations passed at b5b6446; latest candidates not compile-verified |
| Linux/CachyOS runtime and gameplay | Unverified |
| 10 FPS target | Unverified |

### Remaining work

- Complete 64-bit atomics with real host atomic support and shader-model capability checks; do not split atomic 64-bit updates into independent 32-bit writes.
- Complete unsupported scalar-memory atomics, floating compare-swap and remaining LDS operations. Verify floating atomic NaN, signed-zero, denormal and rounding behavior.
- Expand packed 16-bit arithmetic, double-precision arithmetic and exact Wave64 support.
- Identify missing shadow-mask and builder shader instructions from local diagnostics; validate dynamic BVH output before normal writeback.
- Complete GPU memory fault recovery, submission replay and conservative dirty-page writeback filtering.
- Reduce memory overhead, resolve build failures and validate first launch on CachyOS.
- Measure correct rendering and sustained frame times on hardware before claiming playability or performance.

Latest atomic candidate: [74a4231](https://github.com/larbob1/emulard/commit/74a4231757696def3f822e7f84b8fc7216fb80ab). Both source compositions were checked against the pinned source. This is not a successful Rust build or GPU test. The BVH safety gate remains enabled.

## First launch

See [first launch readiness](docs/first-launch.md) for the recommended CI-compiled source revision, optional local cross-build and synthetic Wine checks. No playable build has been established.

## Local development

Prerequisites for full runtime compilation: Windows x64, the upstream pinned Rust toolchain, a recent Windows SDK and build tools. GPU testing additionally requires D3D12 Shader Model 6.6 and mesh shaders. Linux is supported for the local diagnostics and synthetic native probes; runtime execution through a compatibility layer is unverified.

```sh
python3 -m unittest discover -s tools -p 'test_*.py'
bash tools/preflight.sh
python3 tools/build_runtime.py ../runtime-baseline
```

Use a new directory outside this repository for each source preparation. Add --build on a Windows build host; add --lighting-memory for the independent page-boundary experiment. The source preparation script disables upstream pushes.

See [runtime compilation](docs/runtime-compile.md), [runtime bring-up](docs/runtime-bringup.md), and [lighting development](docs/lighting-memory.md).

## GPU memory integration

See [cross-project GPU memory review](docs/gpu-memory-integration.md) for the raw scalar-base address candidate and remaining dirty-page integration work.

## Performance target

10 FPS means at most 100 ms per frame. The fastest upstream reported world intervals are about 240–350 ms on another machine. Reducing copies, waits and compilation stalls while preserving correct rendering is the initial objective. No performance result for Emulard has been established.

The numeric frame report tool summarizes existing local telemetry without printing raw log lines. To compare matching scenes and settings, add `--baseline /path/to/baseline.log`:

```sh
python3 tools/frame_report.py /path/to/local.log --skip 5
```

Only compare like-for-like scene intervals and check for dropped draws. Aggregate interval medians are not per-frame percentiles.

## Privacy and licensing

Do not commit proprietary assets, executables, credentials, local paths, hardware identifiers, or raw diagnostic reports. Upstream source and licensing notices remain in their separate checkouts. The project patch scripts and original regression code are provided under GPL-3.0-or-later. See the upstream licenses for upstream components. Source and patch tools only; no commercial content is provided.
