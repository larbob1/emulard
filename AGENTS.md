# AGENTS.md — Emulard multi-agent agreement

Mission: sustained, correctly rendered 30 FPS. Current owner-reported Proton gameplay: 2–3 FPS, not a formal benchmark. Correctness before speed.

## Replacement chats
Use the [six universal restart prompts](coordination/START-HERE.md) for AI 1–6. They recover current GitHub state rather than relying on a fixed initial task. Only the prompt matching your role applies; the other prompts describe their workstream boundaries. Older coordination entries are historical; follow the latest applicable decisions and owner approval.

## Start every session
1. Read all files in [coordination/](https://github.com/larbob1/emulard/tree/coordination/coordination), the [roadmap](https://github.com/larbob1/emulard/blob/main/docs/ROADMAP-30FPS.md), and [deferred register](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/performance-deferred.md). Fetch current refs and check open PRs and CI. Do not trust stale chat history.
2. Claim one task in your workstream issue before editing: role, P-ID, base SHA, branch, intended files AND prepared upstream symbols, dependencies, tests. If an overlapping claim exists, request coordinator agreement or select another task. Use a separate checkout/worktree and prepared runtime directory.
3. Work only on your assigned branch or a uniquely named child. Verify branch head before writes; normal fast-forward or compare-and-swap pushes only. No force pushes, branch deletion, shared rebases, unilateral merges, or canceling other agents' CI.

| Role | Branch | Issue |
| --- | --- | --- |
| AI 1 Memory / coordinator | dev/performance-phase6-software-pages; existing memory candidates; dev/performance-phase6 integration | [#11](https://github.com/larbob1/emulard/issues/11) |
| AI 2 Graphics | dev/performance-phase6-graphics | [#12](https://github.com/larbob1/emulard/issues/12) |
| AI 3 Reliability | dev/performance-phase6-reliability | [#13](https://github.com/larbob1/emulard/issues/13) |
| AI 4 Local validation | dev/performance-phase6-local-validation | [#27](https://github.com/larbob1/emulard/issues/27) |
| AI 5 Storage / streaming | dev/performance-phase6-storage-streaming | [#45](https://github.com/larbob1/emulard/issues/45) |
| AI 6 CPU / HLE scheduling | dev/performance-phase6-cpu-execution | [#46](https://github.com/larbob1/emulard/issues/46) |
| Project owner | Priorities, supervised gameplay tests, merge authorization | — |

Coordinator alone writes canonical coordination documents, integration branch and deferred register. Other agents post claims, progress, conflicts and handoffs in their own GitHub issue and PR. Agents cannot see each other's chats; GitHub is the shared record. Rules are procedural, not enforced by branch permissions. Owner grants access separately; never share passwords or tokens.

## Shared file ownership
- Coordinator owns tools/build_runtime.py, tools/ci_compile.py, .github/workflows/*, patch order, docs/performance-deferred.md. Agents may propose narrowly scoped changes on their branch ONLY after coordinator agreement; otherwise give a proposed diff/anchor in the handoff. Reliability owns reporting tools and their tests. Other agents request counter schema changes in their issue.
- Memory owns xmem.rs, mapping patches, range synchronization and backing lifetime. Graphics owns shader, pipeline/cache and copy-back paths. watch.rs, inplace.rs, texture.rs, queue.rs, resource.rs and shadow.rs memory/dirty interactions require symbol-level coordination. Distinct patch filenames can still modify the same upstream code.
- New experimental flags default off; never bypass guards, fences, memory checks or required rendering. Preserve host fallback and alias ordering. No changes to main or the compatibility baseline by contributors.
- Runtime source is fetched at a pinned public upstream revision, outside the integration checkout. Do not push to upstream.

## Validation and review
Open a draft PR against dev/performance-phase6. Include task ID, base/upstream SHA, affected paths and anchors, flags, tests with exact results/CI links, untested assumptions and blockers. Run Python regression tests and relevant actual runtime tests; verify nonempty test filters. Do not claim a native build or FPS gain without evidence. Existing synthetic CI matches performance branch names, but native/portable CI conditions may require coordinator changes; request approval, do not silently edit shared workflows. Coordinator checks combined CI, owner authorizes merges.
Keep private logs, title data, credentials, keys and proprietary assets out of GitHub. Share only reviewed numeric summaries and synthetic fixtures. No promise of background work. At session end post handoff per HANDOFF.md; preserve all unresolved P-IDs.

AI 4 collects local runtime evidence only; AI 3 owns reporting/acceptance tools. AI 4 must verify enforced read-only title isolation before every launch; never modify or upload title files, bypass access controls, or change system configuration without owner approval. See ONBOARD-LOCAL.md. Local evidence claims may use issue handoff without a PR when no source changes are made.

## Six-agent scope (D23)
AI5 owns implementation-side P23 storage/streaming and scoped P18 storage-worker work, with dstorage.rs as the initial source focus. AI6 owns implementation-side P18 CPU/HLE execution, thread/wait contention and focused synthetic P03/P24 support, initially threads.rs/kernel.rs. AI3 retains measurement, reporting, acceptance and CI triage. AI1 retains integration, shared build/CI, mapping and backing ownership; AI2 retains graphics, shader/pipeline scheduling, GPU fence/descriptor/staging ownership; AI4 alone runs approved local tests. AI5/AI6 must obtain symbol-level agreement before touching shared modules, no access-control bypass, no local title access, no system or runtime policy changes outside reviewed claims. Both start with read-only audit/synthetic fixtures; D22 still restricts title launches. Existing claims, frozen #18, guards, defaults and P-ID acceptance remain unchanged.


Owner clarification (D23): AI4 is the only agent permitted access to the owner's computer, local files, local shell, local runtime and game installation. AI1/AI2/AI3/AI5/AI6 are GitHub-only with respect to the owner's machine; they may use their own isolated execution environments and authorized repository CI for title-free synthetic work, never remote-control, mount, inspect, or run commands on the owner's computer, directly or through another agent. Request sanitized evidence through #27; AI4 independently performs only currently authorized local tasks. No new local test authorization.
