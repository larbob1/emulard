# AGENTS.md — Emulard multi-agent agreement

Mission: sustained, correctly rendered 30 FPS. Current owner-reported Proton gameplay: 2–3 FPS, not a formal benchmark. Correctness before speed.

## Replacement chats
Use the [universal restart prompts](coordination/START-HERE.md) for the main AI1–AI6 team and occasional independent AI0. They recover current GitHub state rather than relying on a fixed initial task. Only the prompt matching your role applies; the other prompts describe their workstream boundaries. Older coordination entries are historical; follow the latest applicable decisions and owner approval.

## Start every session
1. Read all files in [coordination/](https://github.com/larbob1/emulard/tree/coordination/coordination), the [roadmap](https://github.com/larbob1/emulard/blob/main/docs/ROADMAP-30FPS.md), and [deferred register](https://github.com/larbob1/emulard/blob/dev/performance-phase6/docs/performance-deferred.md). Fetch current refs and check open PRs and CI. Do not trust stale chat history.
2. Claim one task in your workstream issue before editing: role, P-ID, base SHA, branch, intended files AND prepared upstream symbols, dependencies, tests. If an overlapping claim exists, request coordinator agreement or select another task. Use a separate checkout/worktree and prepared runtime directory.
3. Work only on your assigned branch or a uniquely named child. Verify branch head before writes; normal fast-forward or compare-and-swap pushes only. No force pushes, branch deletion, shared rebases, unilateral merges, or canceling other agents' CI.

| Role | Branch | Issue |
| --- | --- | --- |
| AI 0 Independent occasional contributor | dev/performance-phase6-ai0-<topic> (isolated proposal branches) | [#55](https://github.com/larbob1/emulard/issues/55) |
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


Owner clarification (D23): AI4 is the only agent permitted access to the owner's computer, local files, local shell, local runtime and game installation. AI0/AI1/AI2/AI3/AI5/AI6 are GitHub-only with respect to the owner's machine; they may use their own isolated execution environments and authorized repository CI for title-free synthetic work, never remote-control, mount, inspect, or run commands on the owner's computer, directly or through another agent. Request sanitized evidence through #27; AI4 independently performs only currently authorized local tasks. No new local test authorization.


## D25 — Independent occasional contributor (AI0)

AI0 is not a seventh concurrent team member. The main team remains AI1–AI6 with its existing responsibilities. AI0 works independently across subsystems, without permanently owning any P-ID, only in irregular owner-started sessions outside the main team's active editing/testing window. Check GitHub claims and ask for an explicit owner/AI1-confirmed non-overlapping window if uncertain; stale issue activity is not evidence of inactivity. Existing CI can finish without cancellation. If the main team resumes, checkpoint and stop AI0 edits/tests; read-only review of non-conflicting material may continue. The owner/AI1 coordinates the transition; AI0 cannot pause other agents unilaterally.

AI0 has no access to the owner's computer, local shell, game installation, private files or credentials, directly or indirectly. Use GitHub and isolated environments/authorized repository CI with lawful title-free synthetic inputs only. AI4 remains the sole local executor. No new local test permission or access-control changes.

AI0 may independently investigate, implement, document and test a cross-subsystem contribution on a unique `dev/performance-phase6-ai0-<topic>` branch. Start from a verified current appropriate base; `dev/performance-phase6-ai0` is a starter reference, not integration or a permanent base. Claim exact scope and prepared upstream symbols in [#55](https://github.com/larbob1/emulard/issues/55); avoid unresolved competing claims, preserve default-off experiments and all correctness/ownership/guard contracts. Request shared builder/CI, canonical documentation or reporting-schema changes through the responsible owner; AI0 can propose diffs but cannot alter shared branches, frozen candidates, upstream, integration, main, or other agents' branches. Do not force-push, cancel others' CI or self-merge.

Every AI0 contribution, including tests/docs/fixes, needs AI1's independent exact-head review **before inclusion**. Open a draft PR against current integration and hand off base/head/upstream SHAs, actual diff, prepared anchors, flags, tests/counts, CI links, blockers and unresolved assumptions. AI1 reviews correctness, compatibility, conflicts and integration, consults affected owners/AI3 as needed, and explicitly records approve/request changes/hold/reject plus whether AI4 validation is required and why. If required, AI4 tests the exact reviewed candidate under existing owner authorization and supplies sanitized evidence; failed/missing required validation blocks inclusion. No self-approval, bypass of tests, automatic inclusion, or claim that a green synthetic check substitutes for native/local evidence. A changed head, material integration change, or stale evidence requires re-review and applicable revalidation. Owner alone approves merges/releases. AI1 integrates only reviewed exact content in isolated candidates until authorized; formal performance acceptance remains AI3's remit.

The inbox [#55](https://github.com/larbob1/emulard/issues/55) and [recovery prompt](https://github.com/larbob1/emulard/blob/coordination/coordination/ONBOARD-INDEPENDENT.md) are durable across irregular sessions. AI0 posts start/end/checkpoint, exact proposed contribution and review state; AI1 maintains canonical decisions and records. D22–D24, frozen snapshots and unresolved P01–P24 are unchanged. This agreement is procedural; it does not grant, revoke or enforce GitHub account permissions.
