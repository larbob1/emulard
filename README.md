# Emulard compatibility baseline

Emulard is an experimental x86-64 console compatibility-layer development
project. This branch packages and patches the read-only [VIctory fork](https://github.com/fxceless/victory-fork)
runtime. It is for local development and compatibility research; it is not a
standalone emulator or a playable release.

## Current status

The runtime builds for the Windows target and launches under Proton on Linux.
The latest local diagnostic run advanced beyond startup and submitted over
2,000 frames before its 260-second timeout. This confirms launch and GPU work,
not correct rendering or playable gameplay.

This branch includes:

- A multi-plane PresentX compositor for combining scene and interface output.
- A Wine launcher that maps the supplied title directory to `G:` for
  drive-rooted file access.
- A 32 MiB pipeline-worker stack and iterative boolean shader lowering to
  avoid stack overflows on large shaders.
- Conservative shader retry and predicate-search limits for split-wave
  translation.

### Known blockers

- Some compute shaders still fail translation. One needs synchronization
  across divergent waves in a 256-thread group; another uses an unsupported
  waterfall loop. Those draws are dropped.
- Several host GPU pipelines are refused, and intermittent black frames are
  reported.
- The full run did not reach verified gameplay. Rendering correctness,
  controls in gameplay, stability, memory use and sustained frame rate remain
  unverified.

The wave changes keep safety checks enabled. Do not force a group barrier or
approximate divergent-wave result to make a shader appear to translate; that
can deadlock or produce incorrect output.

## Prepare and build

Create a fresh runtime checkout outside this repository. The preparation
script pins the Victory fork revision and applies Emulard's source patches.
It disables pushes from the runtime checkout.

```sh
python3 tools/build_runtime.py ../runtime-emulard
```

On a Windows build host, add `--build` to run the configured shader/GPU checks
and build the release and diagnostic runtimes:

```sh
python3 tools/build_runtime.py ../runtime-emulard --build
```

For Linux cross-compilation, use the separate cross-build workflow described
in [first-launch readiness](docs/first-launch.md). Linux runtime execution is
experimental and requires a configured Wine or Proton environment with
D3D12 support.

## Launch under Wine

Use a dedicated, initialized prefix and a locally built runtime. The helper
maps the title folder as `G:` and refuses to replace an existing mapping to a
different folder.

```sh
WINEPREFIX=/path/to/prefix \
  bash tools/run_wine.sh /path/to/victory.exe /path/to/title.exe --console series-s
```

Set `WINE` to a wrapper for the selected Wine or Proton installation when the
default `wine` command is not the one used to initialize the prefix. See
[first-launch readiness](docs/first-launch.md) for smoke checks and Proton
setup notes.

## Development notes

- Treat repositories referenced by the preparation and patch scripts as
  read-only source material. Make Emulard changes in this repository's
  patchers and integration code.
- Keep game data, keys, executables, local paths, credentials and raw runtime
  logs out of commits. Share reviewed summaries instead of raw diagnostics.
- Compilation and frame progress do not establish playability. Record shader
  refusals and dropped draws when evaluating a change.

See [runtime compilation](docs/runtime-compile.md),
[runtime bring-up](docs/runtime-bringup.md), and
[first-launch readiness](docs/first-launch.md) for detailed workflows.
