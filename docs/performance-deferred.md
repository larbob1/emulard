# Performance deferred-work register

This register is cumulative across the six performance phases. Keep the
same IDs in every later branch. An item is not closed by writing code:
record the validating commit, tests, and measured result (where relevant).
Keep unverified experiments opt-in. Review all open items at the end of
Phase 6; do not erase unresolved items or equate implementation with FPS.

| ID | Origin | Status | Outstanding work / acceptance evidence |
| --- | --- | --- | --- |
| P01 | 1 | Open | Compile the paired-wave candidate, run phase 1/2/3 tests on Windows and Proton, including aliases, partial failures, concurrent readers and replay. Record real results. |
| P02 | 1 | Open | Matched scene benchmarking after warmup with capture off; collect frame wall time, median and tail latency, dropped draws, GPU/CPU utilization and mapping counts. Compare native Windows and Proton. |
| P03 | 1 | Open | Critical-path instrumentation distinct from overlapping worker totals; extend numeric reports for later counters and percentile samples. |
| P04 | 2 | Open | Software-only GPU tile page mappings; audit direct CPU dereferences, preserve CPU-visible aliases and validate copy/readback ownership. |
| P05 | 2 | Open | Full placeholder interval tracking and coalescing/splitting optimization; demonstrate fewer host calls on captured workloads. |
| P06 | 2 | Open | Transactional mapper failure recovery, checked map/unmap results, rollback or documented failure semantics; fault-injection tests. |
| P07 | 2 | Open | Batch changed scatter operations without changing ordering, duplicate-address behavior, or failure semantics. |
| P08 | 2 | Open | Port captured tile mapping replay and backing-view comparison to paired-wave runtime; exercise partial and overlapping aliases. |
| P09 | 3 | Prototype | Range-aware locking: migrate audited runtime writers and readers to scoped gates; protect complete views reconstructed by unmap, handle alias invalidation and lock ordering. Prototype in probes/range_gate.rs only. |
| P10 | 3 | Open | Lifetime-pinned backing views with section identity/generation and retirement; no stale handle reuse or memory lifetime violations. |
| P11 | 3 | Candidate | Validate bounded texture snapshots and generation retries; measure lock wait vs added copy cost, stale snapshot behavior and starvation. Retain original path. |
| P12 | 3 | Open | Replace global epoch with per-range generations, validate all mapping and free/protect paths and non-overlapping reader concurrency. |
| P13 | 4 | Open | Production completion-scoped dirty tracking; integrate per-flight descriptors, faults, atomics, alias notifications and completion fences. |
| P14 | 4 | Open | Reduce synchronous readback/copy-back and redundant buffer hashing; maintain exact visibility and fence semantics. |
| P15 | 4 | Open | Persistent resources, staging reuse, async transfers, texture refresh/detiling optimization and VRAM/RAM budget validation. |
| P16 | 5 | Open | Unsupported shader operations, paired-wave semantics, waterfall loops, FidelityFX descriptor mutation, missing pipeline methods; ensure scene rendering correctness. |
| P17 | 5 | Open | Persistent pipeline/shader cache correctness and performance, compile worker stability, native-wave specialization, dropped draws. |
| P18 | 6 | Open | Descriptor and command list caching, storage worker tuning, release/PGO evaluation, native Linux backend feasibility. |
| P19 | 6 | Open | Consolidate validated improvements across runtime variants, improve CI and run end-to-end correctness/performance acceptance; close only with evidence. |
| P20 | 6 | Open | Verify sustained visible gameplay at target milestones (5, 10, 20, 30 FPS); do not count black frames or dropped draws as playable. |

## Current state

Phases 1 and 2: opt-in implementation candidates committed; no runtime
compilation or gameplay measurements independently verified here.
Phase 3: short-lock snapshot candidate and standalone range-gate prototype.
The global mapping lock remains the production safety mechanism.
Phases 4–6 are not implemented. Keep this register updated in each phase.
