# Exact placeholder hint experiment

P05 candidate. `VICTORY_MAP_EXACT_PLACEHOLDERS=1` (off by default) tracks
exact ranges from successful preserve-placeholder unmaps, including
multi-page ranges. A bounded nonoverlapping interval index removes entire
overlapping entries rather than guessing the host split/coalesce state.
Before the original split/replace path, it tries an exact host replacement
for a matching hint. A failed replacement falls back to the existing path.
Alias-run mapping can avoid its per-page split/coalesce loop when an exact
preserved range is available.

This is not an authoritative virtual memory manager: a stale hint cannot
authorize dereferencing memory, and the operating system still checks
replacement. External frees/protection changes are not comprehensively
tracked. Neighbor reconstruction can still require additional mapping.
Memory commit failure cleanup remains an outstanding P06 issue. The cache
is bounded at 65,536 entries; no merging of adjacent ranges is assumed.

Tests: standalone actual interval helper, native physical alias tests in
baseline and optimized mapping modes, concurrent read and tile replay
fixtures. `exact placeholder totals` reports direct replacement attempts
and hits at power-of-two sampling points. A successful hit avoids an
initial split operation; not a complete host syscall census.

Compare on the same binary against the switch off, with all other flags
unchanged. Record actual host map/unmap time, alias rates, p95/p99 frame
times, and complete scene correctness. No performance improvement claimed.
