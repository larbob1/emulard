# Combined playtest candidate

Isolated review build, not a merge or release. Base 2d244a519946e3581dffe19f8694b5818fec12d9, whose runtime-changing revision c5db073 passed 27 Windows suites and both profiles. Pinned upstream 51700c6d43a3507fa65e50fe4bb64074ce706cd4.

## Selected contributions

- PR #9 at 72fcda9e75235505afeb69ce687d0438567afb66: exact-placeholder reuse, native 32 suites and both profiles passed. Retain default off.
- PR #14 at c660257e0291ec6a807647835d88f246c98a6c28: zero-size serialization failure and latest pending cache publication recovery; independent synthetic tests passed, combined native test required.
- PR #15 at 9330d96706cd9ce0e65af29bae5784478e6f478f: reporting, matched pairs, storage comparison and owner-attested acceptance evaluation; independent synthetic tests passed. Snapshot only; agents can continue on their own branches. Added exact placeholder counter from PR #9 to this integration-only report and test.
- Excluded PR #10 latest pinned reader, PR #16 scatter lock batching and PR #17 stream bounds pending native verification; no software mapping replacement or default switch changes.

No changes to source branches, main or upstream. No formal FPS gain. Native correctness and playtest approval required.

## First comparison after CI passes

Preserve the known-working executable and use a separate checkout and runtime directory. Follow main's docs/PLAYTEST.md and first-launch guide. Build the pinned combined revision with:

```sh
python3 tools/build_runtime.py ../runtime-combined --paired-wave-refresh
python3 tools/cross_build.py ../runtime-combined --diagnostics --jobs 2
```

Within the same binary compare baseline (all optional mapping optimizations off) against each mapping switch separately. In particular compare `VICTORY_MAP_EXACT_PLACEHOLDERS=1` against the same baseline; compare `VICTORY_MAP_DIFF_RUNS=1` with `VICTORY_MAP_DIFF=1` already set in both runs; compare `VICTORY_MAP_ALIAS_DIRECT=1` with `VICTORY_MAP_RUNS=1` set in both. Keep `VICTORY_FRAME_LOG=1` and other settings identical. Only combine switches after successful individual comparisons; maintain identical cache state and visible gameplay. The cache publication fix is unconditional, so use a separate controlled revision comparison to measure its effect.

Use `python3 tools/frame_report.py candidate.log --baseline baseline.log --skip 5 --skip-frame-batches 1 --target-fps 30`. See performance-acceptance.md and performance-storage-comparison.md for stronger evidence. No raw logs, proprietary data or private paths should be shared.
