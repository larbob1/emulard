# HLE thread lifecycle review (P18/P24)

Scope: pinned victory-fork 51700c6d43a3507fa65e50fe4bb64074ce706cd4, loader threads.rs blob 903aebd4cffc7e4a9a05b12f98068697a972f6f3 and HLE xasync.rs blob 068d75f2a8a50b7a4f0ec7a45e9c849c657bcde1. Read-only source audit; no runtime changes.

## Actual source boundaries

- Pool::submit enqueues under the pool state mutex, then uses std::thread::spawn when queued work exceeds idle workers. Pool::work counts idle around its condition-variable wait and releases the lock before Task::run. Baseline pool workers persist.
- Loader threads.rs registers ON_THREAD in .CRT$XLAV. Windows thread attach and detach notifications are forwarded to attached title images even for runtime-created threads. Snapshot of Arc image references and quiet flags is taken under IMAGES, then image notifications happen without that mutex; attach order is forward and detach reverse.
- On Rust-started threads, the attach path saves and restores the runtime's own TLS around image notifications. Source comments explicitly note that Windows loader notices and Rust setup precede the thread body. A successful spawn is therefore not an observed entry into Pool::work.
- Normal worker exit can introduce additional thread detach notifications; worker retirement changes that frequency relative to baseline persistent workers. Actual title callback effects and Windows loader serialization are not represented by a Rust-only test. Do not infer that the existing loader can always make progress through arbitrary reentry.
- Process-wide detach_all is an exit-only path with EXITING and its watchdog. It is unrelated to an ordinary worker retirement strategy and must not be repurposed or changed.

## Candidate constraints

Keep pending starts, entered workers, available idle workers, active callbacks, retiring workers and actually ended threads distinct. Remove availability under the admission lock before retiring, then release it before exiting or joining. A join or TLS cleanup may need locks used by scheduling; no join while holding the admission lock. Never credit a retiring worker as available capacity. Do not assume that a new worker has entered or that a queued dependency can progress just because spawn returned.

The standalone lifecycle fixture uses actual Rust TLS Drop with a bounded cleanup gate and a replacement worker, and separate channel-gated startup and lock dependency cases. These establish a portable boundary example only; the replacement is explicitly created by the harness, not by native HLE admission. A normal Rust TLS destructor is not a Windows loader callback. No loaded title images, Windows loader lock, DLL entry points or actual guest TLS are exercised.

## Before a runtime retirement policy

Require exact prepared baseline native evidence and independent review, then native test-only lifecycle characterization without touching title files. Test attach/detach order and quiet behavior if a coordinator-approved synthetic image fixture can represent them; preserve the existing startup, failure, callback and unload semantics. Review normal return, cleanup reentry and process shutdown separately. Observe worker entry/exit and callback progress, thread creation frequency and retained idle resources separately under controlled workload; compare matched repeated workloads and report thread counts, not guessed RSS or FPS. Do not select a timeout, cap, or change production policy from the portable model. D22/D23/D24 restrictions remain.
