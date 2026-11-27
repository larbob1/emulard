# Wave translation candidate

On a 32-lane host, the reviewed translator attempts several transformations before approximate per-half wave execution. This patch adds constant-edge threading as another candidate in the exact retry sequence. The same transformation is already used in the translator's final unsupported-instruction fallback. The new placement also allows it to be tried for programs that emitted code but still require a 64-lane host wave.

The patch fixes a retry-policy inconsistency: the later lane-mask fallback must honor the explicit opt-in for wave-wide branches when translating wave64 programs. The existing wave32 default remains unchanged. It also adds the local-wave policy to the shader cache fingerprint so an approximate cached translation is not silently reused for a strict-policy run.

The source preparation script applies the candidate automatically. For controlled correctness investigations, use the existing strict local-wave policy (VICTORY_WAVE_LOCAL=idiom) and leave wave-wide experimental branches off. Keep separate baseline and candidate builds. Do not bypass the builder safety checks.

Two Rust policy tests and four Python patcher tests are supplied. No claim is made that a previously rejected builder shader now translates: the new retry needs compilation, shader validation and execution on a 32-lane device. The candidate does not supply a universal exact emulation of divergent wave64 control flow.

Synthetic CI verifies the Python tests and probes, not the full external runtime. The previous synthetic workflow passed. Build and test the runtime on a supported Windows build host before considering a GPU run.
