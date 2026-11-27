# Paired-wave tile replay

The existing synthetic stable-backing replay fixture is now prepared for
paired-wave builds. It compares native mapped aliases with a software table,
including cross-page reads and detiling. It is a test, not a replacement
runtime mapper. The Windows test plan runs it with experimental mapping
flags disabled and enabled.

Diagnostic builds can optionally record the same local mapping-range CSV
as the fxceless variant via `VICTORY_PAGE_TRACE` and
`VICTORY_PAGE_TRACE_AFTER`. Keep all traces local; they contain title virtual
addresses. The trace has a bounded entry count and can alter timing; do not
benchmark with tracing enabled. The ignored captured replay fixture accepts
the normalized format via `VICTORY_TILE_REPLAY`, with a 4096-page per-region
fixture limit. Never pass untrusted capture files.

No runtime replay has yet been verified on paired-wave. See P08 in the
[deferred register](performance-deferred.md).
