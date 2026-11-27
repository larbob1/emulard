# Shader fingerprint presence review (P17/P22)

Review only; no production patch or native registration.

Pinned upstream: 51700c6d43a3507fa65e50fe4bb64074ce706cd4.
- `crates/victory-shader/src/emit/mod.rs`, blob
  `282d7c0757c70b2a71c58bd989191962314d55e1`, lines 212–219:
  each switch is encoded as name, equals, optional value bytes, NUL.
  An absent switch and a present empty switch have identical encoding.
- `crates/victory-shader/src/emit/lower.rs`, blob
  `6e7aa710b1ae931ae72696add85a96bfcc3077a3`, lines 4270 and 10930:
  VICTORY_MESH_OUTPUT_STRICT and VICTORY_STRICT_JOINS use presence,
  not value equality. The latter uses OnceLock.
- Consequently a cache hit from a non-strict translation may bypass
  strict translation when a strict switch is present but empty.
  No actual cache failure or affected shader has been reproduced.

## Standalone fixture

`tools/test_shader_fingerprint_presence.py` compiles the original
switch-loop encoding and a proposed alternative in a disposable Rust
binary. It launches fresh child processes with only the two synthetic
switch values overridden, distinguishing absent, empty, 0, 1 and
separator-like values. It does not mutate the test process environment,
load a driver, translate shaders, or read/write a shader cache.
The exact original encoding loop is adapted to a supplied name list,
rather than the generated full translator switch list.

Proposed alternative: length-prefix each name, a presence byte, and
for a present value a fixed-width little-endian length and its encoded
bytes. This preserves the difference between absent and present-empty.
The 36-case cross product is a finite regression set, not a proof
of platform-independent environment encoding or complete cache identity.
Encoded OsStr bytes are platform-specific, as in the existing design.

## Before a production candidate

Require AI1/AI3 review of the proposed framing and exact prepared
translator, separate from the #59 memo native parity gate. A source
change deliberately changes the translator fingerprint namespace;
rerun actual cache equivalence and publication failure fixtures.
Confirm absent/empty/nonempty handling in fresh native processes;
exercise real strict-join and mesh-output behavior with synthetic
shaders, and ensure old keys are not accepted as corrected keys.
Retain release and diagnostics build coverage, default strict semantics,
and no live environment mutation. OnceLock effective settings versus
fresh environment reads require a separate immutable-process-settings
contract review. No title launch, performance claim or merge authorization.
