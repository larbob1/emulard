# Phase 6 — cumulative performance candidate and acceptance

The paired-wave branch contains all six phases. Phase 6 adds an optional
`VICTORY_DISK_WORKERS` cap (unset preserves automatic count, positive values
cannot exceed available CPU parallelism), interval-percentile and FPS milestone
reporting, selected long-frame counts, and a cumulative Windows source/test/build
workflow. The earlier Phase 5 synthetic CI failed one builder patch test because
a short comment anchor overlapped a longer anchor. Phase 6 combines those edits
rather than disabling the test. This does not prove the actual baseline patch
applies until checked against pinned source.

## Build
```sh
python3 tools/build_runtime.py ../runtime-perf6 --paired-wave-refresh
python3 tools/cross_build.py ../runtime-perf6 --diagnostics --jobs 2
python3 tools/cross_build.py ../runtime-perf6 --jobs 2
```

The Windows workflow runs the full paired-wave build and targeted tests.
A compile/test success does not establish actual game rendering or performance.
Use the release build for normal use and diagnostics for matched measurement.

## Acceptance protocol
- Use the same scene, console model, resolution, driver, Proton version and
  shader cache state. Keep capture off, `VICTORY_FRAME_LOG=1` for comparisons,
  and record whether the full scene is visible. Keep previous experimental
  flags unset for baseline; test each opt-in individually before combinations.
- Compare 2, 4 and automatic DirectStorage workers; compare shader worker
  caps independently. Do not reduce synchronization or draw wait budgets just
  to inflate FPS. Repeat each warmed test at least three times.
- Run `python3 tools/frame_report.py candidate.log --baseline baseline.log --skip 5`.
  Interval percentiles summarize reported averages, not individual frames.
  Long frames are selected and capped by the logger; omitted counts are reported.
  No-drop intervals are not proof of correct visual output.
- Validate mapping aliases and failures, concurrent readers, exact copy-back,
  pipeline cache restart, missing shaders and driver/device loss. Compare native
  Windows and Proton if possible. Do not upload raw game logs, binaries or data.

## Deferred-work review

The [cumulative register](performance-deferred.md) retains all IDs P01–P24.
Most architectural changes are still open: software GPU tile tables,
placeholder ranges, transaction recovery, full runtime range locks and backing
view lifetimes, submission-scoped shader dirty tracking, async readbacks,
unsupported shader and pipeline methods, descriptor caching, PGO and native
Linux. The current release candidate is unverified. Prioritize P01/P24 (build
and tests), P02/P20 (real scene benchmark), then the largest measured bottleneck.
No sustained FPS increase is claimed.
