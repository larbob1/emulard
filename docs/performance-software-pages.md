# Software GPU page-table prototype (P04/P10)

This branch supplies a portable sparse page table with 64 KiB entries,
logical section identity plus generation, checked map/unmap operations,
complete-source snapshot aliases, coalesced backing span resolution and
read plans that reject holes or missing backing before modifying output.
It does not use native host addresses. The model's reader uses borrowed
backing slices; actual native section pinning and fence retirement are not
implemented. Snapshot overlap behavior is deliberately a model contract,
not a claim about the existing title API.

The prepared native tile replay fixture now compares three representations:
native mapped views, the original dense reference table, and the sparse
software table. Existing alias mutations, cross-page reads, missing pages
and detiling compare actual backing data. Captured replay remains local-only.
The portable model also has deterministic randomized mapping tests.

## Production integration gates (not done)

1. Inventory CopyPageMappingsBatchX call sites and consumers. Classify
   ranges that can be proved GPU-only. CPU-visible memory must retain host
   views, including aliases, direct title pointers, faults and HLE writes.
2. Introduce stable native backing-section objects with generation and
   lifetime pins. Retire only after all readers and GPU submissions finish.
3. Mirror successful host mapping events into a checked page table under
   the existing mapping lock. Compare reads/coverage against host views,
   track divergences and fall back before changing real behavior.
4. Route a narrow GPU read-only consumer to pinned backing spans; validate
   actual layout/detile, cache identity, dirty notifications and remap races.
5. Only after CPU-access proof and ownership validation, consider omitting
   host remaps for eligible GPU-only ranges. Preserve host fallback.
6. Validate GPU writes/readbacks/alias invalidation and submission fences
   before extending the optimized path to writable GPU resources.

No production mapping path changes in this branch, no new runtime switch,
no claimed host calls saved or measured FPS improvement. P04/P08/P10
remain unresolved. Use the existing working Proton binary for gameplay.
