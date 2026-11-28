# R2 isolated selection-generation repair preview

AI1 exact approval #11 comment 7233307109; AI2 claim #12 comment 7233387344.
Pristine integration 08472987ffee011796d48d7c90114439a6a68908,
upstream 51700c6d43a3507fa65e50fe4bb64074ce706cd4. No composition with
#134 or R3, no production registration. Historical #134 native 24/24
(12 controls + 12 adverse observations) remains intact and is not a repair.

## Scratch transformation

Use Python 3.12+ and an independent disposable checkout prepared by pinned
build_runtime.py --paired-wave-refresh. Run
`python tools/prepare_ai2_selection_repair.py <checkout>` for dry-run,
then the same command with --apply in that disposable checkout only.
The preparer checks raw/prepared and manifest identities, exact fixtures,
three uniquely reversible replacements, three append postimages, checkout
isolation and complete non-.git content inventory. It does not build or run
tests. If application fails, discard the checkout rather than retry in place.

- texback: empty or saturated-empty remap interval is a no-op; current
  ticket predicate uses Acquire.
- host: same-owner valid target stays in its slot without allocation.
  Same-owner stale target is replaced in that slot only on successful actual
  Target::new. A refused new target leaves the old invalid target, not a
  successful delivery. Drop replaced target outside deferred guard. Existing
  mapping lock order, record/land validity rechecks and no auto-rebind at close.
- These changes do not guarantee concurrent mapping atomicity, guest resource
  lifetime, full publication, or required-failure disposition.

Static reconstruction from actual raw sources and paired patches: host
11+5 hunks, resource 2 hunks, texback unchanged. Intermediate repair blobs
host 031a65c12bbab967759383b2a75a3be46c46bbde,
texback a17dfb5f693163d64ab8f4a60ede71e52c2f596a.
Full predicted postimages: host 8bea49c650a0eec442729ee7d3c12f16354af54d
(456888 bytes), texback 75641b7edbefa66a69d81d144a9f637f0abbe7e4
(12994), resource 314c10076c9fa7f07a8fb24f69b4c44f3b758185 (161182).
Exact inverse checks performed on reconstructed inputs, not actual native
preparation. Fixture host 97485281a3d2863f302c72205e9c5527c3f757e4;
observer ac2ddc2d44ac86e7f638d760725be5b99298e243 and owned resource
80250d2d44288ba0d708f39c4ed674aec6bc5d30 identical to #132.

## Planned independent native gate

AI3 exact review before AI1 separate registration. Exact ignored names
host::ai2_selection_repair::actual_selection_* in fresh direct processes,
debug/release diagnostics, WARP1 SWEEP0 TEXTURE_BACK=7x3f61,
COPY_MODE/GPU_TIMING absent; exact executable digest, normal libtest framing,
exit0, watchdog, two canonical stderr receipts, actual WARP LUID identity.
Cases 0-11 per profile (24 matched correction observations) plus case12
per profile (2 stale-only regressions). No submission or actual remap.

| IDs | Original ticket | Selected ticket after intent | Recorded |
| --- | --- | --- | --- |
| 0,1,2,7,8,9,10 | valid | same Arc | 1 |
| 3,4,5,6 | invalid | distinct actual current Arc | 1 |
| 11 | valid | original plus distinct owner | 2 |
| 12 | invalid | no second intent; no rebind | 0 |

All current selected tickets must be valid and independent eligible
diagnostic ticket must not enter list selection. Empty interior cases 8/9
are seam-only. Case12 has no second intent, no independent eligible ticket,
and missing_current=0 refers only to absence of a current second obligation;
not a claim of successful delivery. A failed Target::new is not accepted
as repair, but is not independently injected here. Full owned bytes and guards
preserved, actual guest release, ticket invalidation, registry cleanup and
healthy zero fence; do not claim all resources globally retired or zero
recorded GPU commands. Original R2 actual receipts are #134; do not
reinterpret them. No actual native run, production change, OOM, landing,
notification, gameplay or FPS claim.
