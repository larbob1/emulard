# Lighting bring-up: raw-address page boundaries

The upstream renderer translates compute shaders that build and traverse bounding-volume hierarchies (BVHs). Its existing ray-node intersection implementation already resolves the two 64-byte halves separately. However, generic raw-address vector loads and stores resolve only the starting page for up to four dwords. Scalar vector loads have the same limitation within each four-word chunk.

If a 4-byte-aligned vector crosses a 64 KiB page boundary and the two directory entries refer to different host views, the trailing words can be read from or written to the wrong view, or be lost. The experiment resolves each dword separately in the global vector load, global vector store and scalar memory load paths. It preserves the existing guarded store semantics and address carry arithmetic. It does not alter the ray-node intersection algorithm.

## Prepare an isolated candidate

```sh
python tools/build_runtime.py ../runtime-lighting --lighting-memory
```

Add --build on a supported Windows build host. Keep the normal build as a control. The reviewed shader cache includes a fingerprint of the executable, so separately compiled executables have distinct translation keys.

## Tests and limitations

The Python reference model covers different page views, missing pages, 32-bit address carry, and contiguous views. Source patcher tests cover revision and anchor checks. These are not GPU execution tests. The source edits have been verified against the pinned blob but require Rust compilation, DXIL validation, and a hardware test.

This change may be considerably slower because every word needs a directory lookup and fault reporting. It is deliberately optional. It assumes naturally aligned dwords and does not solve individual unaligned dwords crossing a page. It does not recover a write to an unmapped page or correct stale mappings. It has not been shown to fix a particular lighting defect.

Remaining lighting blockers include unsupported or rejected 64-lane builder programs, the uncompiled shadow-mask programs, memory residency and synchronization, and end-to-end GPU validation. Do not force unsupported wave behavior or disable the existing builder safety rule. Test synthetic shaders first; compare candidate and baseline in a controlled local run only when available.

No assets, logs or personal configuration belong in the repository.
