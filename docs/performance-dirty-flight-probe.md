# P13/P14 — dirty flight model (not production)

Pinned runtime: `51700c6d43a3507fa65e50fe4bb64074ce706cd4`. This isolated
CPU-only prototype is not registered in the runtime builder. No new
runtime flag, shader instrumentation, GPU readback, fence or mapping code.

## Contract

The model owns one immutable region and a distinct per-flight ticket.
The region is capped at 4096 4 KiB pages for sparse planning (16 MiB
aligned; edge pages are clipped); larger regions use the authoritative
baseline. An incoming bitmap must match the ticket and fence, exact
word count and zero unused tail bits. It can produce sparse candidate
compare ranges only when every coverage assertion is true. Otherwise
use the existing complete authoritative path, NOT just this region if
a write footprint is unknown. A zero bitmap is never proof of coverage.

The bitmap represents pages possibly written, not bytes actually changed.
Existing byte comparison, CPU conflict precedence, alias notifications and
visibility remain authoritative. The model does not validate store addresses
or instrument actual writers. Real implementation must verify descriptor
lifetime and all store/atomic/copy/resolve/clear writers, out-of-domain
writes, fault status and actual backing identity for each flight.

A fence value is meaningful only in the same queue/device domain. The
model checks a distinct fence-domain identity as well as the value; the
caller still supplies actual verified completion. Device-loss sentinel or
incomplete/wrong-domain fence cannot plan. The retained Arc is a stand-in
for an aggregate of actual backing and descriptor leases. Retirement is
explicitly permitted only after handback, generation/alias publication,
readback visibility and ordered title signals are all acknowledged.
The model now gates effects through four ordered stages. A completed stage
cannot execute again. A proven no-effect failure permits retry of only
that stage; an uncertain outcome or unwind quarantines the flight before
any automatic retry or retirement. This models sequencing, not actual
writes, recovery, locks or GPU synchronization. Real ownership must retain
failed flights independently of caller drop and implement explicit
reconciliation, ordered shutdown and device-loss handling. The stages are
logical milestones, not permission to move existing runtime operations.
Readback operations that mutate title memory must also publish their
actual alias/generation changes under the agreed mutation guard before
visibility is acknowledged. Title signaling and resource reuse ordering
across multiple flights remains a coordinator-reviewed requirement.

## Proposed integration boundaries — approval required

| Read-only upstream anchor | Responsibility |
| --- | --- |
| host.rs::Flight, CardPlan | allocate unique per-flight bitmap and retain descriptor/backing leases |
| shader lowering and descriptor resolution | prove complete store/atomic and descriptor coverage, otherwise authoritative fallback |
| host.rs::relay_worker | actual fence domain completion; no early reuse |
| host.rs::relay_land, shadow.rs::card_merge/copy_back_done | existing exact merge and actual publication before marking complete |
| host.rs::card_done, FINISHED/bury | retire only after the same flight's handback and generation publication |

Coordinate with AI 1 on P12 generation tokens, external lock ordering,
complete alias mutation footprints, actual lease identity, unknown-writer
global invalidation and failure handling. Coordinate with AI 3 on counters
and matched transfer/CPU/wall-time evidence. No production integration
until approved and all native suites pass; no assumed FPS gain.

## Tests

`python -m unittest discover -s tools -p test_dirty_flight.py`
compiles the actual model with rustc. Fifteen cases exercise partial-page
clipping, zero/full masks, incomplete fence and device loss, stale
ticket/fence, every coverage category, malformed/oversized masks,
publication failure, wrong fence domain, required readback/signal acknowledgements and independent retained leases, plus randomized
page oracle across bitmap word boundaries. New cases reject duplicate/out-of-order effects, retry proven no-effect failures without replaying successful stages, quarantine uncertain outcomes at every stage, and quarantine unwinding effects. CPU-only, no hardware tests.

## Checked marker and observation-only oracle

The serial marker accepts already-resolved backing byte coordinates, using
an opaque identity rather than virtual addresses or descriptor slots. It
checks the entire nonempty span before OR-ing inclusive page bits, with
bounded capacity and word-boundary handling. Invalid spans, overflow,
unknown footprints or wrong backing permanently invalidate that marker.
Finish consumes the marker and requires independently established complete
coverage. A missing report takes the existing authoritative path.

Observation requires the same flight, backing and completed fence domain,
plus independently provided full completed baseline changed spans in the
same region. It counts candidate, changed, missed and extra pages without
changing either rendering or copy-back. Missing evidence is not an empty
scan. False negatives must disqualify sparse eligibility in any future
runtime integration; this observation-only model does not enforce a
production acceptance policy or change Flight::plan. A zero miss count is
not proof of all writer coverage. Both paths use synthetic backing identities;
actual alias projection, complete mutation spans and retention belong to
AI1's P10/P12 work. Different aliases must first resolve to the same stable
backing coordinates. No production alias projection or GPU atomic marking
is implemented. The actual prepared runtime remains unchanged.

Seven additional regression cases (22 total) cover word/page crossings,
invalid/unknown spans, identity/coverage/capacity, high-address clipping,
false negatives and false positives, missing/unrelated scan evidence, and
a deterministic page-intersection oracle. No actual transfer reduction.

## Multi-backing observation and bounded readback lifecycle (CPU-only)

A multi-region comparison accepts up to 64 distinct opaque backing identities
and 4096 aggregate pages, one immutable region per backing. Aliases must
already have been resolved by the real mapping owner. Reject duplicate
backing identities instead of attempting incomplete coalescing. Unknown or
out-of-range writes invalidate the whole plan. Completed scan evidence must
cover every region exactly once, match the flight and fence and carry the
same region and backing. Missing scan is not empty scan; bound input to
65536 changed spans. Consumed comparison returns Matched, Missed or
Ineligible; any missed page rejects Match. No result authorizes skipping
transfers. Same numerical offsets in different backings are independent.

The readback slot model (probes/readback_slots.rs) has at most 64 fixed
capacity slots under a checked aggregate byte budget. Reserve best fit,
return Full immediately if unavailable; caller retains baseline fallback
and must not wait under mapping locks. Lease identity is distinct from slot
index, preventing old leases from operating on reused slots. State order:
Reserved -> InFlight -> Complete -> Copied -> Published -> Signaled ->
retired. Completion checks the same fence domain and rejects device loss.
Only proven no-effect submission failure or unused reservation may cancel;
unknown outcomes and unwind quarantine before retry and retain the pin.
Copy and publication represent actual readback mutations and complete
alias/generation visibility; title signals are logical ordered milestones,
not permission to reorder existing runtime signals. No real GPU allocation,
readback scheduling, synchronization or drop-safe failure retention yet.
Pool teardown/device-loss reconciliation and cross-flight ordering require
an external owner; never drop an active pool as a cancellation strategy.

Five new multi-backing cases (27 dirty-flight total) and six readback-slot
cases run in synthetic CI via Python discovery. No prepared runtime changes.
