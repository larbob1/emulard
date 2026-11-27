# Road to 30 FPS

**Goal:** sustained, correctly rendered and responsive gameplay at 30 FPS on a reproducible reference configuration. This is an engineering target, not a forecast or a current claim.

The reported 1–3 FPS corresponds to roughly 333–1,000 ms/frame. 30 FPS requires an average frame duration of about 33.3 ms: roughly a 10–30× improvement over that starting observation. Historical diagnostics suggest large host mapping stalls, but there is no current matched benchmark proving how much each component contributes to the critical path.

The [canonical deferred-work register](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/performance-deferred.md) retains IDs P01–P24 and detailed evidence. This main-branch roadmap is a prioritized planning view. No item is closed by appearing here; update the canonical register with evidence before closing it.

## Reference configuration and benchmark protocol

Start with the RTX 5060 Ti / Series S configuration documented in the compatibility branch's earlier experiments (record actual CPU, RAM, VRAM and driver before testing). Use the same authorized local workload, Series S profile, resolution, render scale, graphics settings, OS, Proton/driver version, runtime commit, and cache state. Record the exact actual configuration; no specific resolution is assumed here.

1. Pass synthetic, Windows runtime, release/diagnostic build and Proton smoke checks.
2. Choose one repeatable scene with actual world rendering and input; record camera path/actions and fixed warmup. Keep capture off during timing.
3. Record cold-cache startup separately from steady-state runs. Compare flags individually against an unmodified configuration of the same commit/profile.
4. Collect at least three matched baseline/candidate runs, using elapsed wall time and correctly displayed frame counts, individual frame-time batches, p50/p95/p99, drops/refusals, CPU/GPU usage, VRAM/RAM, disk activity and critical-path timing.
5. Use numeric reports from `frame_report.py` and `benchmark_pairs.py`; keep raw logs, addresses and game assets local. Detailed frame batches are rounded to milliseconds; interval averages are not individual-frame percentiles. Do not add overlapping worker durations.

## Milestones

| Gate | Target average frame duration | Exit condition |
| --- | --- | --- |
| M0 — Build | Not applicable | Both profiles compile; selected suites pass with no empty filters |
| M1 — Correct scene | Not applicable | Full scene and UI render; input works; no missing required draws/pipelines or invalid memory accesses in workload |
| M2 — 5 FPS | 200 ms | Repeatable visible gameplay with no correctness regression |
| M3 — 10 FPS | 100 ms | Same workload and validation |
| M4 — 20 FPS | 50 ms | Same workload and validation |
| M5 — 30 FPS | 33.3 ms | Final acceptance below |

Proposed final acceptance: three repeatable 10-minute steady-state runs at an average of at least 30 correctly displayed frames per second, measured as frames divided by elapsed seconds; p95 frame duration at most 50 ms, p99 at most 100 ms, no crash, no black scene, no known missing required draws, and responsive controls. Record cold-cache behavior separately. These are initial engineering criteria, not measured results; revise them transparently if the workload requires different criteria. The result applies only to the tested workload and hardware.

## Priority 0 — Stabilize the cumulative runtime

**Blocker: no validated cumulative release.** Do not stack production architectural rewrites into a failing baseline.

- [ ] **P24** Resolve the Windows split/restore mapping assertion and any remaining CI failures; inspect the exact suite/mode results and fix causes rather than weakening assertions.
- [ ] **P01** Compile both runtime profiles, run all selected suites in off/on modes, validate native Windows and Proton aliasing, memory protection and regression fixtures.
- [ ] **P08** Run deterministic and captured tile replay on the paired-wave runtime; compare backing views, cross-page reads, repeated/overlapping aliases and detiling.
- [ ] **P06** Finish checked map/commit/unmap handling, failure cleanup and transactional recovery (or explicit documented non-transactional semantics); inject failures and verify no stale bookkeeping.
- [ ] **P02 / P03** Establish a reproducible benchmark and actual critical-path instrumentation. Record wall-clock waits separately from worker totals, and compare native Windows versus Proton.
- [ ] **P16** Reproduce missing required shader operations and pipeline creation methods; validate visible scene correctness before accepting an FPS result. Continue detailed shader work in Priority 3.

**Exit:** known mapping failures resolved, test evidence linked in register, both builds available and a repeatable correctness workload.

## Priority 1 — Remove host virtual-memory churn

This is the strongest currently documented bottleneck. Focus on reducing real host operations, not just requested page counts.

- [ ] **P05** Complete placeholder interval tracking, split/coalesce state, and exact reuse; verify the split/restore fallback and compare actual host call counts. Validate the isolated ordered-set reverse-alias candidate before integrating.
- [ ] **P07** Batch changed scatter requests, preserving request order, duplicate-address semantics, alias writes and failure behavior.
- [ ] **P04** Design and implement software GPU tile page tables for GPU-only mappings. Audit every CPU dereference, keep CPU-visible aliases correct, and retain a tested host mapper fallback.
- [ ] **P10** Introduce lifetime-pinned backing sections with stable identity, generation and retirement tied to readers and GPU completion; protect against handle reuse.
- [ ] **P09 / P12** Integrate range-based reader/writer synchronization and per-range generations. Expand writes to full affected host views; audit free/protect paths, alias invalidation and lock ordering. Keep the global guard until migration is proven.
- [ ] **P11** Validate short-lock snapshots against old data, concurrent remaps and retry starvation; measure whether copies cost less than reduced waiting.

**Exit:** replay/alias equivalence, failure-injection tests, no access violations; demonstrably lower mapping call count and wall-clock mapping waits on matched workloads. Aim for M2 then M3 only if measurements support it.

## Priority 2 — Reduce GPU transfer and synchronization overhead

- [ ] **P13** Implement submission-owned GPU dirty bitmaps with complete shader store/atomic coverage, descriptor lifetime management, fault handling, alias notifications and completion fences. Keep exact fallback for uninstrumented writes.
- [ ] **P14** Reduce synchronous readbacks, copy-back bandwidth and redundant hashing. Introduce fence-safe asynchronous transfer/readback scheduling and validate exact visibility.
- [ ] **P15** Improve persistent resource residency, staging reuse, texture upload and detiling efficiency; budget RAM/VRAM and handle pressure without freeing live resources.
- [ ] **P21** Finish AVX2/sparse merge/mask and idle pool integration tests. Portable helper equivalence has passed; verify real GPU integration, allocation churn and timing.

**Exit:** byte-for-byte correctness across GPU writes and aliases; reduced transferred bytes and critical-path copy/queue waits; no additional stale frames or memory pressure regressions. Aim toward M3/M4 after profiling.

## Priority 3 — Shader and pipeline correctness/performance

Rendering correctness also gates M1; do not delay required shader fixes simply because this optimization group is listed third.

- [ ] **P16** Implement or correctly handle unsupported wave operations, waterfall loops, FidelityFX descriptor mutation and missing pipeline methods (reported slots 0x1c8 and 0x218). Preserve exact paired-wave semantics and synchronization.
- [ ] **P17** Audit shader and pipeline cache keys, host wave specialization, worker stack stability, cross-process cache ownership and dropped draws.
- [ ] **P22** Fault-inject cache serialization/rename failures; validate concurrent saves, restart/driver rejection, scheduler fairness and cold/warm compilation.
- [ ] **P18** Port validated render-target/descriptor/command-list caching only with correct state invalidation and resource lifetime. Profile CPU contention and GPU occupancy before specialization.

**Exit:** required pipeline creation and shader replay succeed; correct render output; measurable reductions in warm pipeline stalls and CPU recording work. No force-barrier or skip-draw shortcuts.

## Priority 4 — Tune, integrate and verify 30 FPS

- [ ] **P23** Compare automatic vs 2/4 storage workers and independent pipeline worker caps; record throughput, queue starvation and frame latency.
- [ ] **P18** Evaluate release optimization, profile-guided optimization and native Linux backend feasibility only if critical-path evidence justifies the work. Native Linux is a separate potentially large project, not a prerequisite for 30 FPS unless measurements show it is necessary.
- [ ] **P19** Consolidate validated fixes into a coherent runtime branch, port to other pinned variants where compatible, document defaults and rollback; run end-to-end CI and release tests.
- [ ] **P20** Verify M2–M5 on actual hardware and publish reviewed numerical results and correctness evidence. Do not report black frames or dropped required draws as gameplay.

**Exit:** satisfy the final M5 acceptance gate and record the tested commit, settings, hardware, results and remaining compatibility limitations.

## Illustrative frame budget (not measured)

A possible starting budget for **non-overlapping critical-path** work is 8 ms CPU/HLE + mapping, 4 ms texture/transfer synchronization, 18 ms GPU rendering, 3.3 ms presentation and other overhead. Parallel stages may overlap; use actual traces to revise this allocation. It is not an instruction to remove safety waits or a prediction that these budgets are attainable.

## Status snapshot

At the time of writing, all 24 deferred IDs remain unresolved. Phase 6 synthetic CI passed 107 Python tests, 4 range-gate tests and 10 portable copy-helper executions at `8956a8e`. Native runtime and gameplay acceptance remain unverified. The authoritative [register](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/performance-deferred.md) and [Actions](https://github.com/larbob1/emulard/actions) should be used for live evidence.

Every completed task must identify the validating commit, test/benchmark command, outcome and remaining caveats. Keep unfinished tasks listed. If a prototype fails to improve performance or breaks correctness, revert or leave it disabled rather than promoting it.
