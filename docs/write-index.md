# GPU write declaration indexing

The existing runtime repeatedly searches vectors of copies and their write ranges while collecting a submission. This candidate replaces those linear duplicate checks with an index keyed by the live copy identity and exact range. It preserves first-seen ordering and overlapping ranges, which is important because distinct host copies can alias the same title memory.

The CPU and GPU-card writeback paths share the collector. All existing snapshots, completion ordering, range comparison, and actual writeback behavior remain unchanged. It does not track GPU-dirty pages and cannot eliminate snapshot or comparison bandwidth. The additional hash tables have a memory and CPU cost; the expected benefit is in duplicate-heavy workloads, not guaranteed in small ones.

The regression test checks order, duplicate removal and a 6,400-declaration workload with 64 unique ranges. Another four Python tests check the source preparation. The earlier synthetic lighting test incorrectly assumed every replacement removes its anchor, including a replacement that deliberately keeps the old function declaration. The assertion now verifies the retained anchor appears exactly once.

The reviewed Marvisak memory implementation uses per-list dirty bitmaps and post-completion filtering. Its contracts differ from this baseline's global snapshots and optional relay. A faithful integration must maintain per-submission bitmap ownership, completion fences, alias-safe byte-level merges, and conservative fallback for uninstrumented root or descriptor writes. Until then, no declared write is discarded based on a dirty mask.

No performance or rendering outcome is claimed. The candidate is compiled in CI before hardware benchmarking.
