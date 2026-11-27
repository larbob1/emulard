# Per-range generation model (P12)

This standalone prototype tracks the last mutation generation of disjoint
byte intervals, not a global invalidation on every mapping. A snapshot
token records a checked range and the current generation, tied to its
tracker identity. A later mutation invalidates earlier overlapping
tokens, while disjoint snapshots remain valid. A multi-range alias event
shares one generation. Exact interval splits preserve older generations.

Metadata is bounded (default 4096 intervals); pressure or an unknown
writer footprint causes conservative global invalidation. Generation
exhaustion permanently disables the tracker rather than wrapping.
The tracker must be externally serialized with the corresponding writer
events and reader snapshot/validation. Its bounded stored metadata does
not cap the caller's input array; an integration must bound work per event.

## Production acceptance gates

- Identify every writer that invalidates a snapshot: host view removal
  and restoration, virtual free/protect, CPU and DirectStorage writes,
  GPU completion-scoped writes and all reverse aliases. Remap footprints
  must include entire removed views, not only the requested range.
- Define lock ordering and acquire a range read guard before reading
  mapped bytes. Tokens do not pin mapped memory or synchronize content.
- Verify the snapshot's token at publication under the same synchronization
  that prevents a writer racing the publication. A validity check alone
  followed by unlocked publication is insufficient.
- Begin with an observational mirror alongside the global epoch, compare
  results using synthetic replay and real title-local numeric telemetry,
  then consider an opt-in narrow texture consumer. Unknown paths must
  invalidate all; no skipping invalidations or dropping the existing guard.
- Coordinate with graphics on GPU fence retirement and dirty notifications
  before production changes. Compare with the same gameplay workload and
  measure actual snapshot retries, bytes copied, wait time and FPS.

No native runtime changes, GPU writes, host mappings or new environment
switches. This is prerequisite logic, not a measured performance gain.
