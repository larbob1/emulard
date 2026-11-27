# P23/P24 isolated early-drop native parity

Base: 7b5dfdcdad04b54f5633a0d016a723d5fcc8c2f0 (#52, native passing). Imported exact AI5 preview 8ba8adaad7d7c1ba28e8836b6ef80cb477004846, blob 8f1c7ca1ef1d4f6e600acc79070ba47ce556760b. Pinned upstream 51700c6d43a3507fa65e50fe4bb64074ce706cd4.

Before any insertion, verify complete prepared dstorage and execute slice identity. Insert original codec fixture first, then the test-only execute clone and explicit off/on modules. Qualify baseline and both mode filters separately; each ignored invocation requires exactly one passing test. Keep existing codec, mapping, GPU and both build gates. Force LF only for byte-pinned codec fixture. No production scheduling, allocation or lifetime policy change. Native evidence pending; no allocator/RSS/throughput/FPS proof or title execution.
