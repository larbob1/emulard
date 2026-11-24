# Idle upload memory budget

The reviewed runtime keeps up to 128 MiB of unused scratch upload chunks in a shared pool. This candidate exposes EMULARD_SCRATCH_IDLE_MB, clamped to 0–128 MiB. The default remains unchanged. A smaller value returns idle chunks instead of keeping them for reuse, without affecting the lifetime of chunks still held by command lists. This may increase allocation overhead.

The cap applies only to idle scratch upload memory, not overall RAM, GPU memory, or active allocations. A value of 32 permits up to 96 MiB less idle retention than the original cap; actual savings depend on pool occupancy. This alone cannot solve multi-gigabyte memory pressure. The existing upload pool must remain enabled for the cap to be relevant. An overflow-safe pool admission check and three Rust regression tests are included.

The build script applies this candidate along with the memory scheduling changes. CI compiles and tests the new code when the pinned toolchain and dependencies are available. Four Python patcher tests are supplied. No hardware performance or memory usage has been measured.

Use a separate runtime build and compare defaults with a reduced idle cap during local synthetic tests. Do not force experimental GPU synchronization, drop active resources, or assume a smaller cap improves frame rate. Keep all local reports private.
