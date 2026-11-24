# Completion-scoped dirty-page policy

The read-only Marvisak/VIctory implementation uses per-list bitmaps and completion callbacks. This revision adds a standalone reference model for submission identity, page marks, completion, missing-page dependencies, conservative untracked ranges and byte-level merging. It does not bind a bitmap to the runtime or change production writeback decisions. The policy cannot infer that a write is independent of a missed read; independence must be proven. Untracked ranges retain the existing comparison path. If dependency is unknown, instrumented results must be withheld in the model after a miss.

In the 100-page synthetic workload, two marked pages reduce the model's candidate comparison span to two pages (128 KiB of 6.25 MiB). This is not measured GPU performance or actual runtime bandwidth. Real integration requires per-flight storage and immutable directory ownership, instrumentation for raw stores and atomics, completion ordering, and preservation of untracked descriptor and root writes. Do not discard live writes based on the model.

The scalar-base shader fixture failed the preceding CI test because it used a constant address, which the existing tracker rejects; the stage log identifies the failing test but does not expose its full panic. The revised fixture supplies the address through dynamic root constants and keeps the store live. It must pass CI before being considered verified.

A separate production patch fixes the joined CPU-copy branch that returned before invalidating refresh state. This avoids retaining stale raw-address copy scheduling across a joined write. Existing builder safety and quarantine behavior remain unchanged. No new shader coverage or gameplay is claimed.
