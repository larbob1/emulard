# Performance phase 4: copy-back work and idle snapshot memory

The pinned paired-wave renderer already compares completed GPU writes with
snapshots, pools texture staging allocations, and has multiple experimental
queue paths. Phase 4 adds three independent opt-in experiments without
changing submission ordering, fences, or shader write policy:

- `VICTORY_BACK_AVX2=1`: exact 32-byte SIMD first/last difference scans,
  with runtime AVX2 detection and scalar fallback. The scanner only
  accesses complete chunks and handles tails and unequal lengths.
- `VICTORY_BACK_SPARSE_MERGE=1`: skip exactly equal 256-byte chunks in
  relay merge; skip zero blocks in existing write masks. Changes neither
  byte conflict resolution nor write-mask semantics.
- `VICTORY_BACK_IDLE_MB=128`: example hard cap for idle CPU snapshot
  buffers only. Unset preserves upstream behavior. Zero disables retention.
  Live snapshots are not capped, freed early, or dropped. Buffer eviction
  can increase allocation churn; compare with the original pool behavior.

These are CPU-side copy-back optimizations and idle RAM controls, not a
production GPU dirty bitmap or reduced GPU-to-CPU transfer volume. They
may be slower when most chunks differ or memory allocation churn increases.
No FPS or memory improvement has been measured.

## Prepare and validate
```sh
python3 tools/build_runtime.py ../runtime-perf4 --paired-wave-refresh
python3 tools/cross_build.py ../runtime-perf4 --diagnostics
```

On Windows the preparation script with `--build` runs existing difference,
merge and new perf4 fixtures; tests are not yet verified in this environment.
Compare the same warmed scene with the same prior-phase flags, capture off,
`VICTORY_FRAME_LOG=1`, and each new setting independently. Record frame
time, CPU copy-back and GPU transfer times, RAM, allocation churn, drops and
visible rendering. Compare the idle budget against the unset default.

## Deferred

Production dirty tracking needs immutable submission-owned bitmaps,
descriptor lifetime management, complete shader store/atomic coverage,
fault handling and completion ordering. The existing dirty policy model
does not authorize skipping uninstrumented writes. GPU transfer reduction,
fence-safe async readbacks, persistent resource budgeting and remaining
Phase 1–3 work stay on the [cumulative register](performance-deferred.md).
