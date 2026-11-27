# D16 descriptor owner/list/flight lifetime fixture — review only

This extends #35 with a conservative CPU model. It is not the actual
native ownership fixture or a proposal to release production resources.
The original preview remains unchanged and must not be applied.

## Invariant and proposed design boundary

A title wrapper address is not a stable owner ID. Registration and
unregistration of a wrapper are independent from retained descriptor
state. New owners get checked monotonic identities; stale unregister
cannot remove a new owner. Keep one global pass serialization in the
model; weak cache entries do not confer retention. Every recorded list
must acquire independent owner state at bind/consumption even on skipped
refresh. Each replay holds its recording until actual same-domain GPU
completion AND all publication obligations. Reset requires all flights
retired; a completed recording may be replayed until reset. Failure or
device loss retains active pins, no automatic replay.

The model deliberately keeps ALL old slot versions until the retained
owner dies. This is a conservative safety upper bound, potentially worse
for RAM, not the proposed production retention policy. Mutable/direct
indexed descriptors require a real visibility and slot-version contract;
do not assume recorded descriptor snapshots describe actual GPU use.
Publication boolean is an external assertion, not a real fence or alias
operation. Dropping the modeled queue is not a production recovery path.

## Actual prepared source proof required before any release

| Pinned path | Native deterministic fixture / review |
| --- | --- |
| draw.rs::State::bind, heap_buffers (ONCE/FRAME/WHOLE) | Record two lists sharing heap in same frame and exercise skipped refresh; each must independently pin actual required wrapper/resource/backing state. Include directly indexed resources and dynamic slots. |
| descriptor/host.rs::HostHeap::keep, descriptor.rs::Heap::drop/release_dynamic | Replace descriptor before submit and in-flight, unregister title wrapper, reuse address and dynamic slots. Old/new GPU-visible resources must stay valid for all permitted readers. Stable ID cannot be raw pointer. |
| list.rs::Detached/reset, host.rs::HostList::keep/defer_refresh/reset and Deferred | Recorded-unsubmitted, detached list, repeated submission, reset/drop of wrapper before and after completion. Inspect actual retained Arc/COM resources, not just modeled counts. |
| host.rs::Flight/relay_land/retire/bury | Fake/test fence domain and deterministic completion gates, actual publication/late signals, failed/device-loss path. No release merely because a fence number matches another domain. |
| draw.rs global pass and actual mapping locks | Two concurrent heaps and frames; preserve baseline serialization, prove lock order before any per-owner mutex change. |

First native step should observe ownership without releasing existing
RANGES or directory references. Use synthetic resources and deterministic
test-only hooks; no private title data. AI1 must approve actual fixture
symbols, lock order, mapping/alias and lifetime contract; AI3 review
descriptor/reporting scope. Test exact prepared #18 and both profiles.
No source application, native registration or runtime switch is added.

Eight compiled portable cases cover recorded/skipped lists, reused
address, slot replacement, overlapping replays/reset, dropping recording
after submit, device loss/uncertain publication, unwind, global pass
serialization. They prove only model behavior. All actual native
ownership and memory/FPS evidence remains outstanding.
