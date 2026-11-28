# R2 production-source preview (unregistered)

AI1 approved #11 7233767389; exact scope claim #12 7233794710. Pristine integration 08472987ffee011796d48d7c90114439a6a68908, upstream 51700c6d43a3507fa65e50fe4bb64074ce706cd4. Native scope previously accepted in #139 e68b115a085178235a40aad121528da1b6867793 (run46105151941/job140856124547, 26/26 normal outcomes); fixture parent #136 e0a0579508346cf877d1ed818516e73f21a3d9f0. This is a source-only preview, not production inclusion.

The new `patches/paired-wave-texback-selection-r2.patch` has precisely three replacements copied from reviewed transform blob 0e0f673cd6c60b05be0b2a68fb4a0b398ac8b6a5: ignore empty remap ranges including saturated end<=at, acquire-load current ticket status, replace stale same-owner selection only if a new Target succeeds, drop displaced host copy outside deferred guard. Preserve current selection, no automatic rebind at close, no failed-creation fix, no changes to record/land or queue/fence. No test observers or resource append.

| Path | Prepared Git blob | Repair-only Git blob | LF bytes |
|---|---|---|---:|
| host.rs | 88acbb3b2cf550cdf2303685fcc32249f9e46328 | 031a65c12bbab967759383b2a75a3be46c46bbde | 444457 |
| texback.rs | 3102a4f9ed2f80c86a28fcc5070b855143279574 | a17dfb5f693163d64ab8f4a60ede71e52c2f596a | 11026 |

Patch Git blob 57431b71dc138f7f82c82ea97dd60977530ffeda. Reconstructed exact pinned prepared host (16 hunks forward/inverse) and unchanged texback from upstream; all input blob hashes verified; three validated replacements replayed as unified-diff hunks, then reversed exactly. Repair-only hashes equal actual #139 intermediate receipts before fixture append, not the final instrumented hashes. Host timing/late_stage/relay function bodies unchanged. This is static isolated JS reconstruction, not execution of git apply or builder, compile, native run, or actual matched-arm parity.

## Common placement proposal

Do not register from this branch. If AI1 approves after AI3 review, common insertion is at the end of the paired-wave prepared source sequence (builder 31bc201ad006b304542e8b03405c1a9090d76804, after apply_alias_direct_run.py and before final git diff --check), or equivalent coordinator-owned common stage before any arm-specific optimization. Both independently prepared control/candidate must receive the same pinned patch, before the combined shadow/format selection in the matched audit (#108). Verify both input blobs, exact output blobs, reverse/diff check and whole inventory; only host.rs and texback.rs change in each common step. Recompute complete per-arm hashes and common inventory digest; cross-arm differences must still be only the already authorized optimization paths (shadow.rs and victory-formats/src/texture.rs) for the previous matched design. If another accepted common repair changes host.rs or texback.rs preimage, fail closed and coordinate exact composition with AI1; do not fuzzy-apply or claim hash equality for a different composition. Recheck all seven matched route blocks, actual effective flags and fresh binary provenance, no old parity/binary receipt reuse.

R3/common delivery outcome/real remap/concurrent failure/landing/notification remain separate. No new CI registration, production integration, owner machine or title run, gameplay/FPS or merge. #71 HOLD all24 open.
