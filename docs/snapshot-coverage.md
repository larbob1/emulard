# Snapshot coverage and retirement

The runtime snapshots bytes before GPU execution so that completed writes can be merged with concurrent CPU changes. The previous coverage algorithm repeatedly split a temporary vector for every pending declaration. This candidate clips existing declarations to the requested interval, discards empty overlaps, exits early for a fully covered interval, then computes the uncovered pieces with the existing sorted interval subtraction helper. Pending declaration and completion ownership are unchanged.

When retiring a large batch of exact declarations, the membership test now uses a temporary hash set; smaller batches retain the existing linear membership test. Pending range order and relay flight counts are preserved. Overlapping but unequal declarations are never retired by this optimization.

Two targeted Rust tests compare the interval result against a bytewise reference over exhaustive combinations of a small fixture and check both completion membership paths. All three new source anchors were verified against the pinned source, including the existing memory-budget edits. These are CPU bookkeeping optimizations, not a GPU dirty-page filter. Actual time and memory savings have not been measured.

The last fully validated runtime revision is 773fd22. More recent synthetic checks passed at 7be73e4; runtime compilation remained in progress when this revision was prepared. The complete comparison and merge fallback remains enabled. A safe dirty-page filter still needs comprehensive write coverage, stable resource mapping, and valid completion-scoped feedback. No hardware or Linux execution has been attempted.
