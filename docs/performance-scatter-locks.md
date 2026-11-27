# Changed scatter lock batching (P07)

Opt-in `VICTORY_MAP_SCATTER_LOCK_BATCH=1` reduces repeated acquisition of
the existing physical mutex and renderer mapping writer guard by processing
a bounded prefix (at most 64 changed aligned nonzero mappings) in order.
Each page still uses the existing checked host unmap and map. Duplicate
destinations are reevaluated after every operation. Unknown, unchanged,
zero, or unusual entries fall back to the existing scatter loop. Host
failure stops immediately with the already-completed prefix retained.

This is lock batching, not host syscall coalescing. It changes visibility
of intermediate states to concurrent mapping readers: they may wait until
the bounded prefix finishes. Assess reader wait/latency and DirectStorage
contention before enabling by default. The extra precheck and guard may
hurt singleton-heavy workloads. Exact dirty notifications and existing
map/unmap helpers remain; no lock is removed. Full rollback, host run
coalescing, and correctness under Proton remain unverified.

Native regression adds an invalid middle ID and ordered duplicate changed
destinations; run with and without existing diff mapping plus baseline
modes. Sampled counters `scatter lock batch totals` expose batches,
completed pages and failed batches, not host syscalls or wall time.
Coordinate numeric parser support with reliability AI. Compare same binary
switch off/on, recording waits and actual correctly rendered FPS. No gain
claimed. P07 remains open.
