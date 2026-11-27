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
