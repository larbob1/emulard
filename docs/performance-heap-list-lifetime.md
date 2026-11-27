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

## Retirement publication review (P15/P18; not a runtime patch)

Pinned upstream 51700c6: host.rs::retire captures STARTED, tests FINISHED,
then locks RETIRED and enqueues. submit, settle and relay_land store
FINISHED before bury partitions RETIRED under its mutex. A thread paused
between the first completion test and enqueue may add an already-complete
entry after the matching drain. The next drain can reclaim it; this is a
retention ordering gap, not demonstrated title memory growth.

The standalone retirement_publication_review.rs model forces that ordering
and the converse (enqueue before drain). A possible correction, still
review-only, rechecks the captured boundary under RETIRED, then releases
the mutex before destruction. The model assumes the captured submission
is the last relevant use. Seven cases include a weak-reference sentinel
that checks destruction outside the retirement mutex, not outside all
caller locks. The ordering test does not establish real fence-domain
equivalence or safety of any particular resource.

### Pinned caller inventory (read-only)

- descriptor/host.rs::HostHeap::keep replaces a kept COM reference while
  holding the slot's kept mutex. Retire can already destroy immediately;
  the proposed recheck must not add a RETIRED-held destructor or create a
  new lock order. Mutable slot visibility and independent recording pins
  remain separate prerequisites.
- resource.rs::let_go_idle removes a host texture only after existing
  idle, Arc and COM reference tests; unstage occurs under made's lock.
  Resource::drop retires the host copy and colour twin, then forgets
  texture/descriptor records. Neither call proves all recorded users
  simply by reading a submission count.
- shadow.rs::let_go_idle removes eligible LOOSE entries under the map
  mutex and retires after unlocking; in_place_let_go removes overlapping
  in-place copies from LOOSE and buffer tables before retirement. Preserve
  alias/backing obligations and all independent Arc/COM owners; do not
  weaken existing range, mapping or idle checks.

Only these inspected raw pinned callers are covered here; the combined
prepared postimage and other callers need coordinator review. No new
resource sweep, reclamation threshold, release flag or actual GPU
submission is introduced. A production proposal requires AI1/AI3
agreement, exact prepared source audit, deterministic native ordering
and independently established recorded/in-flight/replay lifetime and
completion contracts. No RSS or FPS attribution.

## Native detached-recording milestone and completion review

Exact isolated #53 (8b3d97c72dc5d87af55cbdd3ca1d432851a4e268,
based on ad4cc8956c11c760b2fb263a65bcba38d7a813ca) native CI
45952737960/job140352102981 completed successfully. Both fresh
VICTORY_D3D12_WARP=1 fixtures passed exactly one test: the expanded
heap slot rewrite observation and detached list reset/release ownership.
Both release and diagnostics builds passed. This supersedes the earlier
pending native status for those exact fixtures only. Neither fixture
submits GPU commands, so actual in-flight or replay ownership is not proven.

Raw pinned host.rs (51700c6) review:
- execute_late transfers Detached lists and order into Flight after submit,
  retaining the submission guard through insertion into LINE. Flight also
  retains card/back/texture range information. The queue fence value and
  logical submission number are distinct.
- relay_worker uses the observed host fence value and landable to select
  an ordered prefix. relay_land performs readbacks and hand-back before
  advancing FINISHED and burying retired objects. land transfers landed
  lists to recycle outside LINE; this is separate from GPU completion.
- Non-relay settle, around lines 5317-5327, warns on
  SetEventOnCompletion failure and continues; it also ignores the
  WaitForSingleObject return value. The later device-removal check alone
  cannot establish that the requested fence completed. The normal path
  performs hand-back, readbacks, bottom-of-pipe writes/signals, FINISHED
  publication, retirement and eventual list recycling.
- Synchronous submit, around lines 5608-5623, likewise warns on Signal
  or SetEventOnCompletion failure and ignores the wait result. The
  subsequent FINISHED.store and bury around 5646 are not guarded by
  an independently verified completed-fence value in this raw path.

This is a potential failure-path correctness gap, not a demonstrated
failure on WARP, Proton or a title. The two inspected graphics patch
files do not directly modify those wait calls; the full combined
prepared postimage and other completion domains still need review.
Do not infer safe earlier reclamation from a successful normal-path
ownership fixture, or from logical submission numbers alone.

Proposed review gate, not an implementation: distinguish successful
event registration, successful wait return, actual completed target
and device-removal/unknown outcomes. In isolated test-only failure
seams, cover signal failure, event registration failure, failed wait,
unreached target, device removal and successful completion. An
unconfirmed submission must not be treated as completed by a new
reclamation policy, publish successful title completion, or recycle
in-flight list owners. A reviewed recovery/termination contract must
preserve ownership until safe, avoid indefinite waits or retry loops,
and not turn uncertainty into a successful fence signal. Confirm the
actual prepared source and coordinate with AI1/AI3 before changing
shared submission or retirement behavior. No title launch authorized.
