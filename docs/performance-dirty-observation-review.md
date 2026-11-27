# P13/P14 review-only baseline observation hooks

This is a narrow first measurement step, NOT production dirty tracking.
Proposal only; `tools/propose_dirty_observation.py <prepared-root>` prints
an in-memory diff, fails on missing/duplicate anchors, never writes source.
No runtime registration, new flags in a built renderer, GPU changes or
cache changes. Coordinator D10 review required.

Pinned source `51700c6d43a3507fa65e50fe4bb64074ce706cd4`; mask snapshot `c074896b1bfd87def17c91c901bf0e9ccf56263f`.
Four exact proposed anchors were verified against pinned source; three
shadow hooks also checked after applying all 6 replacement pairs from
the mask snapshot's copy patcher to pinned shadow.rs. This is not full
prepared-tree composition. Coordinator must repeat against fully prepared
snapshot before authorizing.

* shadow.rs::copy_back_with: before back_piece, only already selected
  differing pieces. This sample set is deliberately biased toward changes.
* shadow.rs::card_merge: before first_difference, existing GPU and old slices.
* shadow.rs::card_merge_relay: before first_difference, existing GPU and held
  slices, under existing before lock. No new locks or callbacks into memory.
* copystat.rs::log: numeric cumulative snapshot through existing log path.
  Check caller-held lock context before approval; no new I/O in sample hooks.

Proposed diagnostics-only switch VICTORY_DIRTY_OBSERVE=1, default off.
OnceLock caches flag. No new work on shader paths, root signatures, shader
or pipeline cache keys. At most 4096 admitted samples process-wide, at most
64KiB per sample; bounded 256MiB of slice length (two input reads per
comparison, potentially 512MiB read traffic), no allocations or retry loop
in sampling. Single CAS admission can lose samples on contention; not
representative or exhaustive. The enabled extra comparison can perturb
timing; do not use it for final performance acceptance. No new waits,
transfers or modifications of any baseline result. Release build excludes
hooks.

Proposed numeric line (no addresses/data):
`dirty_observe_v1 path=0 samples=... bytes=... chunks=... unequal=...`.
Path 0 = selected copy-back pieces, 1 = card merge, 2 = relay card merge.
Cumulative per-process, fields independently loaded, possibly inconsistent
while updates are in flight. Chunks are 4KiB slice-relative units, NOT
physical pages or unique pages; overlapping/repeated slices may be counted
twice. Unequal bytes may reflect CPU changes, not proven GPU-only writes.
No division into frames, exact miss rate, per-flight coverage, actual
transfer bandwidth or skip eligibility. AI3 review of allowlist/aggregation
needed before reporting changes. True bitmap vs complete authoritative scan
still requires stable backing lease, complete writer proof and same-flight
completion. AI1 owns alias projection and generation publication. Readback
writes must publish their own mutation under reviewed guard before visibility;
no production publication hook proposed.

Four portable helper cases and two preview tests. No native compilation
of composed source, GPU data or FPS evidence. Exact proposed edits only.
