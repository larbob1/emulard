# DirectStorage physical-page lookup experiment

Opt-in `VICTORY_STORAGE_PAGE_LOOKUP=1` replaces the temporary run vector
for xmem::pages_known with an existence check and for page_window with
single-contiguous-run resolution. Keeps the same checked byte-range math,
Arc section identity, page ordering, and existing View::map commit/unmap.
Unknown/noncontiguous input still returns failure to the original caller,
which retains write_physical fallback. No new cache or lifetime assumptions.
The flag defaults off. No host map/unmap calls are eliminated.

Native regression compares both lookup helpers against the existing runs()
on contiguous, duplicate, reversed, mixed-section, missing, partial,
empty, out-of-range and overflowing requests, and checks actual cross-page
window bytes in both flag modes. Patcher and pinned preparation tests
verify composition; full native validation is required.

This targets CPU overhead and physical mutex hold time, not GPU critical
path by itself. On fragmented input early refusal may avoid work; on
singleton/contiguous input the gain may be small. Use matched owner
gameplay and DirectStorage metrics before recommending the switch.

## Single-variable #18-derived playtest

This isolated candidate uses frozen #18 dbac4c6 as its base and exact source/test blobs from #21 39a481d; only builder/validation/workflow registration and this guide are added. No graphics, memory mapping, existing flag defaults or reporting changes. Native #21 passed 29 suites and both profiles, but composition is checked independently here. First establish actual correct gameplay using frozen #18. Then in this candidate use identical lawful, read-only local workload and compare VICTORY_STORAGE_PAGE_LOOKUP=0 versus 1, keeping all other options and cache state unchanged. Confirm storage work was exercised; collect existing storage timings, requests and frame metrics with AI3/AI4. Loading-only data is not gameplay; no gain if storage not exercised. No host map calls eliminated, no speed claim, no merge. Preserve frozen #18 and prior executable. No changes to title files.
