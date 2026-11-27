# Performance deferred-work register

This register is cumulative across the six performance phases. Keep the
same IDs in every later branch. An item is not closed by writing code:
record the validating commit, tests, and measured result (where relevant).
Keep unverified experiments opt-in. Review all open items at the end of
Phase 6; do not erase unresolved items or equate implementation with FPS.

| ID | Origin | Status | Outstanding work / acceptance evidence |
| --- | --- | --- | --- |
| P01 | 1 | Open | Compile the paired-wave candidate, run phase 1–6 tests on Windows and Proton, including aliases, partial failures, concurrent readers and replay. Record real results. |
| P02 | 1 | Open | Matched scene benchmarking after warmup with capture off; collect frame wall time, median and tail latency, dropped draws, GPU/CPU utilization and mapping counts. Compare native Windows and Proton. |
| P03 | 1 | Candidate | Numeric report adds interval percentiles, selected long-frame and omitted counts, and FPS milestones. Full per-frame distribution, later counters and critical-path attribution remain open. |
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
| P14 | 4 | Candidate | Optional exact AVX2 scan and sparse merge are implemented; benchmark and validate. Actual GPU readback bandwidth, redundant hashing and synchronization reductions remain open; maintain exact visibility and fences. |
| P15 | 4 | Candidate | Optional hard idle snapshot budget implemented; validate memory pressure and allocation churn. Persistent resources, staging reuse, async transfers, detiling and VRAM/RAM budget validation remain open. |
| P16 | 5 | Open | Unsupported shader operations, paired-wave semantics, waterfall loops, FidelityFX descriptor mutation, missing pipeline methods; ensure scene rendering correctness. |
| P17 | 5 | Candidate | Process-local cache save serialization and retry bookkeeping, optional bounded requested-graphics bursts and compiler worker count implemented. Persistent shader cache key coverage, cross-process cache ownership, compile worker stability, native-wave specialization and dropped draws remain open; validate. |
| P18 | 6 | Candidate | Opt-in paired-wave DirectStorage worker cap implemented. Descriptor/command list caching, release/PGO evaluation, native Linux backend feasibility and measured worker tuning remain open. |
| P19 | 6 | Candidate | Stacked paired-wave integration and Windows compile workflow added; builder patch overlap corrected. Actual compile and end-to-end results, and other runtime variant ports remain open. |
| P20 | 6 | Open | Verify sustained visible gameplay at target milestones (5, 10, 20, 30 FPS); do not count black frames or dropped draws as playable. |
| P21 | 4 | Open | Validate Phase 4 scalar/AVX2 equivalence, sparse merge conflicts, exact mask runs, idle memory cap and CPU/RAM/transfer telemetry; benchmark each switch separately and together. |
| P22 | 5 | Open | Validate cache publication under concurrent periodic/forced saves and injected serialization/rename failures, restart and driver rejection; test scheduling fairness, compiler contention, cold/warm cache frame times and dropped draws. |
| P23 | 6 | Open | Validate the storage worker cap against default and multiple caps; confirm throughput, queue starvation, frame times and safe completion under Windows/Proton. |
| P24 | 6 | Open | Repair any remaining compile/CI failures; verify the builder anchor fix and all cumulative source patches on pinned checkouts. |

## Current state

Phases 1 and 2: opt-in implementation candidates committed; no runtime
compilation or gameplay measurements independently verified here.
Phase 3: short-lock snapshot candidate and standalone range-gate prototype.
The global mapping lock remains the production safety mechanism.
Phase 4: opt-in GPU copy-back scan/merge and idle snapshot budget candidates;
production shader dirty bitmap and asynchronous readbacks remain deferred.
Phase 5: pipeline scheduling candidates and process-local cache publication
fixes; unsupported shader lowering and actual rendering validation remain open.
Phase 6: storage worker cap, reporting extensions, cumulative runtime CI,
and builder anchor repair committed. This is the end of the six-phase
implementation sequence, not a performance release. All 24 register items
remain unresolved pending their acceptance evidence. No item is closed on
implementation alone. Keep this register on subsequent branches and record
actual test results and benchmarks before closing items.

## Recorded validation evidence

- Phase 5 commit `3d1673ea6a443df9ee33b677a52080a343863f12`:
  [synthetic CI](https://github.com/larbob1/emulard/actions/runs/45935638184)
  failed 1 of 91 Python tests (overlapping builder anchors).
- Phase 6 commit `59c3cfb6406a5947a077af57651482ca44ee549c`:
  [synthetic PR CI](https://github.com/larbob1/emulard/actions/runs/45935874457)
  passed the Python test step (93 tests) and standalone range-gate test step
  (4 tests). This resolves the synthetic anchor-test failure, not P01/P09/P24
  as a whole. The Windows runtime validation
  [run](https://github.com/larbob1/emulard/actions/runs/45935865574) failed in the combined preparation/build stage (exit 1, no specific Rust
  diagnostics). Phase 6 subsequently separates preparation from compilation
  and reports sanitized patch names and failure categories. No gameplay benchmark is recorded.
