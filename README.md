# Emulard

Experimental x86-64 console compatibility-layer development. **Not a standalone emulator or a playable release.** The project builds on public upstream implementations instead of rewriting working components.

[Build and test status](https://github.com/larbob1/emulard/actions)

## Architecture and reuse

- [Victory Fork](https://github.com/fxceless/victory-fork): pinned runtime baseline; loader, system shims, graphics translation, shader compiler, input, audio, streaming, caching and existing ray-intersection implementation are retained.
- [VIctory](https://github.com/Marvisak/VIctory): upstream/reference for improved shader coverage, ahead-of-time pipeline preparation, and synthetic GPU memory tests.
- [Five Star Recomp](https://github.com/ThatRecompDev/five-star-recomp): independent reference for shader compiler behavior, memory-aware pipeline compilation, and synthetic tests.

These projects are read-only. The latter two are references, not merged runtimes. See [integration notes](docs/upstream-integration.md) for pinned revisions and boundaries.

## Status

| Area | State |
| --- | --- |
| Source preparation and synthetic probes | Implemented |
| Memory scheduling, query bounds and wave retry | Experimental source patches |
| Builder pipeline preparation and memory budgets | Experimental source patches |
| Full Windows runtime compilation | CI validation pending |
| Lighting and stable world rendering | Unresolved |
| Linux compatibility and performance | Unverified |

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

The numeric frame report tool summarizes existing local telemetry without printing raw log lines:

```sh
python3 tools/frame_report.py /path/to/local.log --skip 5
```

Only compare like-for-like scene intervals and check for dropped draws. Aggregate interval medians are not per-frame percentiles.

## Privacy and licensing

Do not commit proprietary assets, executables, credentials, local paths, hardware identifiers, or raw diagnostic reports. Upstream source and licensing notices remain in their separate checkouts. The project patch scripts and original regression code are provided under GPL-3.0-or-later. See the upstream licenses for upstream components. Source and patch tools only; no commercial content is provided.
