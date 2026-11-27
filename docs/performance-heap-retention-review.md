# Heap-pass cache retention — review only (P15/P17/P18)

Base frozen #18 `dbac4c6ea21d9580f5b0bd39ba2b9d6c4eb6f2b1`; pinned upstream `51700c6d43a3507fa65e50fe4bb64074ce706cd4`.
B003 exact #18 offline evidence reports live host-copy windows 28 to 3000
MiB across 17s, live texture staging 342 to 19 MiB, working set 3637 to
12430 MiB, private bytes 2566 to 3191 MiB, nonlocal DXGI 1001 to 4309 MiB.
Independent counters overlap; do not sum or infer exact RSS ownership.
No evidence establishes dead heap cache share or that any heap was destroyed.

## Source-level lifetime issue

Pinned draw.rs::State::heap_buffers uses static RANGES keyed by
HostHeap address. Every entry retains a per-slot Arc<Shadow> and pass
counter; the whole map is never pruned by heap destruction in inspected
source. Heap::drop only unregisters the title heap; HostHeap has no custom
Drop. A dead heap's cache can therefore keep otherwise idle shadows alive.
A reused heap address can also inherit stale pass state and ranges until a
full pass. The existing periodic full pass clears only the selected heap.
This is a source-level retention risk, not proof of B003 attribution.

HostHeap::kept holds COM resources for descriptor slots until replacement;
keep retires old COM references. State::bind keeps host heap COM objects
on the list. Shadow::let_go_idle requires sole Arc and sole COM ref,
age and four frames; then host::retire gates release on STARTED/FINISHED.
HostList::defer_refresh clones the shadow in Step::Refresh until reset.
These guards MUST remain unchanged. Arc and COM holder categories can
overlap. A cached Arc is not a proof of GPU fence completion. Existing
heap destruction and list replay ownership need a separate native audit,
including global FRAME early return, WHOLE refresh throttling and lists
that do not record refresh steps for every referenced resource.

## Proposed owner-local cache (not applied)

Move the range cache to HostHeap::pass_ranges, initialized empty at heap
creation. Preserve per-heap incremental pass count, clear-every-16
behavior, buffer_changes, range reconstruction and refresh calls. Cache
references naturally drop with the owner; a new heap starts fresh even
at a reused address. Four exact anchors checked against pinned raw source.
`python tools/propose_heap_pass_retention.py <prepared-root>` prints
only an in-memory diff and rejects drift/reapplication. No builder entry.
No runtime flag or production behavior changed. If approved for
production, use a default-off experiment with baseline fallback and
review the per-heap vs previous global lock change, all concurrent passes,
lock ordering, GPU lifetime and full prepared composition. Do not release
actual slots, bypass retire, lower sweep age, or change window grid/tails.
Do not equate heap destruction with completion of previously recorded
lists. Confirm independent ownership of each consumed Shadow, including
non-first-pass lists; if not established, do not apply.

Four portable model cases cover cache-only release, independent list pin,
fresh owner and distinct owner/slot replacement. They do not execute
the actual D3D12 or GPU paths. Two exact preview tests cover drift,
duplicates and nonmutation. AI1/AI3 review and actual native heap destroy/
address reuse + recorded/inflight list fixtures required. Existing
numeric holder counts, union coverage, exact-view stats and sweep
releases requested from AI4 offline. No new launch, memory saving or FPS
claim. No canonical/shared files modified.
