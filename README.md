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

The runtime also carries two graphics compatibility fixes from downstream
forks. It disables blending for integer render targets while preserving
the blend state for the other targets in the same pipeline. It substitutes
RGBA16 float for R9G9B9E5 render targets when the host cannot render or
write to the original format. The substitution uses the existing stand-in
path, which skips copies that would require converting between the two
texel layouts.

Sources: [Belobug integer blending](https://github.com/Belobug/VIctory-Belobug-AMD/commit/86292110ff2cd2c7d4d5960a3aa40fe02bc4b415)
and [fxceless render-target fallback](https://github.com/fxceless/victory-fork/commit/8dd30ab472697c47b141c273c2a00f8ce1c00520).

Both runtime revisions also carry Belobug's tiled-shadow shader translation
fix for 32-lane GPUs. The translator recognizes far jumps that only exit
an empty wave and follows scalar values that pass unchanged through a
branch join. This lets both halves of a 64-lane console wave reach the
synchronization used for cross-lane reads. [Belobug source commit](https://github.com/Belobug/VIctory-Belobug-AMD/commit/4fd34fdd6634372b9f9a1ac791cdc86be329c0ad)

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

The baseline reports a shader's unsupported wave size before asking the host
driver to create a pipeline. For compiler diagnostics, set
`VICTORY_SHADER_SAVE` to a writable Windows-visible directory. The runtime
saves the input container before translation, so a worker fault still leaves
an input to replay.

Set `VICTORY_LOG=warn,victory_gpu::pipeline=debug` to log each pipeline
job, shader translation, driver compile, and cache operation with its
Windows thread ID. A start event without a matching finish identifies
the last recorded phase on that worker.

Both runtime revisions accept `VICTORY_WAVE_WIDE_DIGESTS` for offline
experiments with selected containers. Use `victory translate --pipelines`
to check whether the driver accepts the resulting pipeline. A successful
creation check leaves dispatch correctness and stability unverified.

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

### Experimental fxceless refresh

Use `--fxceless-refresh` to prepare the newer renderer in a separate
checkout. It includes fxceless's fixes for descriptor records copied by the
game and buffer views that begin between host buffer elements. Emulard
applies the integer blend and Wine disk-backed memory patches to this base.
The refresh uses fxceless's shader translator and presentation path. It
also reuses the placeholder when a single page is remapped over a view
of the same size. This saves one virtual memory call while preserving the
source page and aliasing behavior. Its alias indexes remove individual
addresses without scanning all the views of a page.

```sh
python3 tools/build_runtime.py ../runtime-fxceless-refresh --fxceless-refresh
```

In one Linux/Proton diagnostic run, the vacant-placeholder cache avoided
4,824 host calls across the logged frames. The remapper passed four
captured mapping replays with the cache enabled and disabled. The
scripted run still logged a shader pipeline-worker stack overflow, and
only the FPS overlay was visible when checked. One frame spent 2.95
seconds in remapping. A sustained 10 FPS in visible gameplay remains
unverified.

The diagnostic frame log splits remapping time into map calls, unmap
calls, and time waiting for readers. Set `VICTORY_DISK_WORKERS` to cap
DirectStorage concurrency for a profiling run. The default uses all
available logical CPUs.

Set `VICTORY_MAPPED_BY_VIEWS=1` to skip host memory queries when Emulard's
view table covers an entire texture range. Partly mapped textures and
other allocations use the host query. The diagnostic frame log counts
the queries skipped.

Set `VICTORY_CACHE_PAGE_PLACEHOLDERS=1` to also reuse vacant 64 KiB
placeholders left by earlier unmaps. If the host rejects a cached
placeholder, the mapper retries with the usual split. The diagnostic
frame log counts successful reuses.

Set `VICTORY_BIND_CACHE=1` to try the render-target binding cache ported
from the 7900 XTX fork. It reuses a binding when the host resources and
view descriptions match, and resets the cache when recording moves to
another command list. The diagnostic frame log counts bindings sent and
reused. [Source commit](https://github.com/avatarmanz/VIctory-7900XTX/commit/ca1d519f18ccece3daf2b05191a43fae17ac6f91)

### Experimental paired-wave refresh

Prepare the paired-wave translator from [fxceless PR #854](https://github.com/fxceless/victory-fork/pull/854)
with Emulard's Wine memory and integer blend patches. This build composites
the scene and overlay in retail PresentX calls. It also reads FidelityFX
`FSPX` programs in `ACCC` containers through the shader translator.
The paired-wave build uses the same 32 MiB pipeline worker stack as the
baseline and captures shader inputs before translation when
`VICTORY_SHADER_SAVE` is set.
It also normalizes DXIL loop back edges using [upstream commit 8e14d23](https://github.com/Marvisak/VIctory/commit/8e14d23547c34d323dc5bbcbd127db2ea9c62398)
so the Proton shader converter can handle loops with multiple back edges.
It can also group contiguous physical page mappings and skip unchanged mappings
using [VIctory-7900XTX commit 4180818](https://github.com/avatarmanz/VIctory-7900XTX/commit/41808180e6f362771b57ef2e78d97ddc319c8e8e).
Set `VICTORY_MAP_RUNS=1` to enable batching. Page-by-page mapping remains
the default after the Proton trial still showed multi-second remapping
stalls in Story Mode.
Placed 3D unordered-access views preserve their aliases using
[VItoriaBr commit b6e61ab](https://github.com/uiliannn/VItoriaBr/commit/b6e61ab6311a6eed6c4c138a5cf6fd88339acba7).

```sh
python3 tools/build_runtime.py ../runtime-paired-wave --paired-wave-refresh
```

On a 32-lane GPU, this translator represents each 64-lane console wave
with one host wave. Each host thread executes two logical lanes. Use
`VICTORY_WAVE_LOCAL=idiom` to restrict per-half translation to cases where
the translator recognizes it as exact. Use `VICTORY_WAVE_PAIRS=0` to compare
with the paired-wave fallback disabled.

Replay captured shaders with `victory translate --pipelines` before testing
in Story Mode. In a local Proton run, all five targeted compute pipelines
were created during the Story Mode transition. The captured FidelityFX
programs parse, then stop when the translator encounters a descriptor
modified after loading. The two console pipeline creation methods at slots
`0x1c8` and `0x218` remain unimplemented.

### Trace the Story Mode transition

In a diagnostic paired-wave build, point `VICTORY_CAPTURE` at a writable
capture directory and set `VICTORY_CAPTURE_WORLD=1`. On selected world
frames, `frame-<n>-plane-0.png` shows the first PresentX plane before
compositing when there are multiple inputs. Compare it with `frame-<n>.png`,
the composed frame. The `PresentX input` log identifies each title resource
so it can be matched with the frame's operations. Set `VICTORY_CAPTURE_FRAMES`
to select specific frames, or `VICTORY_CAPTURE_WORLD_ALSO=0,1` to capture
the first two world frames too.

The operation trace also identifies the target addresses and shader hashes
of graphics draws dropped for missing host pipelines. Requested vertex
graphics pipelines get priority over mesh and compute during compilation,
using [VItoriaBr commit 8cb509b](https://github.com/uiliannn/VItoriaBr/commit/8cb509bc09f411049bca57e34ffd277aee0ed357).

Set `VICTORY_NATIVE_UPSCALER=1` to try the title's built-in upscaler when
the FidelityFX path fails. The opt-in checks the picker signature before
changing the in-memory image. It uses the native mode documented in
[VIctory-7900XTX commit e151e71](https://github.com/avatarmanz/VIctory-7900XTX/commit/e151e71fa09faf4525771f71869c03a4e89b68b1).

With `VICTORY_FRAME_LOG=1`, long-frame logs split remapping into system
unmap, map, commit and bookkeeping time using
[fxceless commit d8986cd](https://github.com/fxceless/victory-fork/commit/d8986cd7b8392f85478f5675933c59712519e163). Compare those counters with texture
refresh and copy-back times. Worker durations can overlap. Keep capture
disabled for steady-state timing, since reading back selected frames adds
a GPU wait and PNG encoding.

In a local Series S run under Proton on an RTX 5060 Ti, the first plane
was already black on the first three captured world frames. On two of
them the second plane contained color, which reached the composed output.

In that run, `VICTORY_TEXTURE_NO_WAIT=1` kept the texture refresh wait for
stable mappings near zero by reading through the kernel or retrying on
the next refresh. It remains opt-in. The first captured world frame still
took 18.3 seconds, including 6.8 seconds of system mapping and 3.7 seconds
of system unmapping across threads. The next two captured frames took
4.9 and 2.8 seconds, including 450 and 296 milliseconds of copy-back.

### Experimental unchanged-mapping fast path

The paired-wave performance candidate supports `VICTORY_MAP_SKIP_SAME=1`.
It skips host mapping calls for exact, complete physical page matches while
retaining dirty notifications. It is disabled by default. See
[phase 1 performance validation](docs/performance-phase1.md) for matched-run
instructions and limitations. No sustained FPS improvement has been verified.

### Experimental range-diff mapping

Set `VICTORY_MAP_DIFF=1` in the paired-wave performance candidate to
preserve unchanged spans in partially changed physical mappings, group
unchanged scatter requests and try placeholder coalescing before splitting.
See [phase 2 performance validation](docs/performance-phase2.md). This is
opt-in and not yet compiled or benchmarked.

### Experimental short-lock texture snapshots

Set `VICTORY_TEXTURE_SHORT_LOCK=1` in the paired-wave Phase 3 candidate
for bounded snapshots that release the mapping guard before hashing and
detiling. It is opt-in; no sustained FPS gain has been verified. See
[phase 3 validation](docs/performance-phase3.md) and the cumulative
[performance deferred-work register](docs/performance-deferred.md).

### Experimental GPU copy-back CPU work

The Phase 4 paired-wave candidate offers opt-in `VICTORY_BACK_AVX2=1`,
`VICTORY_BACK_SPARSE_MERGE=1` and an optional idle snapshot capacity
`VICTORY_BACK_IDLE_MB`. See [Phase 4 validation](docs/performance-phase4.md)
for independent tests, caveats and the deferred production dirty bitmap.

### Experimental pipeline scheduling and cache publication

Phase 5 adds `VICTORY_PIPELINE_WORKERS` and `VICTORY_PIPELINE_GRAPHICS_BURST`
for optional compiler scheduling experiments and process-local pipeline
cache publication fixes. See [Phase 5 validation](docs/performance-phase5.md)
and the [cumulative register](docs/performance-deferred.md).

### Buffer-copy performance under Proton

In a Series S Story Mode run on the RTX 5060 Ti, `VICTORY_COPY_CHANGED=alt`
alternated between uploading changed 256-byte chunks and the default at
20-second intervals. After pipeline compilation settled, GPU upload volume
was about 9 MB per frame with comparison enabled and 44 MB with it
disabled. Median reported frame times were about 2.4 and 1.9 seconds
respectively, from four enabled and six disabled reporting windows after
excluding the first six seconds after each toggle. The title progressed
through the scene during the run, so the windows contain different frames.
Keep the changed-byte mode off by default.

The separate `VICTORY_COPY_PLAIN=1` trial stayed below 1 FPS during the
sampled world transition while pipelines were compiling. Neither trial
established an FPS gain. In one 4.7-second frame from the alternating run,
system map and unmap calls alone totaled 4.3 seconds across threads.
That points to the host memory mapping path as the next place to measure
and reduce work.

In the paired-wave build, set `VICTORY_CACHE_PAGE_PLACEHOLDERS=1` on
Proton to reuse exact single-page placeholders after successful unmaps.
This carries over the baseline's Wine-specific fast path. If Wine
rejects a cached address, the mapper splits the placeholder and retries.
The option is off by default. Use `VICTORY_CACHE_PAGE_PLACEHOLDERS=alt`
to alternate every 30 seconds. With `VICTORY_FRAME_LOG=1`, long frames
report successful reuses and fallbacks.

In the Proton trial, one 7.9-second world frame reused 1,048 placeholders
with zero reuse fallbacks. The mapper still spent seconds in system calls,
and the trial did not establish a sustained FPS gain. All 12 xmem tests
passed under Proton with reuse enabled and with it disabled.

### Replay tile mappings

In a diagnostic refresh build, set `VICTORY_PAGE_TRACE` to a new writable
file path as seen by Windows. Set `VICTORY_PAGE_TRACE_AFTER` to the first
presented frame to capture. The trace records up to 65,536 range requests
with process addresses and page indices. It contains no texture bytes.

```sh
python3 tools/prepare_tile_replay.py ranges.csv replay.csv --frame 3300
```

Pass the replay path in `VICTORY_TILE_REPLAY` and run
`cargo test -p victory-hle tile_replay_captured_ranges -- --ignored --nocapture`
on Windows or run the cross-built test executable under Proton. The
normalizer preserves request order in the busiest 128-page window for
the selected frame and replaces source addresses with synthetic pages.
The replay compares the live mapper's page bytes and unmap results with
the software table. The deterministic fixture also checks reads across
page boundaries and writes through repeated aliases. Keep raw traces
local.

Set `VICTORY_TEXTURE_TABLE_CHECK` to the first presented frame to check
live texture reads in a diagnostic build. The uploader samples up to
512 reads and compares the first mapped page segment against a read-only
view of its backing section. It uses the existing upload path during the
comparison. The summary reports matches, skipped reads, concurrent
changes and differing bytes. The `victory_gpu::texture_table=debug` log
filter adds sample addresses for correlation with a local mapping trace.

On hosts with 32-lane waves, `VICTORY_WAVE_WIDE_DIGESTS` enables the
existing experimental wave-wide branch retry for selected compute shaders.
Supply a comma-separated list of 32-digit DXBC container digests. A
container's digest is the 16 bytes after the four-byte DXBC signature.
The shader cache distinguishes configurations with different digest lists.

For rendering diagnosis, `VICTORY_FILL_WAIT=1` makes uploads wait for
earlier GPU writes before reading their source bytes. On Proton, a
world-transition trace caught an upload using old bytes just before a
black frame. This setting avoids that read-ahead path and can increase
frame time.

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

The baseline reuses exact placeholders when replacing mapped physical
pages. Under Wine it also remembers single-page placeholders left by
separate unmaps, which can save a host call when textures stream back in.
If Wine rejects a cached placeholder, the mapper retries with a split.
Set `VICTORY_CACHE_PAGE_PLACEHOLDERS=0` to disable the cache on the baseline.

On a memory-constrained Wine host, set `VICTORY_XMEM_BACKING_DIR` to the
Wine-visible path of an existing private directory on a filesystem with
several GiB free. The runtime uses sparse work files there for console
memory sections. This trades SSD traffic for lower swap pressure. An
abrupt termination of Wine can leave these files behind. Remove them
after the runtime using that directory has exited.

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
