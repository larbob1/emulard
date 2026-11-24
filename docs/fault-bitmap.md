# Lighting and world rendering: fault discovery

The existing raw GPU address path records missing pages in a small hashed table. Different pages can collide, and a later report can overwrite an earlier one. The experimental replacement assigns each directory page one bit, using a GPU atomic OR to combine reports. The 128 GiB directory now needs a 256 KiB fault buffer instead of 16 KiB. The host scans set bits and prepares the corresponding page copies for subsequent frames.

The candidate is included only in the optional lighting-memory build. It composes after the earlier memory scheduler and per-dword boundary patches and checks the original blobs and exact predecessor contents. Two Rust decoding tests and four Python tests are supplied.

This fixes hash collisions, not the entire fault recovery system. Reads and writes issued before a page is mapped are still lost. The host clear can still race a GPU report, as in the original path. A proper fence-scoped feedback design and valid allocation extents are still needed. Atomic operations, including zero-mask operations for mapped accesses, may significantly increase GPU cost; this is not a performance optimization. The extra buffer allocation is 240 KiB. The candidate requires compilation, shader validation, and GPU tests.

The existing acceleration-structure builder safety gate remains enabled. No unsupported shader is marked successful and no rendering result is claimed.
