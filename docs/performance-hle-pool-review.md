# P18/P24 HLE worker admission review (AI6)

- Assigned base: 6b19a42d6f0d95fe8ec42ef4a6f056a0ad96414b
- Pinned upstream: fxceless/victory-fork 51700c6d43a3507fa65e50fe4bb64074ce706cd4
- Claim: #46 comment 7211422282. D22/D23: title-free fixture only; no production change.

## Read-only findings

- `victory-loader/src/threads.rs::on_thread` snapshots attached images under IMAGES, releases the mutex before callbacks, preserves forward attach/reverse detach and saves/restores Rust TLS for host-created threads. `detach_all` has an exit-only watchdog yield loop. Neither is a proven frame-critical hotspot. Do not change TLS, callback ordering, loader policy or watchdog.
- `victory-hle/src/modules/kernel.rs::module` does not export generic wait/timer functions; `find_module` handles library initialization and host policy. Do not alter it.
- `victory-hle/src/modules/xasync.rs::Pool::submit` pushes under state mutex; starts an OS thread if queued count exceeds idle count. `Pool::work` claims under the same mutex, runs callbacks outside it, tracks idle around condition-variable wait. Workers persist. Newly requested threads are not counted until they run; another worker can drain earlier queued work before a pending thread starts, leaving latent capacity unrecognized by later submissions. A fresh burst alone does not imply overspawn.
- `Port::new/take` serialized worker waits with a one-second timeout to detect sole-reference lifetime; manual dispatch uses predicate-based finite/infinite waits. `Queue::submit` creates one sleeping thread per delayed submission; `deliver` invokes monitors; termination and shared composite ports complicate cancellation. No timer consolidation or idle wake policy change proposed here.
- The branch builder and initial patch inventory were inspected but a complete prepared-source anchor audit was not established (connector batch limit). Findings refer to exact pinned upstream, not independently prepared runtime. Coordinator must verify prepared symbols and caller/lifecycle constraints before implementation.

## Deterministic fixture

Run: `python probes/test_hle_pool_admission.py -v`. Five tests passed in an isolated Python environment. No native build or gameplay test.

A deterministic sequential model compares existing queue-length > idle admission with a hypothetical queue-length > idle + starting admission under the same abstract interleavings. When a worker drains two tasks while another requested worker is still pending, then two new tasks arrive, baseline requests three workers total; reservation model requests two. An eight-task fresh burst requests eight in both. Additional cases exercise active callback exclusion from capacity, a pending worker finding an empty queue, FIFO claim order and idle reuse. This is a counterexample and model only, not actual thread counts, measured contention, or a throughput claim. Wake/start actions are explicitly scheduled, not OS condition-variable behavior. No modeled failure, timing, cancellation or indefinite startup delay.

## Before runtime candidate

1. Verify exact prepared Pool::submit/work and other worker ownership with AI1 and AI5/AI2; no shared edits.
2. Prove starting reservation and decrement under the same mutex; keep callbacks outside lock and active callbacks out of available capacity. Do not cap pool or change priorities/affinity. Explicitly handle failed spawn or delayed startup without leaving permanent phantom capacity; preserve existing error contract. Review notification coverage when idle and starting workers coexist.
3. Native barrier-controlled fixtures: overlapping submit/start/drain; idle wake and spurious wake; blocked/reentrant callback requiring another worker; startup failure/liveness, FIFO claim ordering (not completion order), exactly-once work, and unchanged disabled mode. Test actual scheduler and contention with bounded deadline; never infer fairness from this model.
4. Request AI3 review of sanitized startup/worker evidence and any future counter schema; AI1 owns registration and CI. Any experiment must default off after review. D22 no title launch; request existing sanitized evidence via #27 only.

All P-IDs remain unresolved. No runtime, builder, workflow, report schema, frozen #18 or title changes. No FPS estimate.
