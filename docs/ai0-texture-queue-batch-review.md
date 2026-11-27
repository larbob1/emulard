# EXT-17 — texture queue batching review

Review only. [Scope claim](https://github.com/larbob1/emulard/issues/55#issuecomment-7225014577).

## Source

External [batching abf1020](https://github.com/trustno1-coder/VIctory-NVIDIA/commit/abf1020d25e46da6974f173bff08c89c990cfc49) batches 16 outcome notifications and captures checked metadata with due slots; [marks 2ad55e6](https://github.com/trustno1-coder/VIctory-NVIDIA/commit/2ad55e65b3832063d524394755310af761ffe1a3) adds per-slot atomic write marks and skips some mutex acquisitions. These are newer source, not prepared Emulard. External Windows timings are not transferable and are not additive. The external sequential-equivalence test can return when no host GPU is available.

Pinned 51700c6d43a3507fa65e50fe4bb64074ce706cd4 descriptor/host.rs 7970fc5f0c3977bde0a81dbcec1a497384b933bc: TextureQueue530, same593, later605, hold623, room633, partly649, recheck657, checked665, changed672. draw.rs 41380c23a61b93000c4886265c3063676ddc4864 heap_textures1842, room/remap/waiting/due1890–1899, budget break, checked1977, hold/refusal, removal return and final recheck/done. Pinned census and scheduling differ. The [RTX asynchronous attempt changes abb8adf](https://github.com/aleksesipenko/VIctory-RTX/commit/abb8adf362094e93406152d95f9587e22138facb) concern a distinct newer upload-ahead system; no port proposed.

## Distinct correctness questions

Write identity already rejects superseded outcome notifications. It does not change when same-write metadata is updated. A cached fingerprint/looks/uploaded tuple may become stale without a mark mismatch. If a room event occurs between preparing and flushing Held, the final retry deadline may differ from immediate notification. These are conditional interleavings of the raw queue operations, not observed concurrent gameplay failures; establish actual pass serialization, legal linearization and acceptable delay before enabling batching. A metadata-only lock optimization must not infer that texture content, GPU staging ownership, or upload success is established by a mark.

Do not assume batching is behavior-neutral merely because a sequential final-state test passes. Test real call graph, due order and budget limits, duplicate processing, concurrent passes, remap/rewrite/remove/recheck, room events, heap replacement, every break/return and panic path, bounded pending outcomes, fairness and the lifetime of staging/descriptor owners. Decide whether a batch should flush before an event, invalidate cached metadata, or defer only independent notifications; do not select a runtime policy here. Avoid unconditional Drop-time successful publication on failure. Any marks require complete mutation accounting, memory ordering, overflow/nonreuse and heap identity review. No new shared telemetry or benchmark policy.

Native review gate: recover actual prepared source including #35/#76 descriptor and #79/#80/#83 lifetime/mapping proposals, establish the real queue/lock and upload receipt contract, actual native tests with deterministic interleavings and explicit capability receipts, CPU/GPU correctness, AI1/AI2/AI3 review, AI5 upload dependency and AI4 disposition. Only then evaluate fixed explicit modes with matched Proton workload and lock wait, critical-path frame time, backlog age, staging bytes, rendered parity and peak memory. No claim of a leak or performance gain.

Standalone model: python -m unittest discover -s tools -p test_ai0_texture_queue_batch.py . This tests a subset of queue state transitions, not real mutexes, upload jobs, due ordering, or native GPU execution. Five tests; counterexamples are expected observations in the abstract model, not actual runtime faults. No runtime, flag, builder, CI or title access changes.
