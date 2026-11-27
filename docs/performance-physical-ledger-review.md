# Physical-memory logical accounting review (P10/P18/P24)

Frozen #18 dbac4c6ea21d9580f5b0bd39ba2b9d6c4eb6f2b1; upstream 51700c6d43a3507fa65e50fe4bb64074ce706cd4. Standalone Rust probe only, no runtime registration. These balances are separate logical measures, not additive or resident RAM. An event source and coherent sampling contract must be reviewed before instrumentation. Checked model rejects arithmetic underflow/overflow or impossible unique view bytes; uncertainty invalidates attribution rather than silently clipping.

| Population | Proposed observation point | Limit |
|---|---|---|
| Section handle capacity | Successful creation in XMemAllocatePhysicalPages; actual successful CloseHandle in Section::drop | Arc lifetime distinct from page IDs and OS view lifetime; handle closed does not imply backing released |
| Page-ID bytes | Actual insert/remove in Physical::pages under current lock | Duplicate or missing removal cannot decrement |
| Title view logical bytes | Successful map/commit and recorded insert in Physical::views; checked unmap_with removes only after host success | Failed unmap retains view, partial neighbor remap counts successful pieces only; replacement needs exact old/new accounting |
| Unique shown backing pages | Existing Physical::shown entry first/last address transition, not a new index or scan | 64KiB pages, alias excess is logical view bytes minus unique shown bytes; no residency inference |
| Temporary storage view bytes | View::map host map success, View::drop successful host unmap (including commit-failure cleanup) | Failure/uncertain cleanup must mark unknown, not pretend freed |
| Failed/untracked operations | Host failures, especially map commit rollback failure or unexpected returned address | No new recovery behavior; stop attribution if unknown |

The pinned Section::drop currently ignores CloseHandle result, View::drop ignores UnmapViewOfFile result, and map commit-failure rollback ignores the unmap result. These are observation gaps, not evidence a failure occurred. A later diagnostic hook must observe outcomes without changing control flow, locks, ownership, lifetime, cleanup or guard. Existing checked unmap path restores GPU metadata when host unmap fails; do not alter it. OWN persistent copy-back views and GPU copies are explicitly outside this model. Backing-mode subdivision requires verified provenance; no raw addresses/handles/paths or title content. No new scans, per-page log lines or locks. Actual concurrent snapshot consistency, counter overhead, sampling interval and exact source composition/native checks remain open. Eight synthetic tests prove model behavior only, not native source correctness or FPS. D22 no title launch.
