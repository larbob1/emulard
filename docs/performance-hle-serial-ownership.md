# Serialized port ownership audit (P18/P24)

Review only. Pinned victory-fork 51700c6d43a3507fa65e50fe4bb64074ce706cd4, xasync.rs Git blob 068d75f2a8a50b7a4f0ec7a45e9c849c657bcde1. Line numbers refer to that exact upstream file, not a combined prepared runtime. Historical native #51 is baseline only; coordinator #58 4a7e8955ae6381c15ba01daa6e4d118fc4fde715 registered the four earlier baseline cases, native run 45956314090 active at review. Serialized fixture and standalone event model have not been executed against actual HLE.

## Actual ownership paths

| Path | Ownership effect |
|---|---|
| Port::new (96+) | Serialized worker clones Arc<Port>; empty take(1000) followed by sole strong reference check ends worker. |
| Queue::new (202+) | Owns two Arc<Port> slots; the slots can share a port through composition. |
| XTaskQueueGetPort (286+) | Borrowed raw pointer to existing Port, not a new strong reference. Validity depends on open source queue. |
| XTaskQueueCreateComposite (298+) | Adds a strong Port reference per slot, including two references if same port in both slots. |
| queue / duplicate / close (261+, 319+, 330+) | Add/drop Arc<Queue> references, not new Port owners per handle. Temporary API reference also extends queue lifetime. |
| Queue::submit / deliver (210+, 229+) | Delayed thread holds Arc<Queue> through port delivery and monitor callbacks; immediate submission holds the temporary queue reference too. |
| Process queue (247+, 428+, 437+) | Global optional Arc<Queue> can retain a custom queue after caller closes its handle. Replacement/clear drops a reference under PROCESS_QUEUE lock. Lazy default uses thread-pool ports. |
| Manual dispatch (340+) | Temporary queue reference held across wait and callback. No change to manual semantics proposed. |
| AsyncBlock (448+, schedule 575+, complete 603+) | Raw queue pointer is not an independent retained Arc; schedule and completion resolve it when used, with existing fallback behavior. Do not invent additional ownership guarantees. |

## Preferred design for review: separate worker state from public port ownership

The portable model's explicit owner count is not a literal mapping to actual HLE handles. Instead, consider keeping existing Arc<Port> ownership and raw borrowed port identity unchanged. Port owns Arc<WorkerState>; serialized worker holds only Arc<WorkerState>, never Arc<Port>. The last actual Port drop therefore occurs naturally after all owning queue slots disappear, regardless of duplicate handles, delayed queue references or process queue ownership.

WorkerState would own queue storage, condition variable and a final-close predicate under the same mutex. Port drop would set that predicate and notify; worker would drain already accepted jobs before returning when empty and closed. No periodic wait is needed in the candidate, and no explicit handle counter or extra owner increment per duplicate would be required. Do not assume this is already implemented or safe. A candidate must retain every path that can legally submit and prove the raw Port address is still the address returned by GetPort. Never resurrect a dropped Port via raw pointer. No change to existing caller lifetime contract or exported ABI is proposed.

Keep the existing lock order: process queue replacement can drop Port while holding PROCESS_QUEUE; candidate close must not call callbacks, acquire process queue or join while holding port mutex. Worker must drop queue mutex before Task::run, including reentrant submissions. No guest callback or monitor execution in destructor. Review panic/poison policy, allocation overhead, default-off cost, thread creation failure and actual loader detach before implementation. A separate allocation for worker state may offset savings; no measured benefit yet.

## Termination is not ownership release

XTaskQueueTerminate (374+) sets a queue-local terminated flag, drains the shared port's currently queued tasks under its task mutex, notifies waiters and runs canceled callbacks outside that lock. It does not close Port or eliminate another queue's ownership. It does not necessarily prevent previously scheduled delayed deliveries. Preserve current behavior until separately reviewed; do not silently make termination a global port shutdown or force cancellation on close. Existing manual dispatch predicates depend on the individual queue's termination flag; worker close must not replace that predicate.

## Validation requirements

First exact serialized baseline native fixture (ca02788e) and composed baseline #58. Then an independently reviewed test-only candidate with real Port/Queue construction, exact prepared pin, and fresh process tests: duplicate queue handle, composite using both slots of one serialized port, original close with surviving composite, process queue retention/replacement, delayed submission holding queue through monitor delivery, final close during blocked callback and ordered drain, reentrant callback that closes or submits, separate termination with another queue on shared port, and no-work wait/close interleaving. No callbacks or joins in close. Verify actual port lifetime separately from OS thread exit and Rust/Windows loader lifecycle. Maintain full existing xasync tests and release/diagnostics builds. No native fixture for this alternative yet.

Measure actual wait returns, timeout returns, useful task claims, close notification and worker exits separately only after instrumentation approval; actual CPU, latency and overhead require matched workloads, not the number of modeled periodic waits. No guessed FPS. D22-D25 unchanged; no production changes, shared CI, schema, owner access, title launch or merge.
