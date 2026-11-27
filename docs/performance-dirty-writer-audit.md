# P13/P14 — initial GPU writer coverage inventory (read-only)

Source revision: `51700c6d43a3507fa65e50fe4bb64074ce706cd4`, upstream
fxceless/victory-fork. This is an initial pinned-source audit, not proof
of exhaustive coverage of prepared code or any title. No implementation
permission or shader/command changes. Before using sparse masks, repeat
against the exact cumulative prepared runtime and inspect every writer
(including dynamically generated host helper shaders).

| Location / symbol (pinned line approx.) | Required instrumentation or fallback |
| --- | --- |
| shader emit/lower.rs::memory (2820) | Directory addresses use 64 KiB pages; rawBufferStore fault reporting is internal, not a title dirty page. Preserve missing-page handling; fault or unknown mapping invalidates sparse eligibility. |
| lower.rs::memory_flat (2888) | Global raw stores and atomicBinOp/compareExchange. Resolve each active lane, byte span and cross-page footprint against retained backing, not just VA. Preserve guard, mask and atomic result. |
| lower.rs::buffer (9912) | Raw, typed and structured stores plus atomics. Descriptor base, element index/stride, offsets, typed format, active lanes, component mask, access width and bounds all matter. Unknown format or dynamic mapping stays authoritative. |
| lower.rs::image (9119) | TextureStore and 32/64-bit image atomics. Track subresource/plane/twin/alias ownership; no linear page inference from texture coordinates. Exclude initially. |
| lower.rs::lane_heap_index/heap_index/descriptor_phi (6330–6525), descriptor_data.rs::descriptor_data | Dynamic/per-lane selection and descriptor mutation: complete descriptor resolution and lease identity required. Unknown paths stay authoritative. |
| gpu draw.rs::bind, tables, readable (3478), root_view, execute_indirect (3058) | Existing buffer UAV refresh and gpu_writes declarations and texture_written path; STORES/write_skip is not proof of complete dirty instrumentation. Cover root views, direct indexing, mesh/compute/graphics and indirect arguments. |
| gpu descriptor/host.rs::mirror, mirror_copied, buffer_uav, raw_uav_at, twin_uav | Record actual backing and descriptor versions/leases at submission, not recyclable slot/VA; audit mutations, reuse, null descriptors and aliases. |
| gpu list.rs::copy_buffer_region/copy_resource/copy_texture_region/resolve, clear_rtv/clear_dsv (816–1343) | Existing GPU copy, texture and attachment paths remain authoritative; explicit destinations and full affected views needed, not shader bits. |
| list.rs::copy_memory (1352), resolve_queries (1400), write32/write64/defer_write (2019+) | Deferred CPU-side title mutations and bottom-of-pipe values; not GPU bitmap evidence. Publish actual mutation/aliases before visibility, preserve queue cuts and signal ordering. |
| host.rs::defer_gpu_write/defer_read_back (6757+), Step::Copy/Fill/Run/Host/GpuWrite, card_before/card_back/relay_card_back | Preserve existing declarations, readback/copy/compare helper work, pending writers, unknown closures and alias/snapshot guards; helper UAVs must not be confused with title buffers. |
| host.rs::Flight/CardPlan, relay_worker, relay_land, read_backs, card_done, FINISHED/bury; shadow.rs::copy_back_done/card_merge/card_merge_relay | Completion and publication ownership: verified same fence domain, actual handback and all readback writes, mutation generations and aliases, ordered title-visible completion, then release/reuse as appropriate. No early clearing or unsafe retirement. |

## Proposed first production boundary (not authorized)

Start with a single well-defined buffer-only domain, on an opt-in shadow
comparison mode that does **not** skip baseline transfers or writes.
Record conservative per-flight dirty candidates and compare against the
existing completed byte comparison. A single false negative, unknown
writer, descriptor mutation, fault, missing report, overflow, or mapping
identity mismatch disables sparse eligibility. Texture/image/indirect
coverage remains unproven; do not infer their correctness from buffer
tests. Keep baseline as authoritative even for a valid zero mask until
complete instrumented coverage and matched GPU fixtures are established.

4 KiB dirty units are prototype units, not the 64 KiB address directory
or existing compare pieces. Use checked byte intervals, correct mask and
width, stable backing identity and complete alias translation; overlapping
writes must OR bits atomically. False positives are acceptable, false
negatives are not. Descriptor slots, bitmap buffers and backing leases
remain submission-owned until actual verified completion and publication.

AI1 must approve mapping/mutation guard scope, lock order and all live alias
generation updates; unknown mutation footprints call invalidate_all under
the same guard. Pending writes must exclude stale readers independently
of generation tokens. AI2 must audit prepared lowerers, helper shaders,
command methods, descriptor/root signature capacity and shader cache
fingerprints before changing any source. AI3 must agree numeric-only
telemetry: coverage rejection reasons, compared candidate pages, actual
baseline changed pages, missed pages and authoritative fallbacks. No
instrumentation, telemetry schema, new flag, or FPS claim in this document.

## Failure handling

Only a stage proven to have no effect may retry in place. If handback,
generation invalidation, a readback write or signal has partially succeeded
or its result is unknown, retain leases, quarantine and reject blind
replay. A real owner must durably retain the failed work and define
reconciliation, cross-flight ordering and terminal device-loss handling.
No production action should be inferred from a simulated acknowledgement.
