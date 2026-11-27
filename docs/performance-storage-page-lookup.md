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
