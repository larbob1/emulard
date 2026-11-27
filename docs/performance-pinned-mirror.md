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
