# Conflicts and dependencies

No active claim from AI 2 or AI 3 at setup. Known overlap:
- Memory vs graphics: texture.rs, watch.rs, inplace.rs, resource.rs, queue.rs, shadow.rs memory invalidation and fence ownership. No unilateral changes in overlapping functions.
- Graphics vs reliability: P18 descriptor caching belongs to graphics implementation; reliability measures and tunes.
- All: shared builder, CI, deferred register and patch order owned by coordinator; reports owned by reliability. Send proposed anchors/schema in issue comments.
- Long native CI runs: do not cancel another agent's active jobs. Coordinator schedules integration checks.
Post conflict in your issue with P-ID, paths/symbols, competing claim, proposed resolution. Pause only the contested portion. Coordinator records decisions here.
