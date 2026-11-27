# Mapping hot-path experiment

Originally isolated; the branch passed Windows CI and its opt-in source changes are now ported to cumulative Phase 6. Combined validation remains pending. Two independent opt-in experiments:

- `VICTORY_MAP_DIFF=1 VICTORY_MAP_DIFF_RUNS=1`: group contiguous backing
  slices inside changed spans using the existing coalesce-or-page mapper.
  Unchanged spans still use the existing dirty notifications and both mapping
  locks remain in place. It does not batch changed scatter requests.
  `mapping diff run totals` counts completed logical runs/pages, not actual
  host calls. Failure may leave partial changes as before.
- `VICTORY_TEXTURE_VIEW_ESTIMATE=1`: use the existing renderer view census
  for fully covered texture residency estimates. The read guard must be
  available immediately, otherwise the original host-query path runs.
  Gaps, missing entries and overflow fall back. No direct memory read or
  committed-memory safety check is replaced. `texture view estimate hits`
  counts avoided estimate paths.

Run each switch independently, compare exact same scene/cache/profile,
record frame times, actual host calls, texture residency accuracy, drops,
and visual output. Source anchors and synthetic fixtures are not proof
of runtime correctness. P05/P06/P08/P11/P15/P24 remain open. No FPS gain
has been measured.

Native Windows CI tests the existing physical-page suite, a mixed contiguous
changed-run case, replay with run batching enabled, and a coverage fixture
that compares the new walk against the existing cover function. Use Proton
on actual hardware after the full native suite passes.

The cumulative branch also adds `VICTORY_MAP_ALIAS_DIRECT=1`: with alias runs enabled, try the original contiguous mapper before splitting/coalescing. Compare it separately; `alias direct run totals` reports attempts and successes. A miss falls back to the established helper. No FPS gain is claimed.
