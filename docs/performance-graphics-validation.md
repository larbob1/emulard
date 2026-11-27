# Graphics native validation snapshot

Isolated coordinator test branch, not a merge. Cumulative base 09ba89ba24d0fa195150c74112f904b109550395.
Graphics PR #14 snapshot 81a2d3543925e4ce07c0146d8c045bc2b04263b3; independent stream bounds PR #17 snapshot 5e4aabecf06bb466512685bbc8cc0e9ba4e93056.
Includes cache publication/recovery, stage identity, full linked digest, linked single-flight, monotonic wait accounting, early queue pruning, near-size staging reuse, and stream bounds. Registers nine additional native test filters and both build profiles. Default-off switches retain their defaults. Pure helper tests do not establish D3D12 fence-safe lifecycle or real gameplay improvement.

The frozen combined playtest PR #18 is unchanged. Newer graphics commits are not included. No measured gain, no owner merge approval.
## Isolated P21 follow-up

Child of b183b12850b8bea85e25db2ddc0d6e8f3d0fff46. Stages only the exact two-file copy-back fixture delta of #14 b8a02e71e2d0868e1b4e390af28514f919d02a69. Native validation adds four fresh process invocations of copy_back_mask_tests (five cases each expected; runtime feature detection remains authoritative), covering both individual and combined sparse/AVX2 modes. No production fence or copy-back behavior change intended. Synthetic full pinned preparation and both Windows profiles required; results pending. Original #22 and frozen #18 stay unchanged.
