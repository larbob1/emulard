# Performance phase 3: shorten texture mapping locks

This candidate is stacked on Phase 2. The new runtime option
`VICTORY_TEXTURE_SHORT_LOCK=1` is disabled by default.

Fully mapped, non-on-demand textures up to 8 MiB can be copied into the
existing thread-local scratch buffer under the existing mapping read
guard. The guard is released before hashing and detiling. Mapping epochs
are checked after hashing and again after detiling. A snapshot invalidated
before detiling is skipped; one invalidated during detiling is marked for
retry. This does not make the snapshot transactional or guarantee a
fresh image across concurrent writes. It can increase copy cost and
scratch use; global epochs may cause retries due to unrelated remaps.
Other texture paths use their existing behavior. The global lock stays
in place; the epoch is not a substitute for the guard.

A separate standard-library-only Rust prototype in
`probes/range_gate.rs` models interval-based read/write exclusion,
writer priority on intersecting ranges, and expansion to complete host
views. It is not linked into the runtime. A future integration must
audit every writer, including free/protect paths, lock ordering,
section lifetimes and alias invalidation before enabling range locks.

## Prepare and test

```sh
python3 tools/build_runtime.py ../runtime-perf3 --paired-wave-refresh
python3 tools/cross_build.py ../runtime-perf3 --diagnostics
python3 -m unittest discover -s tools -p 'test_*.py'
rustc --edition 2021 --test probes/range_gate.rs -o /tmp/emulard-range-gate-tests
/tmp/emulard-range-gate-tests
```

The performance candidate synthetic workflow runs the Python patcher and
standalone Rust range-gate tests on performance branches. The paired-wave
Windows build also runs the mapping guard and generation fixtures.
Run the existing xmem and shader fixtures before gameplay testing. The
standalone prototype tests do not prove runtime correctness. Benchmark
the exact same warmed scene with `VICTORY_FRAME_LOG=1`, capture disabled,
`VICTORY_TEXTURE_NO_WAIT=0` and the same Phase 1/2 flags in both runs.
Compare `VICTORY_TEXTURE_SHORT_LOCK=0` versus `=1` independently.
At info log level, `texture short-lock totals` reports cumulative snapshot
bytes, copy and unlocked processing microseconds and retry counts. Use
frame reports to compare reader waits and frame time, not additive worker
durations. Validate visible rendering, dropped draws, repeated remaps,
retry behavior and memory usage. No FPS improvement has been demonstrated.

See [deferred-work register](performance-deferred.md) for all unfinished
work from Phases 1–6.
