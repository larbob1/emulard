# Performance deferred-work register

This register is cumulative across the six performance phases. Keep the
same IDs in every later branch. An item is not closed by writing code:
record the validating commit, tests, and measured result (where relevant).
Keep unverified experiments opt-in. Review all open items at the end of
Phase 6; do not erase unresolved items or equate implementation with FPS.

| ID | Origin | Status | Outstanding work / acceptance evidence |
| --- | --- | --- | --- |
| P01 | 1 | Candidate | All 21 selected Windows suite invocations and both build profiles passed at 8956a8e. User reports Proton gameplay at 2–3 FPS; exact commit/flags and reproducible logs not supplied. Direct mapping preflight also passed Windows CI at 027849b. Newer integrated runtime, matched native/Proton comparisons and additional failure fixtures remain open. |
| P02 | 1 | Candidate | Local repeat-pair numeric benchmark aggregator added. Actual matched gameplay runs, CPU/GPU utilization, frame-level tails and native Windows versus Proton comparison remain open. |
| P03 | 1 | Candidate | Numeric report adds interval percentiles, selected long-frame and omitted counts, and FPS milestones. Also reports latest cumulative mapping/snapshot counters and actual rounded individual frame distributions from detailed frame batches. Critical-path attribution and real workload verification remain open. |
| P04 | 2 | Prototype | Sparse software page model and three-way native replay comparison in draft PR #10. Six portable tests passed. Runtime mirror, CPU-access audit, GPU-only classification, real backing lifetime and host-map elimination remain open. |
| P05 | 2 | Candidate | Direct physical mapping retries through the existing coalesce-or-page helper after a failed contiguous map; Windows split-restore fixture exposed the missing case. Full interval tracking, native validation, and measured host-call reductions remain open. |
| P06 | 2 | Candidate | Diff mapper now rejects unknown physical IDs and missing disjoint source ranges before changing views; checked range overflow and regression cases added. Checked unmap refusal handling and neighbor restore checks implemented with injected host failure fixture; full map/commit recovery, rollback and runtime verification remain open. |
| P07 | 2 | Candidate | Opt-in bounded scatter lock batching in PR #16 preserves per-page native operations and ordered prefixes. Native tests and Proton measurement pending; true host run coalescing remains open. |
| P08 | 2 | Candidate | Ported existing diagnostic trace and stable-backing tile replay fixture to paired-wave; validate runtime fixture with flags off/on, captured replay and partial/overlapping aliases. |
| P09 | 3 | Prototype | Range-aware locking: migrate audited runtime writers and readers to scoped gates; protect complete views reconstructed by unmap, handle alias invalidation and lock ordering. Prototype in probes/range_gate.rs only. |
| P10 | 3 | Prototype | Opt-in live mirror in PR #10 retains native Arc<Section> references and resolves pinned spans. Mapped-view lifetime, external frees, GPU fence retirement and consumer synchronization remain open. |
| P11 | 3 | Candidate | Validate bounded texture snapshots and generation retries; measure lock wait vs added copy cost, stale snapshot behavior and starvation. Retain original path. |
| P12 | 3 | Open | Replace global epoch with per-range generations, validate all mapping and free/protect paths and non-overlapping reader concurrency. |
| P13 | 4 | Open | Production completion-scoped dirty tracking; integrate per-flight descriptors, faults, atomics, alias notifications and completion fences. |
| P14 | 4 | Candidate | Optional exact AVX2 scan and sparse merge are implemented; benchmark and validate. Actual GPU readback bandwidth, redundant hashing and synchronization reductions remain open; maintain exact visibility and fences. |
| P15 | 4 | Candidate | Optional hard idle snapshot budget implemented; validate memory pressure and allocation churn. Persistent resources, staging reuse, async transfers, detiling and VRAM/RAM budget validation remain open. |
| P16 | 5 | Open | Unsupported shader operations, paired-wave semantics, waterfall loops, FidelityFX descriptor mutation, missing pipeline methods; ensure scene rendering correctness. |
| P17 | 5 | Candidate | Process-local cache save serialization and retry bookkeeping, optional bounded requested-graphics bursts and compiler worker count implemented. Persistent shader cache key coverage, cross-process cache ownership, compile worker stability, native-wave specialization and dropped draws remain open; validate. |
| P18 | 6 | Candidate | Opt-in paired-wave DirectStorage worker cap implemented. Descriptor/command list caching, release/PGO evaluation, native Linux backend feasibility and measured worker tuning remain open. |
| P19 | 6 | Candidate | Stacked paired-wave integration and Windows compile workflow added; builder patch overlap corrected. Both build profiles passed at 8956a8e; current-head validation, end-to-end gameplay and other runtime variant ports remain open. |
| P20 | 6 | Open | Verify sustained visible gameplay at target milestones (5, 10, 20, 30 FPS); do not count black frames or dropped draws as playable. |
| P21 | 4 | Candidate | Independent Linux CI compiled the actual prepared scalar/AVX2, sparse merge and idle budget helpers; five tests passed in each of two switch modes. Runtime mask paths, GPU integration, CPU/RAM/transfer telemetry and real benchmarks remain open. |
| P22 | 5 | Open | Validate cache publication under concurrent periodic/forced saves and injected serialization/rename failures, restart and driver rejection; test scheduling fairness, compiler contention, cold/warm cache frame times and dropped draws. |
| P23 | 6 | Open | Validate the storage worker cap against default and multiple caps; confirm throughput, queue starvation, frame times and safe completion under Windows/Proton. |
| P24 | 6 | Candidate | Prior Windows split/restore and partial-source regression failures resolved at 8956a8e; complete Windows validation passed. Isolated hot-path Windows CI also passed; newer preflight also passed. Combined current integration remains open. |

## Current state

Phases 1 and 2: opt-in implementation candidates committed. Earlier Windows
runs compiled the HLE test executable but failed the split/restore regression;
both profiles and selected Windows suites subsequently passed at 8956a8e; gameplay remains unverified.
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

- Runtime CI run [45935947236](https://github.com/larbob1/emulard/actions/runs/45935947236) failed during pinned source preparation with a patch context mismatch. A local minimal Git fixture reproduced the same failure applying CRLF patch text to LF source. Normalize patch line endings, enforce LF patch checkout, and retain strict context checks; the next CI run must confirm the actual runtime failure is resolved. P01 and P24 remain open.

## Deferred resolution work

P08: ported the existing tile replay fixture and optional local mapping trace to paired-wave. Test calls run with mapping flags off and on. Trace files contain virtual addresses and are local-only; do not upload them. Actual compiled replay and captured title validation are still pending. No IDs closed.

P02/P03: added local matched-pair aggregation and allowlisted cumulative counters. Real gameplay measurements and critical-path timing are not available. Use at least three matched pairs, with visual scene confirmation by the operator.

P01/P24: the cumulative paired-wave test runner now requires at least one passing test per selected suite and reports the failing suite. A zero-test filter is a failure, not validation. Full Windows build/test results and Proton execution remain outstanding.

### Stabilization evidence

- [Windows runtime CI 45936234001](https://github.com/larbob1/emulard/actions/runs/45936234001): after the LF normalization fix, pinned source preparation and toolchain checks passed. The subsequent runtime test/build stage failed (exit 1); no specific error code was retained by that run. The failing stage is not resolved.
- [Synthetic CI 45936436022](https://github.com/larbob1/emulard/actions/runs/45936436022) for commit `69f7f49c36eb09b885f82bfb7aaf93fee7c3f0ae`: 101 Python tests and four standalone Rust tests passed. This includes CRLF patch handling, replay patcher, report aggregation and nonempty suite enforcement. The full runtime is still unverified.
- P01/P24 remain open; P02/P03/P08 have candidates, not completed acceptance. P04–P07, P09–P17, P18–P23 remain as listed in the table. No FPS result or closure is claimed.

P03: detailed present-to-present frame batches now produce independent p50/p90/p95/p99 and maximum frame times, with count validation and separate warmup exclusion. No runtime measurements are available.

P06: preflight failures now leave existing aligned diff mappings intact, and range overflow is rejected before mutation. This is not transactional host failure recovery. Existing native map/unmap error paths still require a separate audit and fault injection; no closure claimed.

P21: a separate portable-copy CI job prepares the pinned patched renderer and compiles the exact portable helper functions with rustc on Linux. This can verify pure CPU equivalence and idle-budget tests without compiling D3D12 or claiming gameplay correctness. Results recorded below.

- [Windows CI 45936505077](https://github.com/larbob1/emulard/actions/runs/45936505077) compiled and ran the first selected HLE test, then failed with a runtime assertion panic in `physical_pages_map_alias_and_unmap`. This is not a release-build success. The assertion location was not included by the earlier sanitized filter; the revised filter records source-relative panic locations, failed test names and the current experiment switches. P01/P24 stay open.
- [Synthetic CI 45936759570](https://github.com/larbob1/emulard/actions/runs/45936759570) at `4ea21899f6ef644ea1401adcc340bfd8e561b7f3` passed 102 Python and four standalone Rust tests. Runtime mapping tests remain unverified.

- [Linux portable-copy CI 45936840744](https://github.com/larbob1/emulard/actions/runs/45936840744), commit `497c612685113154b7e24cdb8b56206c8f4af9e7`: pinned cumulative source preparation passed, and the extracted actual Rust helpers compiled and passed five tests each with AVX2/sparse disabled and enabled (10 test executions). Hardware-specific AVX2 checks use runtime feature detection. P21 remains a candidate because GPU integration and real performance measurements are absent.

P05/P06/P24: direct physical mapping now attempts the existing coalesce-or-page fallback when a multi-page contiguous host map fails. The existing remap regression exercises split-then-restore; actual Windows outcome is pending. This is not a complete placeholder interval tracker or transaction recovery. CI now runs all selected suites and both build profiles even after a failing group, then fails overall, so independent results are not hidden by the first failure. Superseded Windows jobs are canceled.

P06: checked unmap candidate preserves the HLE view index on host unmap refusal, restores the invalidated renderer view census, and reports failed neighboring reconstruction instead of silently succeeding. Known renderer-guarded blocks are reopened before invalidation; this may increase remap work. Added injected host refusal to the physical mapping fixture. Full rollback across multiple views and failed map/commit cleanup remain open. Runtime verification pending.

- [Windows CI 45936873951](https://github.com/larbob1/emulard/actions/runs/45936873951), commit `e5d1e38c9c13e76be11aae9c49268589e2b8de9c`, all three mapping flags off: failed `physical_pages_map_alias_and_unmap` at `xmem.rs:1659:9`. Reconstructing the pinned source and its xmem transformations identifies the assertion as restoring the original three-page contiguous mapping after a split. The coalesce-or-page fallback in `e1f7501c187b3582f0532d919c9b65f960d429b7` targets precisely that operation. [Synthetic and portable-copy CI](https://github.com/larbob1/emulard/actions/runs/45937093784) passed on that commit. The Windows fix and checked-unmap candidate still require runtime validation; P01/P05/P06/P24 remain unresolved.

### Reverse alias indexing candidate (isolated)

- [dev/performance-phase6-alias-index](https://github.com/larbob1/emulard/tree/dev/performance-phase6-alias-index), commit `3b63d02e4e6874a53acd1827e220282bf90217b7`, ports the existing fxceless ordered-set reverse alias indexes to paired-wave in both HLE and GPU. Exact source anchors checked against pinned upstream; a new reverse-index regression and Linux source preparation job are included. Not merged into Phase 6 while the Windows mapping stabilization run is active. P05/P08/P18 remain unresolved: full interval tracking, replay verification, matched benchmarks and native runtime checks still required. See the candidate's `docs/performance-alias-index.md`.

- [Alias index synthetic CI 45937502413](https://github.com/larbob1/emulard/actions/runs/45937502413), commit `3b63d02e4e6874a53acd1827e220282bf90217b7`: 107 Python tests, four standalone range-gate tests and ten portable copy helper test executions passed; native reverse-index regression and performance remain unverified.
- P06/P24: reviewed the earlier range-diff preflight against the existing partial-source fixture. A wholly absent first source page still fails without changing a disjoint destination; a valid prefix followed by a missing page now falls back to the established alias mapper, preserving partial-map semantics. The existing fixture is retained. CI now records each validation group's pass/fail with its experiment switches, including both build profiles. Windows jobs queue rather than cancel an active run. No item closed; runtime results pending.

### Mapping hot-path optimization (isolated)

- [Windows run 45937238198](https://github.com/larbob1/emulard/actions/runs/45937238198), commit `1fcdf683ed9425aab08e929b4d6936b9364c40c9`: preparation and toolchain checks passed. The keep-going validation reported two failures, both in `physical_pages_map_alias_and_unmap`, with panic at `xmem.rs:1790:13` in the alias-byte comparison closure. No other groups or build profiles were reported as failed. This is earlier source, not current release acceptance. The newer [Windows run](https://github.com/larbob1/emulard/actions/runs/45937702602) tests the partial-source correction and was in progress when checked.
- [PR #8](https://github.com/larbob1/emulard/pull/8), branch `dev/performance-phase6-mapping-hotpath`, commit `2871877b1e30a6c41882c6e577aa53fac0469365`: adds opt-in changed-span contiguous backing-run batching (`VICTORY_MAP_DIFF_RUNS=1`, requires `VICTORY_MAP_DIFF=1`) and guarded fully-covered texture residency estimates (`VICTORY_TEXTURE_VIEW_ESTIMATE=1`). Actual title-memory read safety checks remain unchanged. Six source anchors checked. [Synthetic CI](https://github.com/larbob1/emulard/actions/runs/45938587709) and [Windows CI](https://github.com/larbob1/emulard/actions/runs/45938587772) started. P05/P06/P08/P11/P15/P24 remain unresolved. No FPS gain claimed; full interval tracking, changed scatter batching and architectural changes remain outstanding.

- [Hot-path synthetic CI 45938587709](https://github.com/larbob1/emulard/actions/runs/45938587709) at `2871877b1e30a6c41882c6e577aa53fac0469365` passed 108 Python, four range-gate and ten portable copy-helper test executions. Full runtime checks pending.
- P06/P24: default direct mapping now preflights the entire physical request in one pass, grouping contiguous backing slices before unmapping. An unknown final ID cannot destroy the destination, regardless of experimental flags. Existing native map/unmap failures remain nontransactional; valid requests retain original mapping and fallback behavior. The earlier alias-byte assertion now identifies the exact synthetic step and page in sanitized CI. All four source anchors verified against reconstructed prepared xmem. This is not a verified resolution of the alias mismatch; runtime tests pending.

### First complete Windows validation and playtest readiness

- [Windows CI 45937702602](https://github.com/larbob1/emulard/actions/runs/45937702602) at `8956a8e3a3f847a2e7959ac17623debc11a1da6c` passed all 21 selected suite invocations (including all four physical-page modes, concurrent reads and tile replay) and both release/diagnostic builds. This verifies the earlier partial-source correction in the tested native Windows suites, not Proton gameplay. Use this exact revision for the first controlled playtest after smoke checks. [Newer preflight runtime CI](https://github.com/larbob1/emulard/actions/runs/45938913428) and hot-path native validation remain separate. No item closed; all 24 IDs retained.
- P02/P03/P20: report now supports `--target-fps 30`, approximate present rate derived from rounded individual durations, independent sample counts, and the new hot-path counters. Default target remains 10 for backward compatibility. A present is not proof of a correctly displayed frame; operator visual checks and repeated runs remain required. New report tests are pending CI.

### Proton baseline and mapping hot-path integration

- Project owner reports actual Proton gameplay at approximately 2–3 FPS. Exact runtime revision, settings, scene, duration, visual correctness and raw measurements were not supplied; treat this as an operator-reported baseline, not formal 30 FPS acceptance. Target is approximately 10–15x improvement.
- [Hot-path Windows CI 45938587772](https://github.com/larbob1/emulard/actions/runs/45938587772) at `2871877b1e30a6c41882c6e577aa53fac0469365` passed all 24 selected suite invocations and both build profiles, including changed-run and coverage fixtures. Ported its opt-in changes to the cumulative branch without merging the old branch's other files. Combined current-head tests are pending.
- P05/P08: new independent `VICTORY_MAP_ALIAS_DIRECT=1` experiment (requires `VICTORY_MAP_RUNS=1` and a multi-page changed run on the alias-run path) first tries normal contiguous mapping before per-page splitting/coalescing. Falls back to existing map_run on refusal. Counters record logical attempts and hits, not host syscall counts. This can cost an extra attempt if the range is fragmented; compare matched workloads, never enable as default without measurement. Existing map failure cleanup remains nontransactional. Native tests pending. Full interval tracking and P07 changed-scatter batching remain open.

- [Integrated mapping synthetic CI 45939889284](https://github.com/larbob1/emulard/actions/runs/45939889284) at `c5db0730fa6977c93de543cdd755a426133e52d3` passed pinned source preparation, 113 Python tests, four standalone range-gate tests and ten portable copy-helper executions. [Combined Windows validation](https://github.com/larbob1/emulard/actions/runs/45939884795) was pending when checked. No new performance result or deferred-item closure claimed.

### Exact multi-page placeholder reuse

- [Draft PR #9](https://github.com/larbob1/emulard/pull/9) at `72fcda9e75235505afeb69ce687d0438567afb66` adds `VICTORY_MAP_EXACT_PLACEHOLDERS=1` (default off). Tracks at most 65,536 exact preserved ranges from successful unmaps; overlapping changes discard whole hints rather than infer boundaries. Matching ranges attempt host replacement before splitting or coalescing. Host validation and original fallback remain. Six prepared xmem anchors checked. [Synthetic CI](https://github.com/larbob1/emulard/actions/runs/45940202823) and [Windows CI](https://github.com/larbob1/emulard/actions/runs/45940202830) started. P05 remains a candidate: not a full reservation interval tracker, no comprehensive external free/protect tracking, no actual Proton improvement measured. Kept separate from cumulative branch while its existing runtime validation runs.

- [Exact-placeholder synthetic CI 45940202823](https://github.com/larbob1/emulard/actions/runs/45940202823) passed on `72fcda9e`: 115 Python tests, four range-gate tests, four exact-hint Rust tests and ten portable copy-helper test executions. Pinned cumulative preparation passed. Native Windows validation and measured gameplay remain pending. No deferred ID closed.

### Software page-table architecture prototype

- [Windows CI 45938913428](https://github.com/larbob1/emulard/actions/runs/45938913428) at `027849b6915b3998aed22765040f109c41a23cb7` passed all 21 selected suites and both build profiles. Direct physical-map preflight now has native test evidence; no additional Proton result claimed.
- [Draft PR #10](https://github.com/larbob1/emulard/pull/10) at `2465f0a391bf4a2226d2fc5fc246069ea04e1afc` adds `probes/software_pages.rs`, a sparse 64 KiB page model, checked backing plans and logical section generation keys. The test-only runtime tile replay compares native views, dense reference and sparse model. [Synthetic CI 45940469806](https://github.com/larbob1/emulard/actions/runs/45940469806) passed 113 Python tests, four range-gate tests, six software-page tests and ten portable copy-helper executions. [Native CI 45940469770](https://github.com/larbob1/emulard/actions/runs/45940469770) remains pending at time of writing. The model is not a native lifetime pin and skips zero production host remaps. P04/P08/P10 remain unresolved. Next: audit `CopyPageMappingsBatchX` consumers, section lifetime and GPU-only classification; mirror successful mapping operations before replacing native behavior.

- P04/P10: [PR #10](https://github.com/larbob1/emulard/pull/10) advanced to `3803f323f088bccbbbe3225a1691133b6af8b19f`. Adds `VICTORY_MAP_PINNED_MIRROR=1`, an observational interval mirror under existing locks, updated after successful host map/unmap. Pinned plans clone native Arc<Section> references; failures disable the mirror. Six reconstructed xmem anchors verified. Four portable tests and native comparison/refusal fixtures added; CI pending. No production read path changed, no GPU completion or mapped-byte lifetime pin, no remaps avoided, no FPS result. See branch `docs/performance-pinned-mirror.md`. All 24 IDs remain unresolved.

- P05: exact-placeholder candidate 72fcda9 passed [Windows CI 45940202830](https://github.com/larbob1/emulard/actions/runs/45940202830), 32 selected suite invocations and both profiles. Isolated, not merged; measured Proton benefit and full authoritative interval tracking remain open.
- P04/P08: software page model 2465f0a passed [Windows CI 45940469770](https://github.com/larbob1/emulard/actions/runs/45940469770), 28 selected suites and both profiles, including native three-way replay. Pinned mirror 3803f32 passed [synthetic CI 45940715753](https://github.com/larbob1/emulard/actions/runs/45940715753), 114 Python tests and 24 standalone/portable Rust executions. Its native CI remains active.
- P04/P10: PR #10 now at 49ca4761a8b917cca2c0b001203c838777cada91. Adds a test-only native read-only backing view fixture: scattered cross-page reads, alias replacement, retained plan after all views/page IDs retire, and final Arc release. No production read callback, mapped-byte pin, GPU synchronization or avoided host remaps. [Synthetic](https://github.com/larbob1/emulard/actions/runs/45941392929) and [native](https://github.com/larbob1/emulard/actions/runs/45941392890) CI started. No new FPS measurement; all 24 IDs remain open.

### Coordinated development update

- Combined cumulative c5db073 passed [Windows CI 45939884795](https://github.com/larbob1/emulard/actions/runs/45939884795): 27 selected suite invocations and both release/diagnostic builds. This is the latest cumulative runtime-changing revision with native acceptance evidence, not a new Proton performance result.
- P07: [PR #16](https://github.com/larbob1/emulard/pull/16), commit 1f5cbf1049d0c76496df77aaa85f0d079527d960, adds opt-in VICTORY_MAP_SCATTER_LOCK_BATCH=1. Bounded ordered changed prefixes (up to 64 pages) amortize mapping lock acquisition while preserving per-page native operations, duplicate order, invalid/clear/unchanged fallback and stop-on-failure. Three exact prepared anchors verified. [Synthetic CI](https://github.com/larbob1/emulard/actions/runs/45941647725) passed 114 Python tests, four range-gate tests, ten portable copy-helper executions and pinned preparation. [Native CI](https://github.com/larbob1/emulard/actions/runs/45941647777) pending. Longer writer holds may hurt readers; no syscall reduction or FPS claim. P07 is a candidate; true host coalescing and measured acceptance remain open.
- P04/P10: pinned-read fixture 49ca476 passed [synthetic CI](https://github.com/larbob1/emulard/actions/runs/45941392929); native fixture remains queued. Production reader work depends on native verification and graphics fence/ownership agreement.
- AI 2 opened [PR #14](https://github.com/larbob1/emulard/pull/14) for P22 pipeline cache publication; AI 3 opened [PR #15](https://github.com/larbob1/emulard/pull/15) for P02/P03/P23 benchmark/reporting. Their changes have not been integrated or independently accepted. Shared ownership requests posted to issues #12/#13. All 24 deferred items remain unresolved; no merge.

### First combined multi-agent playtest candidate

- [PR #18](https://github.com/larbob1/emulard/pull/18), branch dev/performance-phase6-combined-playtest, pinned commit dbac4c6ea21d9580f5b0bd39ba2b9d6c4eb6f2b1. Isolated review build on 2d244a5, staging PR #9 at 72fcda9 (placeholder hints, native passed), PR #14 at c660257 (pipeline cache publication, synthetic passed), and PR #15 at 9330d96 (reporting/acceptance/storage tools, synthetic passed). Existing files checked for overlap; added exact-placeholder counter/test on combined branch. Other agents have advanced their own heads; those later changes are not included. No source branch merge, deletion or change to main.
- [Combined synthetic CI](https://github.com/larbob1/emulard/actions/runs/45942012900): all jobs passed. [Combined Windows CI](https://github.com/larbob1/emulard/actions/runs/45942012941) started. The branch contains docs/performance-combined-playtest.md with matched comparison instructions. Await full native validation before recommending it for gameplay.
- PR #10 pinned backing reader, PR #16 scatter lock batching and PR #17 pipeline stream bounds are excluded pending native validation/review. All 24 deferred IDs remain unresolved. No measured gain beyond owner-reported 2–3 FPS.

### Reverse-alias index candidate (P05/P08)

- [PR #19](https://github.com/larbob1/emulard/pull/19), commit b8af0471247b038337d15b9682a598db00c9ffb0, branch dev/performance-phase6-alias-index-v2. Refreshes 3b63d02 prototype on latest cumulative 5d0face. HLE and GPU reverse indexes use BTreeSet, changing large-group removal from linear retain to logarithmic removal. Adds native HLE 64-alias churn fixture (32 replacements, exact reverse lookup and actual alias bytes, unmap and free) and GPU independent-view test. Small groups may regress; no cumulative default change, host remap elimination or FPS claim. [Synthetic CI](https://github.com/larbob1/emulard/actions/runs/45942226564) passed; [native CI](https://github.com/larbob1/emulard/actions/runs/45942226390) pending. P05/P08 remain open.
- PR #18 combined native validation still active at check; #10/#16 native checks likewise not yet complete. AI 2 continues shader cache recovery/identity work on #14, AI 3 continues PGO planning and reporting on #15. Read their issue handoffs; no new integration or merge. All 24 deferred tasks remain tracked. No new gameplay measurement.
