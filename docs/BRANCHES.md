# Branch and integration policy

Main is the documentation-first entry point. The working runtime integration and experiments live on development branches. No code is merged or deleted solely for cleanup.

## Branch inventory

| Branch | Role | PR |
| --- | --- | --- |
| `main` | Project README, roadmap and contributor docs | — |
| [`dev/compatibility-baseline`](https://github.com/larbob1/emulard/tree/dev/compatibility-baseline) | Preserved reference | [#1](https://github.com/larbob1/emulard/pull/1) |
| [`dev/performance-phase1`](https://github.com/larbob1/emulard/tree/dev/performance-phase1) | Mapping fast path and reporting | [#2](https://github.com/larbob1/emulard/pull/2) |
| [`dev/performance-phase2`](https://github.com/larbob1/emulard/tree/dev/performance-phase2) | Range-diff mapping | [#3](https://github.com/larbob1/emulard/pull/3) |
| [`dev/performance-phase3`](https://github.com/larbob1/emulard/tree/dev/performance-phase3) | Synchronization candidate | [#4](https://github.com/larbob1/emulard/pull/4) |
| [`dev/performance-phase4`](https://github.com/larbob1/emulard/tree/dev/performance-phase4) | Copy-back and memory | [#5](https://github.com/larbob1/emulard/pull/5) |
| [`dev/performance-phase5`](https://github.com/larbob1/emulard/tree/dev/performance-phase5) | Pipelines and caches | [#6](https://github.com/larbob1/emulard/pull/6) |
| [`dev/performance-phase6`](https://github.com/larbob1/emulard/tree/dev/performance-phase6) | Cumulative candidate, active stabilization | [#7](https://github.com/larbob1/emulard/pull/7) |
| [`dev/performance-phase6-alias-index`](https://github.com/larbob1/emulard/tree/dev/performance-phase6-alias-index) | Isolated alias-index experiment | Not integrated |

The performance PRs are stacked: each targets its predecessor, not main. PR #7 alone does not target main. Preserve the branch history while review and runtime validation are in progress.

## Organization

- Use Phase 6 as the current development base. Keep small stabilization fixes scoped and independently testable.
- Use isolated branches for invasive optimizations. Prefer an explicit draft PR and targeted test plan when ready for review.
- The upstream checkout is temporary source material pinned by the preparation script. Do not push modified runtime code to upstream.
- The active register is `docs/performance-deferred.md` on Phase 6. Main's roadmap is the priority/acceptance view, not a separate source of task status.
- Keep logs, title data and build products out of Git.

## Integration after validation

1. Verify the baseline and cumulative runtime independently, including native Windows and Proton; document flags and output correctness.
2. Review stacked PRs in dependency order. Decide whether to merge each predecessor or create a reviewed consolidated integration PR. Do not merge a failed experiment just because the branch is old.
3. Reconcile README and contributor-doc conflicts: preserve the main project landing page and move development-specific material into the docs index. Keep stable tracking IDs and historical validation links.
4. Integrate only reviewed changes and rerun the full acceptance checks after any merge/rebase. Keep experimental defaults conservative.
5. Archive checkpoints with tags or retain branch refs before deleting branches. Deleting or rewriting any branch requires maintainer approval.

No branch has been merged, renamed, deleted or force-pushed by this organization change.
