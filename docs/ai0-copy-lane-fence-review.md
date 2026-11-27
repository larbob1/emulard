# EXT-06 — copy-lane fence and ownership seam

Review only. No runtime, builder, flag, or CI changes. [Claim](https://github.com/larbob1/emulard/issues/55#issuecomment-7224672173).

## Existing work and source

AI2 #35 exact defd471105f90fce0849f15251154135a94e81b4 already models sticky removal, domain-scoped receipts, partial publication and monotonic reservation. Its source audit in #12 comment 7212059798 is retained; this proposal does not replace it. The external [RTX fix](https://github.com/aleksesipenko/VIctory-RTX/commit/3e7555570c18f3d4cc3b60576c1fa1870354ecca) concerns synchronous host completion and a different list architecture. No thin-list leak attribution or blanket backport.

Pinned raw upstream 51700c6d43a3507fa65e50fe4bb64074ce706cd4:
- queue2.rs 6d016d270e6de310231f7cbc4c470c3373910c79.
- host.rs 458d146aedf6f13dac80782d283a048d80e4a931.
- host.rs 9181 is test-only, not an extra production query.

| Seam | Raw lines | Specific risk to verify |
|---|---|---|
| Lane::list | 223–240 | Numeric completed sentinel selects spare allocator/list for reset. |
| Lane::send | 255–277 | ExecuteCommandLists precedes sent increment, fallible Signal, then spare ownership registration. Signal error can exit before the local CopyList is moved into spare. |
| Lane::done / wait | 283–297 | Sentinel appears complete; wait result and post-wait query not verified. |
| Second::landing / pick_landing | 384–440 / 106–114 | Sentinel can permit reuse and evict every old landing under budget pressure. |
| Second::sent_up / order_done | 445–455 | Signal error ignored; order completion is a distinct fence domain. |
| host::landable / relay_worker | 2276 / 3345 | Sentinel selects numeric flight prefix, including dependent writes; review later device check and ownership after drain. |
| Host landing caller | 4196 | Direct-fence completion feeds buffer pool eligibility. |

The post-execute signal gap is a source-level ownership concern, not proof that a device failure occurred or that COM destruction is currently unsafe: caller pins, failure termination, pending references and the actual prepared call graph must be checked. The model intentionally does not prescribe indefinite retention, retry, rollback, teardown, or fatal process policy.

## Review gates

1. Recover exact prepared host, queue2, shadow, texback and list. Reconcile with #35's source pin gate; distinguish direct, up, down, order and epoch domains and the actual producer of each fence. Check actual signal admission, reservation overflow, failed dependency waits before Execute, signal failure after Execute, and subsequent publication.
2. Verify an explicit owner for submitted-but-unconfirmed command list, allocator, upload/readback and destination resources. Before Execute, error can leave work not submitted; after Execute, signal failure alone cannot prove not submitted or completion. Do not simply retry or return resources to a free pool. Select bounded terminal/failure ownership disposition with AI1/AI2, not an unbounded quarantine.
3. Native injected receipt fixture, not deliberate device destruction: separate pre-execute failure, post-execute signal failure, event registration failure, non-success wait, stale query, removal sentinel, later apparent success, valid completion. Validate exact ownership and no allocator reset, landing eviction, CPU publication or resource retirement on unknown completion. Check normal smallest-fitting reuse and memory budget behavior unchanged. Distinguish telemetry from ownership.
4. Native success/failure path with up/down/direct dependencies and exact confirmed prefixes, no foreign fence reuse, no silently omitted texture/compute readbacks. Require both builds, independent review, native receipts and AI4 disposition. Actual GPU/device-loss testing is not requested here.

Standalone: `python -m unittest discover -s tools -p test_ai0_copy_lane_ownership.py`. Six proposed arithmetic/ownership tests; no actual GPU, concurrency or runtime recovery. The model stops at reuse eligibility; it does not demonstrate safe teardown after an already-completed owner is reused. No FPS claim.
