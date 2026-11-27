# Decisions

D01: main stays novice-facing documentation; runtime development remains on Phase 6 and separate candidates.
D02: owner approves merges; coordinator alone updates integration and canonical tracking. No history rewriting.
D03: existing working Proton setup is preserved. New features opt-in; no false performance claims.
D04: host mappings remain authoritative until GPU-only classification, backing pinning, read/write/fence correctness and replay equivalence are proven.
D05: benchmark same scene/build profile/settings/cache, repeat at least three times for formal claims. FPS only counts correctly visible gameplay.
D06: coordinate by actual prepared upstream symbol, not only integration patch filename. Shared build/CI changes require agreement; separate worktrees.
D07: do not store private logs, credentials or proprietary content; use synthetic fixtures and reviewed numerical summaries.

D08: P13/P14 AI2 test-only model approved (#12 comment 7210284097). AI1 owns xmem backing identity/leases, reverse aliases, external mutation/snapshot guard and P12 Generations::mark/invalidate_all. AI2 owns submission writer coverage, fence-domain tracking, handback/readback, ordered title signals. Pending GPU writers require synchronization separate from generation validity; after actual mutation, publish complete alias footprints under shared guard before consumers/signals; unknown/partial mutation invalidates conservatively. Fence completion alone does not authorize retirement. No waits under mapping/range locks; no production overlapping edits until exact hunks, coverage and lock order reviewed.
D09: AI3 CPU-only trace proposal conditionally approved (#13 comment 7210302700) for bounded portable TLS/output-queue/concurrent-present model. queue.rs execute/present require AI2 agreement; frame.rs wait/framelog observation-only anchors approved in principle, exact hunks and registration require coordinator review. No GPU causality or displayed FPS inference. PGO scheduling remains deferred.

D10: P12 complete alias publication cannot use inplace::views_of_section because it intentionally skips MANY_VIEWS; tracked mirror projection is a test-only proof, not authority for untracked writes. HLE PHYSICAL -> renderer MAPPING lock order must not be reversed; MAPPING only excludes remapping, not arbitrary writers. Readback writes occurring after handback require their own publication before visibility/signals. Observation-only buffer dirty comparison direction agreed, exact prepared hunks still need approval (issue #12 comment 7210363186).

D11: AI4 assigned #27 and dev/performance-phase6-local-validation; P01/P02/P03/P20/P23 local evidence only, AI3 retains tools/acceptance. Strict read-only original title isolation, lawfully accessible content only, separate writable runtime directories, no circumvention or proprietary upload. Existing historical setup preserved; supervised baseline first, exact #18 all switches off next, individual switches then matched repetitions. Loading-screen presentation not gameplay. System changes/installations require owner approval.
