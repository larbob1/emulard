# Claims and handoffs

Use your workstream issue (#11 memory, #12 graphics, #13 reliability) as append-only communication. Read all three issues before touching overlapping symbols. Coordinator summarizes important changes here; don't independently edit this file.

## Claim template
- Role / P-ID / concrete task:
- Base SHA / working branch:
- Files and prepared upstream functions/anchors:
- Shared dependency or conflict:
- Test plan / expected evidence:

## End-of-session handoff
- Role / P-ID / status (candidate, prototype, blocked, validated; resolved only by acceptance):
- Commit SHA / draft PR / base SHA:
- Changes and actual old/new behavior:
- Tests run, pass/fail counts, CI link; unrun tests:
- Performance measurements or "unmeasured":
- Shared changes requested / blockers:
- Exact next action and remaining work:

Current handoff: memory owns PR #9/#10; graphics and reliability may begin their first assignments independently. No automatic communication or background work.

## AI 1 latest handoff
P04/P08/P10: candidate 49ca476, PR #10. Native test-only pinned read fixture committed; latest CI pending. P05 PR #9 native passed at 72fcda9. Earlier software replay native passed at 2465f0a. Next: verify new fixture and mirror native results, audit read-only consumer and synchronization contracts with graphics before changing production reads. No other agent branch touched; performance unmeasured.

## AI 1 coordinated handoff
P07 PR #16 at 1f5cbf1; synthetic checks passed; native pending. P04/P10 pinned native read still pending; requested graphics agreement on GPU synchronization before production consumer work. Requested AI 3 report allowlist for scatter counters. AI 2 PR #14 and AI 3 PR #15 opened independently; coordinator review and owner merge approval outstanding. No cross-branch changes.

## Coordinator combined-build handoff
PR #18, dbac4c6, exact snapshots #9/#14/#15; see status for CI. Other branches continue independently; no merge approved. Next: review combined native result, compare individual switches on owner hardware, then review newer agent PRs. All 24 IDs open.

## AI 1 handoff: refreshed reverse index
P05/P08 PR #19 b8af047; source change isolated, native validation pending. Reconcile against combined runtime only after checks and actual alias churn measurements. AI2/AI3 claims disjoint; no synchronization change. Continue native validation review, not blind integration. All IDs open.
