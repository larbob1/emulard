# Live pinned backing mirror (P04/P10)

Opt-in `VICTORY_MAP_PINNED_MIRROR=1` mirrors successful native map and unmap
events under the existing physical and renderer mapping locks. Whole-view
removal followed by neighbor reconstruction matches the existing host
event order. Each interval retains the existing Arc<Section> object.
A returned plan clones those references, coalesces adjacent offsets only
for the same live object, and refuses holes and arithmetic overflow.
Pointer equality is meaningful while both Arcs are live; no raw handle or
address identity is exported. Unexpected overlapping inserts or mismatched
removals disable and clear the observational mirror.

The native fixture compares its resolved spans to the HLE's authoritative
view lookup, including an injected host unmap refusal. Portable tests verify
lifetime after retirement, distinct objects with equal values, partial
reconstruction and checked failures. This pins the section handle, not a
mapped byte view, CPU data freshness, or GPU completion. No GPU reader
consumes these plans yet. No host mappings are removed; the mirror adds
overhead and is not a gameplay optimization itself. Default off.

Next gate: audit native section opening and protection, give a bounded
read-only GPU consumer a synchronized backing read, and test retirement
against GPU fences. Direct CPU accesses, GPU writes, external frees and
ownership must be audited before eliminating any host mappings. P04/P10
remain open.

## Native backing-read fixture

A test-only reader opens read-only section views directly from pinned plans, with an 8 MiB bound and all-or-nothing output. Tests scattered page boundaries, replacement of a title alias, unmap/free of all original page IDs, old-plan reads after retirement, and final Arc release. This uses fixture-owned already-committed memory with no concurrent writers. Production read permissions, live GPU/CPU writes, GPU fence completion, mapping lifetime, and consumer integration remain unproven. It deliberately does not add a production read callback or enable a new runtime flag. Native CI pending.

## P10/P12 exact alias projection follow-up

Isolated child of 49ca476. Test-only PinnedViews methods project checked backing byte spans onto all tracked virtual views, ordered by address, using Arc identity rather than recyclable handles; scan/output cap refuses the entire answer. Current-plan comparison checks exact resolved backing identity/offset/length, not data freshness or ABA. These methods are compiled only in tests, not called in gameplay. Native fixture adds projection, refusal, remap, and retirement assertions under Physical lock; portable oracle covers 80 aliases and byte boundaries.

Pinned upstream audit (51700c6): xmem::map/unmap execute under PHYSICAL -> watch::MAPPING for relevant remaps; do not reverse that ordering by calling HLE while holding MAPPING. watch::title_memory_reading excludes mapping changes only, not arbitrary CPU, DirectStorage or GPU writes. inplace::views_of_section deliberately omits pages above MANY_VIEWS; unsuitable as complete alias publication. xmem::write_physical and page_window write through separate views; raw CPU writes, untracked/free/protect paths and pending GPU writes are not captured by this mirror. texture::refresh_unlocked uses host::read_into and hashes the copy; replacing this read needs permissions, writer synchronization and actual byte freshness, not just retained Section.

Use complete footprints only within audited domain; unknown or over-cap => conservative global invalidation or baseline. No callback, new runtime flag, production synchronization change, or host remap elimination. No FPS result. Native run remains a separate gate.
