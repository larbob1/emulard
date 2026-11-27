# Performance phase 1: unchanged physical mappings

This is a candidate, not a measured FPS improvement. The paired-wave runtime
keeps its existing default mapping path. Set `VICTORY_MAP_SKIP_SAME=1` to
enable the exact-match shortcut independently of `VICTORY_MAP_RUNS`.
It compares physical section identity and page index for every requested
page, and retains the remapping guard and dirty notification. Missing,
partially changed, and non-aligned alias requests retain the original path.
It does not bypass synchronization or implement a software-only GPU page table.

## Build and test

From Emulard, prepare a fresh external checkout:
```sh
python3 tools/build_runtime.py ../runtime-perf --paired-wave-refresh
python3 tools/cross_build.py ../runtime-perf --diagnostics
```

The cross-build helper now accepts all three pinned revisions. On Windows
use `--build` instead of the separate cross-build helper; the paired-wave
build runs the physical mapping fixture with the fast path off and on.

For Linux, run the cross-built xmem test under the same Proton setup
before testing a title. Check the fixture with both `VICTORY_MAP_SKIP_SAME=0`
and `=1`. Confirm physical aliases, writes, unmaps, and concurrent readers.
Use only authorized local software and an initialized dedicated prefix.

## Matched workload

1. Disable capture and pipeline debug logging, warm the shader cache, then
   measure the same scene and settings for both runs. Keep the existing
   mapping-run switch off to isolate the new path.
2. Set `VICTORY_FRAME_LOG=1 VICTORY_MAP_SKIP_SAME=0` for baseline.
3. Repeat with `VICTORY_FRAME_LOG=1 VICTORY_MAP_SKIP_SAME=1`.
4. Keep raw logs local. Compare numeric-only reports:
```sh
python3 tools/frame_report.py candidate.log --baseline baseline.log --skip 5
```
5. Check mapping calls/time, skipped pages, texture waits, actual displayed
   scene, drops and pipeline completion. Long-frame totals are cumulative
   thread durations and not additive wall time; long-frame samples are
   biased toward stalls. Alias-rate samples are independent reporting windows.
   Repeat with identical settings at least three times; do not merge if
   bytes, visible rendering or stability regress.

## Next work

If unchanged mappings are uncommon, prioritize range-aware backing views
and GPU-only tile aliases. Introduce generation/lifetime checks and
captured synthetic replay tests before narrowing the global read/write
guard. Keep the current mapping fallback. Then measure completion-scoped
dirty tracking and copy-back waits. No new correctness shortcuts should
become default on the basis of FPS alone.
