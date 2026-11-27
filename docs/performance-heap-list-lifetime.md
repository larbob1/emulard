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

## D18 actual recording-path fixture (first slice)

The isolated candidate adds cfg(test) inspection to actual HostList and
State, and a diagnostics-only ignored test in descriptor.rs. Four exact
anchors checked against pinned raw source. Existing patcher applies only
test code; no normal runtime behavior changes. It constructs one synthetic
placed buffer SRV, checks actual host slot backing and drops temporary Arc
and IUnknown references before inspecting the lists. Observe explicit
Step::Refresh/GpuWrite and kept IUnknown identities, not total ownership.
Two same-frame lists call actual State::heap_buffers: first must record
a refresh, repeat on first must preserve counts, second skips pass. The
baseline assertion that second has no explicit buffer pin in these fields
is a **negative observation**, not a claim of missing all ownership.
Other references (heap COM, global cache, directory, resource holders)
are deliberately left intact. Actual State::bind is not invoked.

Run separately, after full preparation and coordinator registration/review:

    VICTORY_D3D12_WARP=1 cargo test --locked -p victory-gpu --features diagnostics heap_recording_observation_same_frame_refresh_and_skip -- --ignored --test-threads=1

Exactly one test expected, no silent software/device skip; do not run
on a hardware adapter. All global state and the synthetic allocation
remain valid until the isolated process exits; no unregistration or free
under retained cache references. Both lists are closed/reset unsubmitted,
no GPU execution. Wrapper destruction is tested without dereferencing
it afterwards. No production cleanup approval, no actual replay or
in-flight fence proof; next fixtures must cover real bind and detach,
slot replacement and submitted/replayed list retention, with independent
fence/late publication proof. Three Python checks validate wiring only;
native compilation and WARP execution are outstanding.

### Deferred slot correction and positive control

Pinned descriptor/host.rs::HostHeap::mirror defers buffer descriptors when
for_draw is false. The fixture now requires an unmaterialized slot before
State::heap_buffers, then checks the actual materialized slot and the same
Shadow identity/range after the first pass. Temporary lookup references
are dropped before inspecting deferred list state. The stride table has a
separate COM identity: each list must hold exactly one explicit stride pin
(including the second list's FRAME skip), ONCE cannot duplicate it, and
reset clears it. This positive control distinguishes a functioning kept
COM observer from an absence of explicit buffer pins. It does not prove
all owners or GPU execution safety. No production semantics are changed.
