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
Failed acknowledgements retain the lease. A real owner must retain failed flights even if an API object is
dropped, prevent duplicate publication on partial failure, and implement
ordered shutdown/device-loss recovery. This serial model is not such an
owner or a synchronization primitive; the bool acknowledgements are not
proof that real writes or generation invalidations happened.

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
compiles the actual model with rustc. Eleven cases exercise partial-page
clipping, zero/full masks, incomplete fence and device loss, stale
ticket/fence, every coverage category, malformed/oversized masks,
publication failure, wrong fence domain, required readback/signal acknowledgements and independent retained leases, plus randomized
page oracle across bitmap word boundaries. CPU-only, no hardware tests.
