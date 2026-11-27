# Pre-gameplay Phase 1 — actual submission-path readiness

Claim [#11 7228730153](https://github.com/larbob1/emulard/issues/11#issuecomment-7228730153); integration e1d2ecb65f901f1446c99346dcc15fb0e69ab474. Owner approved staged preparation, not an unrestricted title launch. AI0 and AI2–AI6 remain paused until the Phase 1 review checkpoint. D17–D25 restrictions remain; AI4 alone may access owner machine.

## Required evidence before specialist handoff

| Gate | Exact candidate | Status at snapshot |
| --- | --- | --- |
| Production-only control and combined | #96 5c961054125590ab0ece0484154602a235f0f81c | Native 46071731073 jobs 140750029589 (000) and 140750029858 (111) running; synthetic 113+4 passed |
| Actual owned memory recording | #97 039443cee6188670e60f662ef3c945da894dabbf | Native 46071978926 job140750838373 running; synthetic 46071978742/job140750837597, merge5f2c062 into159d0ef, 113 Python+4 range passed |
| Actual deferred refresh preparation | New exact fixture after owned-memory gate | Not implemented/executed; detailed scope below |
| Queue/fence/lifetime review | AI1 source review, AI2/AI3 review upon resumption | Outstanding; no permission to use title or owner machine |

Earlier #87–#94 scoped passes, #95 all eight source configurations, and all individual holds remain valid at exact heads. #96 is a scratch candidate, not a release. The previous owner-authorized pressure-stopped title tests do not authorize repetition.

## Source audit and bounded next native fixture

Pinned upstream 51700c6d43a3507fa65e50fe4bb64074ce706cd4:
- host.rs 458d146aedf6f13dac80782d283a048d80e4a931: submit5421+, holds submitted lock through preparation; runs deferred lists in supplied order5519+, flushes all pending refreshes before take_snapshots and ExecuteCommandLists. run_deferred7067+ adds refreshes; GpuWrite flushes the same copy before writing snapshot; Run invalidates current refresh coverage. Batch7257+, dedup by Arc identity, union of pending ranges, flush_one and flush.
- shadow.rs 4fa43df7932bb6692d164384cd28b1f08f3001ee: update3456+ clamps range and excludes pending GPU writes, update_free chooses write-watch or copy, copy3617+ copies into its own host mapping. preparing801+ and copy_back2900+ have separate submission/snapshot/merge state. Do not set global flight counters or fabricate successful fence completion.
- #97 fixture uses a three-page owned VirtualAlloc allocation, actual registered shadows and explicit ownership guard. Require exact native receipt before reusing the fixture. No arbitrary address query, no scans, no title memory.

Proposed first implementation (separate scoped claim after #97 result):
1. Reuse exact reviewed fixture preparation and canonical #71 old/new final-loop substitution. Fresh process per mode; explicit software adapter, inplace/card/late/wide refresh off, both committed query modes where supported; refresh_once off/on separately if independently justified. Assert all registered spans and resource lifetimes. No GPU commands or writes in this first test.
2. Add cfg(test) helper in actual HostList/host module to run the real run_deferred over a local Batch in supplied order and flush. Prevalidate every Step is Refresh, its Arc identity matches fixture registry, checked span is fully within allocation; reject all other steps before any call. Use actual Shadow::update, not a counter or mocked update. A test-only Shadow helper copies its owned CPU-visible mapping into a bounded byte snapshot. No callbacks, raw GPU writes, or fake submission/fence.
3. Start with owned CPU pages with distinct deterministic bytes, initialize host copies to different sentinels, assert initial and final byte arrays independently (not just compare variants). Record A names page A, B names page B, A repeats; directory publishes B but A's registration lacks it in both variants. In fresh variants execute preparation A only; expect A current and B unchanged sentinel, record shared preexisting coverage gap. For one batch containing A,B and reverse B,A, expect both refreshed before GPU queue would execute. For two separate batches A then B / B then A, capture each batch's byte result and record shared assumption. Do not label missing registration a proven gameplay fault; don't silently repair it as part of #71.
4. Verify no deferred or retained reference escapes, close and drop lists, drop Memory before heaps, unregister only fixture entries and free owned pages. Compare full original/candidate receipts with address-independent stable identities, exact debug/release diagnostics tests and watchdog. No timing or FPS extrapolation.
5. Separate actual queue/fence gate later: require independently reviewed closed command list and bounded fence wait with failure handling, no title launch; actual copyback and any GPU writes require explicit separate ownership and fence-domain proof. Existing late/relay paths remain excluded. A CPU batch pass cannot establish queue/fence/lifetime correctness or approve #71.

## After Phase 1

Only when outstanding failures are resolved and remaining correctness coverage is explicitly dispositioned, send exact evidence and blockers to AI2/AI3/AI5/AI6; AI4 receives review-only local readiness request. Owner resumes specialist agents separately. AI0 stays paused. No automatic merges, no frozen candidate until affected owners and AI3 review, and no local launch until a specific safe plan consistent with D20–D24 is authorized. Retain prior protected working build as rollback. Formal FPS evidence requires correctly rendered gameplay and matched repetitions; no synthetic time or test count substitutes.
