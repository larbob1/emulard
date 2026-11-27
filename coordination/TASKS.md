# Task ownership

Canonical acceptance: [deferred register](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/performance-deferred.md). This matrix allocates work, not completion. All 24 remain unresolved.

| ID | Owner | Scope |
| --- | --- | --- |
| P01 | Reliability | Native/Proton validation |
| P02 | Reliability | Matched gameplay benchmarks |
| P03 | Reliability; AI6 scoped CPU probe support | Critical-path telemetry; AI3 owns reporting/schema, AI6 proposes CPU/HLE probes by agreement |
| P04 | Memory | Software GPU page tables |
| P05 | Memory | Placeholder intervals / host calls |
| P06 | Memory | Mapping failure recovery |
| P07 | Memory | Changed scatter batching |
| P08 | Memory | Tile replay |
| P09 | Memory | Range locks |
| P10 | Memory | Pinned native backing / retirement |
| P11 | Memory | Texture snapshot synchronization |
| P12 | Memory | Per-range generations |
| P13 | Graphics | Completion-scoped dirty tracking |
| P14 | Graphics | Copy-back and async readback |
| P15 | Graphics | Residency and staging budgets |
| P16 | Graphics | Shader and pipeline correctness |
| P17 | Graphics | Pipeline caches and scheduling |
| P18 | Reliability (measurement); AI6 (CPU implementation); AI5 (storage-worker implementation) | Scoped CPU/HLE scheduling and worker tuning; AI2 implements graphics descriptor/cache work by agreement; AI1 approves shared changes |
| P19 | Reliability | Integration review; coordinator integrates |
| P20 | Reliability | Actual FPS acceptance |
| P21 | Graphics | Copy-back validation |
| P22 | Graphics | Cache failure and fairness |
| P23 | AI5 (implementation); Reliability (measurement) | Storage/streaming worker, queue, buffer and I/O improvements; AI3 owns reporting and AI4 local evidence |
| P24 | Reliability; AI5/AI6 scoped fixture support | CI triage; coordinator approves shared edits and native registration |

First claims: Memory #11 continues PR #10 pinned backing reads and CPU-access audit, with PR #9 separate. Graphics #12 starts P22 cache failure/retry (confirm zero-size issue before fixing), then P16. Reliability #13 starts P02/P03 numeric benchmark and test improvements and CI review, then P23. P13/P14 production ownership changes depend on memory/fence contracts. P16 and P22 can proceed independently. P18 shared work requires agreement.

AI 4 (#27) executes local P01/P02/P03/P20/P23 evidence collection in coordination with AI3; existing P-ID owners, acceptance criteria and all 24 unresolved statuses unchanged. AI4 owns local harness operation and visual verification, not reporting schemas or production patches.

## AI5 and AI6 first claims (D23)
AI5 #45: audit exact prepared DirectStorage scheduler/cap and storage lookup candidate #21, queue admission, worker/read/decompression and temporary buffer lifetimes; propose bounded synthetic evidence before implementation. No mapping/write_physical or GPU publication edits without AI1/AI2 agreement. AI6 #46: audit pinned loader threads.rs and HLE kernel.rs thread/wait/timer paths and existing CPU evidence; propose one focused synthetic fixture for contention or wait correctness. No executable/translation/access-control, system priority/affinity, mapping, graphics or DirectStorage changes without review. Both own separate development branches from 6b19a42d6f0d95fe8ec42ef4a6f056a0ad96414b; all 24 IDs open. AI3 retains reporting/acceptance, AI4 local testing. No new title launch authorization.


Owner clarification (D23): AI4 is the only agent permitted access to the owner's computer, local files, local shell, local runtime and game installation. AI1/AI2/AI3/AI5/AI6 are GitHub-only with respect to the owner's machine; they may use their own isolated execution environments and authorized repository CI for title-free synthetic work, never remote-control, mount, inspect, or run commands on the owner's computer, directly or through another agent. Request sanitized evidence through #27; AI4 independently performs only currently authorized local tasks. No new local test authorization.
