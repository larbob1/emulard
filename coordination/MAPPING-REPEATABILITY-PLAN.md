# D24 — Mapping repeatability pilot (review draft, not execution authorization)

## Evidence and scope

Frozen #18 dbac4c6ea21d9580f5b0bd39ba2b9d6c4eb6f2b1; upstream 51700c6d43a3507fa65e50fe4bb64074ce706cd4. Exact revised #49 fa855ee6a3c03f6eb5128651f6af44c2cf949847 native36/36; exact #54 ee24b252c86d68d2cda2b865f97cbf08c8f97656 native45954916422 job140360673031: 40 test invocations plus two builds, all 42 passed. Eight mapping diagnostic invocations, four distinct cases each in explicit mode0 and1, exact1/0 per case. AI4 independent prepared/split review #27 7211994309. These establish bounded synthetic correctness, not a production timing budget or all rollback/fallback paths. D24 design criteria #11 7211599502.

## Stage A: frozen/frozen repeatability design

Propose one identical test-only harness and the same pinned frozen source/build profile for both A and B. Compare two fresh processes of the same binary, not frozen release against candidate diagnostics. Record exact harness, prepared xmem, build/profile, executable identity and runner environment class; require all non-diagnostic mapping switches identical and explicit. No title, actual GPU workload, raw path, address, or machine-identifying output. Do not alter frozen branch; any later authorized harness lives in a new isolated child. Before implementation AI4 and AI3 review the operation table, source seam, receipt and statistical design.

Proposed initial balanced pilot: six matched sets, alternating A/B then B/A order (three each); fixed five untimed warmup batches and ten measured batches per arm per mix, within D24 maximum twenty. These are design choices for review, not measured requirements. Fresh processes for each arm/set; identical deterministic generated data and batch operation counts. No production switches, adaptive repeat counts, affinity changes or instrumentation inside PHYSICAL. Timer brackets each whole batch, not the lock. Record integer nanoseconds, positive clock resolution, and separate empty timer-bracket control; don't subtract it as if exact overhead. Initialization, validation, oracle and cleanup outside timed batch where possible; unavoidable setup inside the operation is declared. No external logging in timed section.

| Mix | Proposed single batch | Correctness oracle outside timed interval |
|---|---|---|
| Read-only | fixed repeated existing physical read-only guard path on identical state | no map mutation, same tracked views and bytes |
| Known no-change | repeat a known unchanged operation proven by existing fixture; no injected corruption | exact expected outcomes and no state change |
| Map/unmap | fixed allocation setup outside timer; balanced real map/unmap cycles | exact mapped bytes, view cardinality, reverse-index reconstruction, clean teardown |
| Alias | fixed source/destination backing and balanced alias/unmap cycle | shared backing bytes, exact reverse entries and cleanup |
| Interior split | recreate a real contiguous three-page view, public middle unmap, then remove retained neighbors | assert actual three-page input and two one-page neighbors, known bytes, no leftover views |
| Reader contention | fixed deterministic per-participant operation counts, bounded start/end gates; repeat equivalent worker mix | actual counts/outcomes and final state, no deadlock; report scheduling variability, not lock hold duration |

Before fixture authoring, specify exact operations per batch and setup/teardown boundary for each mix from frozen prepared symbols; do not choose a batch size based on candidate timing. The interior split path must use the same real-map precondition discipline as #54; don't time the diagnostic oracle or compare a fallback shape. Contention requires separate pilot stratum; no sleeps treated as exact timing or forced scheduler claims. Bound per-case allocations and enforce cleanup, bounded wait/watchdog and fixed operation counts. Failed or unavailable arm invalidates entire matched set; retain failure and missing coverage, never replace quietly.

## Numeric receipt contract proposal (AI3 review required)

One record per expected batch with set, arm, order, mix, warmup/measured indicator, batch ordinal, requested/completed operations, outcome enum, elapsed_ns (nullable for failure) and correctness/cleanup indicator; receipt header carries exact identity and expected matrix. Record empty-bracket controls separately. A complete receipt must match the unique expected matrix, finite bounded unsigned integer counts, all expected outcomes and final oracle; reject duplicates, missing rows, clock reversal/overflow, incomplete cleanup, mismatched identities and partial sets. Retain incomplete sets with explicit reason and do not call them measurements. No raw logs, addresses, title content, absolute timestamps, or cross-clock arithmetic. This is not a schema implementation.

## Interpretation and next decision

For each mix separately, report per-arm batch wall-time p50/max and operation counts, matched set-level A/B median differences, median/range across sets, signed order-stratified differences and empty-bracket control/resolution. Use ratios only when meaningful positive denominators; distinguish batch time from mutex time and no pooled per-operation p95. Do not exclude outliers or infer equivalence from six sets. Pilot estimates repeatability/noise floor only; no candidate comparison, threshold or numeric budget is set here.

After a separately authorized pilot with reviewed actual receipt, AI3 and coordinator/owner preregister fixed absolute AND relative per-mix overhead budget before a distinct confirmatory frozen/off/on test; rotated order, identical profile/runner/workload and same fixture semantics. Candidate changes require exact native correctness and identity recheck. If pilot is too noisy, report unresolved and revise design before new authorized sets; do not tune acceptance after seeing candidate effects. Output worker, cross-clock bridge and protected gameplay remain separate D24/D22 gates. No runtime implementation, new CI execution, local test or merge authorized by this draft.
