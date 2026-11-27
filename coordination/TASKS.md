# Task ownership

Canonical acceptance: [deferred register](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/performance-deferred.md). This matrix allocates work, not completion. All 24 remain unresolved.

| ID | Owner | Scope |
| --- | --- | --- |
| P01 | Reliability | Native/Proton validation |
| P02 | Reliability | Matched gameplay benchmarks |
| P03 | Reliability | Critical-path telemetry |
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
| P18 | Reliability | System/PGO tuning; graphics implements descriptor caching by agreement |
| P19 | Reliability | Integration review; coordinator integrates |
| P20 | Reliability | Actual FPS acceptance |
| P21 | Graphics | Copy-back validation |
| P22 | Graphics | Cache failure and fairness |
| P23 | Reliability | Storage worker measurements |
| P24 | Reliability | CI triage; coordinator approves shared edits |

First claims: Memory #11 continues PR #10 pinned backing reads and CPU-access audit, with PR #9 separate. Graphics #12 starts P22 cache failure/retry (confirm zero-size issue before fixing), then P16. Reliability #13 starts P02/P03 numeric benchmark and test improvements and CI review, then P23. P13/P14 production ownership changes depend on memory/fence contracts. P16 and P22 can proceed independently. P18 shared work requires agreement.

AI 4 (#27) executes local P01/P02/P03/P20/P23 evidence collection in coordination with AI3; existing P-ID owners, acceptance criteria and all 24 unresolved statuses unchanged. AI4 owns local harness operation and visual verification, not reporting schemas or production patches.
