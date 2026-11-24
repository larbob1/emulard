# Cross-project GPU memory review

Reviewed public sources without writing to any upstream repository.

- Marvisak/VIctory: crates/victory-shader/src/emit/lower.rs supports a scalar base with a lane-specific unsigned offset in global memory operations. Its resource tracker recognizes the same operand form as our pinned baseline.
- The baseline rejects that form on its raw-address path. The new candidate emits the low-word addition and explicit carry, then uses the existing signed-displacement helper. It is enabled in both baseline and lighting builds. No broader resource-classification changes are made.
- A synthetic Rust lowering case and four Python tests cover the new path and address arithmetic. The Python reference is not an execution test of the generated shader.
- Marvisak/VIctory's crates/victory-gpu/src/memory.rs uses a per-list dirty bitmap, submission-scoped layout and delayed writeback, including suppression of raw-page writeback after missing-page accesses. The fork uses a flat append-only directory and range snapshots. Porting the bitmap alone would be incorrect: descriptor lifetime, completion fences, copy-back ownership and fault behavior must migrate together.
- Five Star Recomp's src/FiveStar.Shaders/Translation/AddressMap.cs is a separate two-level mapping implementation. Its sparse regions and paired read/write descriptors are useful design references, not directly interchangeable structures.

The scalar-base change expands support for an explicitly rejected address form; no particular previously failing program has been demonstrated to work. The new dirty-page system is not implemented yet. The runtime and shader validation workflows must confirm the candidate. No external binaries, proprietary data, or raw logs are added.
