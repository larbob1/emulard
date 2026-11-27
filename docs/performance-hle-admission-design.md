# HLE admission and scheduling candidate decision record (P18/P24)

Review-only, not an implementation or policy approval. Pinned upstream victory-fork 51700c6d43a3507fa65e50fe4bb64074ce706cd4, xasync.rs blob 068d75f2a8a50b7a4f0ec7a45e9c849c657bcde1 and loader threads.rs blob 903aebd4cffc7e4a9a05b12f98068697a972f6f3. Historical native baseline #51 6e8c5b3cf7dbc11ddd7c5c109cae98cda7f621d3 passed 32 validation groups; exact composed preview #47 26a1a45b31f0ddc55b31233a6d1aa515b90ab13f passed synthetic CI only. Do not transfer native success to the composed suite.

## Decision: no pending-worker credit in admission until liveness is established

Existing Pool::submit enqueues under its state mutex and creates a worker if queue length exceeds idle workers. A successfully created but not entered worker is not equivalent to an idle worker. Windows loader thread attach notifications run before the Rust worker body and may call title code. A gated standalone model demonstrated that counting pending starts can delay dependent work. This is not evidence of an actual title deadlock, but a reason not to approve blanket pending capacity, a hard cap or a fallback timer.

The idle-only baseline is the reference, including its potential redundant starts. Do not claim that baseline is universally deadlock-free. A native gated start fixture must first characterize the existing behavior, not force a desired candidate result. The injected spawn panic fixture catches only a Rust test boundary; preserve the actual existing panic contract and never introduce recovery across extern callbacks based on that fixture.

## Candidate ordering

1. Establish the four native baseline fixtures, with separately invoked fresh processes and exact counts. Confirm prepared source and both builds.
2. Review a narrow idle retirement candidate separately from admission. Recheck the queue and decrement idle availability under the same mutex before exiting; no pending or retiring credit, no callback execution or join under that mutex. Ordinary thread exit triggers loader notifications, so Rust destructor tests alone do not prove safety. Do not select a timeout before native lifecycle characterization and a churn baseline.
3. Review timer waiting independently from dispatch. A single waiter may release due jobs without executing potentially blocking callbacks or monitors. No fixed dispatcher cap, blocking handoff, silent discard, automatic rejection, or unbounded overflow policy is selected. Preserve queue retention, port modes, monitor behavior and the observed termination behavior until a distinct API compatibility decision is reviewed.
4. Revisit pending-worker reservations only if a specific mechanism can preserve dependent progress even when a created worker has not entered. Do not equate a successful spawn, an OS handle or a start request with capacity. If no such proof exists, retain baseline admission.

These are review priorities, not a ranking of measured speedups. None has demonstrated title workload relevance or FPS improvement.

## Native gates before candidate comparison

- Exact existing xasync tests and reentrant callback baseline; gated start, injected spawn panic and delayed lifetime/termination each in a fresh process with explicit one-pass result and watchdog.
- Candidate-specific coverage: callback submits dependent work while blocked, idle waiter notification and queue predicate after wake, delayed start with no idle workers, already-entered active worker not counted as available, exact once task claim, queue ownership and monitor delivery.
- For retirement: submission before/after timeout, notification without work, worker exit and replacement, controlled cleanup overlap. Review real Windows loader attach/detach behavior using an approved title-free fixture, not the owner's files. No join while holding an admission lock.
- For timer: earlier deadline inserted while waiting, no early release, same deadline handoff ordering (not completion ordering), immediate/serialized/manual/pool dispatch, blocked callbacks/monitors, accepted task ownership on full/disconnect, close and termination. No silent drop or changed cancellation policy.
- Preserve default-off semantics in fresh processes, exact baseline behavior, both builds and existing regression suite. A failure, timeout, missing result or unsupported environment is not a pass.

## Measurement proposal (review only)

Use matched title-free synthetic workloads, identical work counts and correctness checks, explicit mode, fresh processes when global pool state persists, warmup and repeated batches with rotated order. Establish baseline repeatability before selecting any overhead budget or production timeout.

Keep spawn requested, creation success/failure, worker body entered, idle, active, retiring and observed ended distinct. A worker may retire from scheduling before its thread finishes cleanup. Avoid extra hot locks or scans; use existing state ownership where feasible and review off-path overhead. Pending/ready/active/completed task counts must use a consistent accounting boundary; rejected or unavailable outcomes separate. Record actual queue wait and time-to-worker-entry separately from callback duration; elapsed wall time is not CPU time. Thread count and requested bytes do not establish RSS. Report distributions per workload and preserve incomplete outcomes. No output schema, instrumentation, thresholds or benchmark implementation authorized here; coordinate AI3 measurement review and AI1 registration.

No title launch, owner-machine access, shared CI registration, merge or production changes. D22-D25 unchanged; AI4 alone has owner-machine access. All P01-P24 remain open.
