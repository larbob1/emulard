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
