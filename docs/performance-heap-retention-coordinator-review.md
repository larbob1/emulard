# Coordinator heap-retention review gate

Exact #35 f184da6e proposal versus frozen #18 dbac4c6 fully prepared source. Dedicated workflow verifies four anchors, two changed-file headers, unchanged tracked diff/status. Preview only; no application, compilation, GPU fixture or runtime authorization.

B003 late snapshot: 658 windows/3000 MiB, all extra Arc holders; 648/2960 MiB descriptor COM holders, 1199 MiB ever copied, union 2276 MiB, nominal-minus-union 724 MiB (rounded). Only 4/16 MiB unsized asks. Overlapping populations, no RSS ownership or reclaimable-byte estimate. Age alone cannot make sampled windows eligible. Existing sweep and retirement gates must remain.

Pinned draw::heap_buffers returns early per list ONCE and process-wide FRAME; it may not record Step::Refresh on each list. State::bind retains ID3D12DescriptorHeap COM, not proof of independent HostHeap metadata or Shadow/slot-resource ownership. Moving RANGES to per-heap mutex changes global serialization; global WHOLE throttle remains. Dead owner cleanup cannot be authorized from portable Arc tests. Need fixture for recorded but not submitted list, skipped refresh, descriptor replacement, heap destruction, pointer reuse, inflight replay, completion and retirement; fail closed when ownership unknown. Consider separating stable owner identity from cache cleanup, preserving serialization first. memory::Memory::copies and numbered directory/heap slots retain run-lifetime references and require independent generation/fence proof; not established as B003 contributor. Never reuse directory slots or release live resources without proof.

AI2 retains descriptor scope and AI3 overlap review. No budget/age/grid changes or local runs. No FPS claim.
