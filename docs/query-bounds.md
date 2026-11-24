# Query-result bounds candidate

The reviewed runtime resolves graphics queries into a caller-supplied buffer. Its old range guard used unchecked addition, which could panic in a checked build or wrap in an optimized build before pointer arithmetic. The candidate checks the result span with checked multiplication and addition before any write. Existing query result sizes and fallback values remain unchanged.

The patcher validates the exact reviewed source blob and both unique source anchors before editing. The synthetic Rust tests cover exact boundaries, zero count, overflow and statistics stride. Python tests cover the patcher's revision guard, edit and line endings.

This is a defensive correctness improvement; there is no evidence this condition caused a particular runtime failure. GPU occlusion and timestamp results are still approximations, and hardware queries are not implemented by this patch. No title data is needed for these tests.

Run the source preparation tool from the repository root; it now applies the query candidate along with the memory scheduler. The Windows build option runs both targeted Rust suites before compiling the runtime. Windows compilation and runtime validation remain pending.
