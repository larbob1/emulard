# Performance phase 2: range-diff mapping

Phase 2 builds on the paired-wave Phase 1 candidate. All new runtime
behavior is disabled unless `VICTORY_MAP_DIFF=1` is set.

- Complete aligned direct physical mapping requests compare requested
  backing section and page index with the live view table. Only changed
  spans are unmapped and rebuilt. Wholly changed requests keep the old path, preserving contiguous mapping behavior. Unknown pages on aligned diff requests are rejected before changing mappings.
- Disjoint, fully resolved aligned GPU alias requests snapshot source
  slices and use the same diff path. Overlapping requests and partial-source prefixes retain the previous semantics; disjoint aligned requests whose first source page is absent are rejected without mutation.
- Consecutive already-identical scatter mappings are checked under one
  physical table lock and use one dirty notification for at most 256 pages.
  Changed requests and duplicate addresses retain the ordered fallback.
- When the existing run-batching path is reached, try coalescing exact
  adjacent placeholders before invoking per-page splits.

The mapping guard remains held until all host changes and dirty
notifications finish. A large host view spanning a changed subrange can
still require reconstruction outside the changed range. Changed spans
currently map page by page rather than depending on Wine coalescing.
On host mapping failure the experimental diff path may leave preserved
neighbors and partially applied changes; this is not a transactional
mapper. Keep it opt-in until failure injection and alias tests pass.

## Build
```sh
python3 tools/build_runtime.py ../runtime-perf2 --paired-wave-refresh
python3 tools/cross_build.py ../runtime-perf2 --diagnostics
```

For Windows use the preparation script with `--build` instead of the
cross-build helper. It runs physical alias fixtures and concurrent reader
fixtures with Phase 2 enabled. For Linux, repeat them under Proton using
the same prefix as the runtime.

## Compare
Use the same scene, shader-cache warmup, console mode and graphics settings.
Set `VICTORY_FRAME_LOG=1` and keep capture off. Compare baseline
(`VICTORY_MAP_DIFF=0 VICTORY_MAP_SKIP_SAME=0 VICTORY_MAP_RUNS=0`) against
`VICTORY_MAP_DIFF=1 VICTORY_MAP_SKIP_SAME=0 VICTORY_MAP_RUNS=0`, then compare
with the Phase 1 and existing batching switches separately. Use the phase 1
numeric frame report and look for cumulative `mapping diff totals` lines
at info log level. Counts represent requested saved/mapped pages, not
actual system calls; unchanged pages in a split view may still be remapped
internally. Check aliases, unmap results, rendering, dropped draws, and
median frame time. No FPS gain has been demonstrated.

## Outstanding
Software-only GPU tile mappings, lifetime-pinned backing views, precise
range locking, full placeholder interval tracking, and failure recovery
are not implemented here. Do not remove CPU-visible virtual mappings
until all direct CPU dereferences have been audited.

## Stabilization update

With `VICTORY_MAP_DIFF=1`, preflight rejects unknown physical IDs and disjoint aligned alias requests with no first source page before modifying the destination. Partial-source prefixes retain the original mapper's behavior. Range arithmetic overflow is rejected for all modes. Host mapping failures remain non-transactional; the fixture checks preflight behavior, not rollback.
