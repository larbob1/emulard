# P23 — DirectStorage worker comparison (prepared, unmeasured)

The paired-wave worker-cap patch uses `VICTORY_DISK_WORKERS`. Unset preserves automatic sizing. Positive caps are limited to available logical parallelism; invalid/zero settings fall back to automatic. Verify actual started workers from the numeric startup records; a requested cap is not a measurement. Do not alter runtime code, thread affinity, shader worker caps or correctness guards for this test.

## Matched trial matrix

Use the same known-good diagnostic runtime revision, machine, OS/Proton version, resolution, scene, route, cache state and logging configuration. Run Windows and Proton separately. Keep captures off. Record warmup and wall-clock duration; use at least three independent repeats per setting and rotate order (auto/2/4, 2/4/auto, 4/auto/2). Cold-cache loading is a separate workload from warm scene traversal; keep cache conditions identical within a comparison. Exit normally and keep raw logs local.

| Setting | Flag | Required validation |
| --- | --- | --- |
| Automatic | unset | Actual configured and started worker count |
| Two | `VICTORY_DISK_WORKERS=2` | Actual count; no stalled requests or visible regression |
| Four | `VICTORY_DISK_WORKERS=4` | Actual count; same correctness checks |

Keep `VICTORY_FRAME_LOG=1` and the same diagnostic log level in all runs. The pinned `dstorage.rs::Lanes::count` emits debug-level `dstorage: last ... s` summaries after completed requests. Enable the runtime's existing debug logging mechanism if supported, consistently across all runs. Confirm the lines exist locally; do not enable request/file traces, which may expose private data. The new parser consumes the existing plain-text tracing fields; actual live format has not been validated here. Do not change shared logging/build scripts without coordinator approval.

## Local reports

```sh
python3 tools/benchmark_pairs.py --pair auto-1.log two-1.log --pair auto-2.log two-2.log --pair auto-3.log two-3.log --skip 5 --skip-frame-batches 1 --target-fps 30
python3 tools/storage_report.py two-1.log --baseline auto-1.log --skip 1
```

Repeat for cap 4 and the other matched pairs. Exclusions are independent sample counts, not an exact synchronized wall-clock cutoff. Use equal, explicitly documented warmup; if logs do not cover the same scene/time, reject the comparison. Add `--visible-scene-confirmed` only after the operator has verified full scene rendering in every run. Keep distinct logs even when running the same setting twice.

Record per trial: revision, actual worker count, correct visible frames / elapsed wall seconds, p50/p95/p99, reported drops/pending pipelines, approximate present rate, storage finished requests, weighted destination throughput, busy/reading worker averages, staging waits, waiting queue snapshots, CPU/GPU utilization, RAM/VRAM, crashes and request completion/error evidence. Storage rate windows are activity-only and rounded, can omit idle/trailing periods, and count completed requests even if they failed. Queue snapshots do not prove starvation duration; request/service/queue latency and successful-byte throughput need separate runtime instrumentation or platform telemetry. Worker time is aggregate and must not be added to frame duration.

## Acceptance and next action

No measured result yet. Do not select a cap merely because it increases destination MB/s. Require safe completion, no visual regressions, repeatable frame-time improvement and no regression in the reference workload. Report any missing sample windows explicitly; if debugging overhead materially changes the workload, repeat timing with matched lower-volume logging. Compare actual results with the coordinator before requesting new instrumentation or changing defaults. P23 remains open until owner-run measurements and correctness evidence are available.
