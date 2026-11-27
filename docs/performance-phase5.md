# Performance phase 5: pipeline scheduling and cache publication

Stacked on Phase 4 for the paired-wave runtime. Two opt-in scheduling
settings preserve default behavior when unset:

- `VICTORY_PIPELINE_WORKERS=4`: select 1–8 compiler workers. Each retains
  the existing 32 MiB reserved stack and below-normal thread priority.
  Invalid settings fall back to the existing automatic count.
- `VICTORY_PIPELINE_GRAPHICS_BURST=8`: after at most 8 requested vertex
  graphics jobs are claimed consecutively, allow a waiting requested
  compute/mesh job to be claimed. Valid range 1–128. This is queue claim
  fairness, not a completion latency guarantee; early prewarm jobs can
  still wait and jobs already compiling cannot be preempted.

The candidate also serializes library saves across threads within a single
process, including publication of temporary files. Periodic callers skip
rather than wait behind an active save; forced saves wait. Failed
serialization retains pending early-list work; failed library publication
restores the captured added count without overwriting concurrent stores;
failed early-list publication requests a retry. These correctness changes
apply regardless of scheduling flags. They do not solve independent
processes sharing the same cache directory. Use a separate cache per
concurrent runtime process.

## Prepare

```sh
python3 tools/build_runtime.py ../runtime-perf5 --paired-wave-refresh
python3 tools/cross_build.py ../runtime-perf5 --diagnostics
```

On Windows use the preparation script with `--build` to run targeted
pipeline queue, cache and wave fixtures and build. Tests still need to be
run. Test cold and warm runs independently, with capture disabled, stable
scene/settings, and `VICTORY_FRAME_LOG=1`. Compare automatic worker count
versus 2 and 4, then compare the graphics burst unset versus 8. Track
pipeline waits, created/loaded counts, dropped draws, visible output and
median/tail frame time. Keep `VICTORY_PIPELINE_WAIT_MS` fixed for these
comparisons: reducing it can drop more draws rather than improve gameplay.

## Still deferred

No unsupported shader operation was newly lowered here. Do not remove
wave/descriptor safety checks or count a dropped draw as successful.
Persistent cache fingerprint coverage, shader compilation stack failures,
driver cache failure-injection validation, shader semantics, missing
pipeline creation methods and real render replay are still open. See the
[cumulative register](performance-deferred.md). No verified FPS gain.
