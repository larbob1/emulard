# Read-only upstream integration

## Baseline (used directly through source preparation)

Victory Fork: revision 2119b0e44c53aa9648307b0c5c73590290305b1f. Retains existing loader, host graphics layer, input, audio, shader lowering and cache. Local patches are applied to a separate checkout. No entire external repository is copied into this repository.

## Marvisak reference

VIctory: revision 70564ae08c82d43df5fad97b08d34628b07b1d9d.

Review the synthetic memory cases in crates/victory-shader/src/emit/memory_tests.rs. These exercise raw-address reads and writes, address carry, descriptor-relative access and missing mappings. They are valuable external comparison tests; the fork has a different directory representation and their harness is not a drop-in port. Keep the original test source in its licensed checkout. The independent page-boundary model in this repository covers related cases but does not replace real GPU execution.

The upstream range-analysis implementation (crates/victory-shader/src/range.rs) is a candidate for later integration, because proving smaller register ranges can reduce translator workload. It has not been ported.

## Independent reference

Five Star Recomp: revision aebe007b821687ece66d6dd3c636c7a9a1bb9b.

The memory-aware compilation design in src/FiveStar.Loader/Shims/D3D12X/Pipelines/CompileBudget.cs motivates the conservative startup compiler cap added here. Our original Rust implementation checks available physical memory and commit at worker startup and caps concurrency at one below 4 GiB headroom, two below 8 GiB, or the existing default otherwise. The manual worker setting may reduce that cap further. This is not the full dynamic reservation system from the reference and does not guarantee avoidance of out-of-memory failures.

The independent project's C# graphics and shader components use different host contracts; no binary or source transplant has been attempted. Its separate compiler, memory-residency and fence behavior need targeted synthetic comparisons before a port.

All three upstream projects declare GPL-3.0-or-later for their main code. Preserve their attribution and any component-specific notices. No proprietary data, identifiers, or runtime dumps are included.
