# GPU completion / readback review source gate

Review only. Frozen #18 `dbac4c6ea21d9580f5b0bd39ba2b9d6c4eb6f2b1`,
upstream `51700c6d43a3507fa65e50fe4bb64074ce706cd4`.
This is not a production correction, native test registration, or approval to
change release or synchronization policy.

## Source identity

The full paired preparation manifest was inspected (14 direct patches and
13 scripts). Only PresentX and present capture modify host.rs; 11+5 hunks were
projected in order with exact context/offset/count checks. Upstream host blob
458d146aedf6f13dac80782d283a048d80e4a931; first projected postimage
8b540a23daf70e02d5720da56e5858cc62b94c36 matches the patch's abbreviated index.
The frozen shadow.rs has six exact replacement pairs from apply_gpu_copy_perf.py
(blob ca74c78c0eb9c32529c4c941a526ecb78a995801), all uniquely applied to
upstream 4fa43df7932bb6692d164384cd28b1f08f3001ee in memory.
The other three source paths have no manifest writes.

The five expected LF Git blob identities are in
tools/check_gpu_completion_review_sources.py. On a separately authorized
already-prepared, title-free frozen #18 checkout, the coordinator can run:

    python tools/check_gpu_completion_review_sources.py <prepared-checkout>

All five must match; mismatches/unreadable paths fail closed. CRLF is
normalized, no other whitespace changes are ignored. This read-only check
does not execute preparation or verify other dependencies/builds; even a
match is not proof of runtime behavior. Do not reuse these pins for a changed
candidate or alter the expected hashes to make a mismatch pass. Unit tests
exercise synthetic data only, not the actual prepared checkout.

## Proposed test-only observation matrix (not authorized native seams)

| Case | Distinguish | Required evidence |
| --- | --- | --- |
| Valid texture readback | Success vs attempted landing | Byte-exact destination, preserved untouched subresources, actual map/unmap receipt |
| Invalidated ticket | Intended stale skip | No destination write, old ticket rejected, replacement remains unchanged |
| Initial read failure | No effect vs successful read | Original destination unchanged; no tiling/copy recorded |
| Map error or null | Failure vs stale skip | No row/texture copy; mapping ownership accounted for |
| Tiling failure after earlier subresource | Scratch changes vs published bytes | Unmap, destination unchanged; no inferred successful publication |
| Multiple buffer readbacks | Known prefix vs failed later buffer | Distinct per-buffer receipts and sentinel bytes; no fake rollback |
| Destination partial copy | Attempted range vs committed bytes | Known completed spans, unknown spans explicit; independent byte oracle |
| Diagnostics skip | Deliberate skip vs actual transfer | Explicit skip outcome, never count as byte success |
| Copy lane receipt | Direct/copy/fetch fence mismatch or removal | Separate fence domains, confirmed query/target and wait status |
| Pending retirement | Logical completion vs actual owner release | Observe retained list/snapshot/COM owners, no release solely on numeric receipt |

Actual native fixture design requires AI1 review of mapping, guard, alias and
notification obligations and AI3 review of outcome semantics. Preserve the
existing intended stale and unmapped behavior, avoid blanket hold/retry or
recovery policies, and do not inject failures into live title execution.
Use synthetic allocations only, bounded isolated processes, exact test
filters and both build profiles where required. All previous snapshots and
CI receipts stay separate. No local launch, merge, or performance claim.
