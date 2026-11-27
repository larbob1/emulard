# Conflicts and dependencies

No active claim from AI 2 or AI 3 at setup. Known overlap:
- Memory vs graphics: texture.rs, watch.rs, inplace.rs, resource.rs, queue.rs, shadow.rs memory invalidation and fence ownership. No unilateral changes in overlapping functions.
- Graphics vs reliability: P18 descriptor caching belongs to graphics implementation; reliability measures and tunes.
- All: shared builder, CI, deferred register and patch order owned by coordinator; reports owned by reliability. Send proposed anchors/schema in issue comments.
- Long native CI runs: do not cancel another agent's active jobs. Coordinator schedules integration checks.
Post conflict in your issue with P-ID, paths/symbols, competing claim, proposed resolution. Pause only the contested portion. Coordinator records decisions here.

### Active cross-workstream dependencies
- P12/P13/P14: AI2 #24 test-only model may proceed. Production host.rs Flight/relay_worker/relay_land/relay_hand_back, Shadow copy_back_done, read_backs/card_done, watch/inplace/queue/texture/resource/xmem shared paths restricted until writer coverage, native lease, fence domain, partial error/retirement and lock-order contracts reviewed. See D08/#12. Memory generation publication cannot substitute for pending-write synchronization.
- P03 CPU trace: AI3 needs AI2 agreement for queue wrappers and coordinator approval of prepared hunks/build registration. AI1 retains memory remap instrumentation; AI2 GPU submission/fence instrumentation. See D09/#13.
- #18 and #22 frozen exact snapshots; #23 separate follow-up. No branch merges authorized. #23 and #25 native succeeded; #26 and #29 native active in separate CI groups. #29 is an isolated child of #18, not a merge or replacement.

- AI4 #27 collects local evidence; AI3 retains reporting schema/acceptance authority. No production changes by AI4 without a new coordinator claim. Read-only title protection mandatory; no raw logs or private paths in GitHub.

- P11 #32 review-only guard proposal: AI1 retains mapping lock contract; AI2 reviews actual staging upload/refresh/submission/fence ownership. No production application before agreement and native race validation. Existing short-lock flag remains off for #18 control.

- P03 #33 native-only registration isolated; AI3 reporting ownership unchanged. P15/P17/P22 offline memory/pipeline triage coordinated with AI4; no production budget or staging changes without ownership/retirement proof. Dirty observation logging outside presenter guard requires review.

### D23 six-agent dependencies
- AI5 #45 storage scheduler/worker/buffer implementation vs AI1 xmem, storage write_physical, physical backing and alias lifetime: coordinate exact prepared symbols and ownership; AI2 retains GPU staging/fence/texture ownership. AI5 does not change AI3 reports or AI4 local harness.
- AI6 #46 CPU/HLE thread/wait/timer implementation vs AI1 memory locks, AI2 graphics worker/pipeline scheduler, AI5 storage workers: read-only audit first; request agreement for shared symbols, no new system settings or scheduling policy by default. AI3 owns trace schema and analysis; AI1 owns shared build/CI. No executable/translation/access-control modifications.
- All six agents claim before edits, post milestones, pause overlapping scope, use separate branches/checkouts and preserve frozen candidates. D22 launch restrictions continue. The project owner alone authorizes merge; AI4 alone executes approved local tests.


Owner clarification (D23): AI4 is the only agent permitted access to the owner's computer, local files, local shell, local runtime and game installation. AI0/AI1/AI2/AI3/AI5/AI6 are GitHub-only with respect to the owner's machine; they may use their own isolated execution environments and authorized repository CI for title-free synthetic work, never remote-control, mount, inspect, or run commands on the owner's computer, directly or through another agent. Request sanitized evidence through #27; AI4 independently performs only currently authorized local tasks. No new local test authorization.

### D25 independent contributor conflicts
AI0 works outside the main six's active edit/test window; confirm exclusivity rather than inferring from silence. Existing CI may complete, never cancel it. Check #55 and main six claims when switching; if uncertain or contested, pause edits/tests and ask AI1 or owner for resolution. AI0 may propose across domains but has no permanent ownership or authority over other agents, shared CI/reporting, frozen candidates or integration. Every exact contribution requires AI1 review and recorded local-test disposition; AI4 alone performs required authorized local validation. Changed head/material integration invalidates stale approval.


### D26 — Owner-authorized regular team resumption
Owner explicitly states AI0 is paused and AI2–AI6 are now active. [AI1 transition claim #11 7229822627](https://github.com/larbob1/emulard/issues/11#issuecomment-7229822627). AI1–AI6 are the active regular team; AI0 remains paused under D25, no new independent edits/tests. This supersedes prior specialist pause statements only. Historical snapshots remain historical. No change to D20–D25 launch restrictions, owner-machine access boundary, ownership/claim rules, guarded defaults, frozen builds, or owner-only merge authorization. AI4 resumes review/preflight design within existing scope; no new title launch, system change or repeated pressure-stop run authorized by this transition.
Integration at transition 4253e23ba524079342a85c6919f71ab9515d11df; upstream 51700c6d43a3507fa65e50fe4bb64074ce706cd4. #99 exact b25ba1e40c65a6d8c80122c419820a3538a62ce0 passed native debug/release 2/2 and synthetic 113+4 (portable skipped); independent primitive scope only. See #11 7229806029 and PRE-GAMEPLAY-PHASE1.md. Phase1 open; #71 HOLD, all24 P-IDs unresolved.
- AI1 #11: owns actual Host::submit synchronous fence/publication test design and shared CI/registration; coordinate host.rs overlap with AI2 before either edits it. Review exact storage scratch registration request; preserve independent native candidates. Reconcile AI3 advisory concurrence separately; no automatic inclusion.
- AI2 #12: continue #82/#64/#65 exact caller/ownership review and #80/#32 partial detile publication fixture planning on assigned graphics branch; review #71/#99 actual queue/copyback failure contract with AI1. Keep host.rs submit implementation with AI1 pending symbol agreement. Then descriptor/vertex actual caller gates. No shared edits unilaterally.
- AI3 #13: own evidence and acceptance, verify actual submit/handback and visibility test protocol with AI1/AI2; formalize independent #99 scope and advisory concurrence #13 7229804805; D24 timing design only. No synthetic FPS extrapolation.
- AI4 #27: review exact #96/#98/#99 evidence, candidate compatibility and safe local readiness/attribution plan; no fresh local title run, installation or system change. Confirm exact candidate, read-only isolation, guard/headroom, visible rendering/input and stop conditions before separate launch disposition.
- AI5 #45: continue P23/P18 exact #48 scratch candidate and #21 page lookup review; propose standalone scratch-only composition from pristine prepared source with exact two ignored filters and independent baseline/build receipts. AI1 owns CI registration, AI3 acceptance. No production scratch/early-drop policy or selector timing authorization by this transition.
- AI6 #46: continue P18/P24 exact #81 actual wait-route/cleanup fixture design, disabled/whole/split/cut paths, ownership and lock contention; coordinate list/queue/host symbols with AI2/AI1 before changes. Preserve waits, guards and system policy; no production cleanup inclusion.
Each specialist must recover live issue/ref/CI state and claim exact task/base/paths/symbols before edits or new tests. Existing CI may finish without cancellation. Report handoffs in assigned issues; AI1 owns canonical records. This is a team transition, not a release or performance milestone.
