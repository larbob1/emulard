# B003 memory-pressure triage (P01/P03/P18)

AI4 #27 comment 7210705368 reports a 17s transition with host-copy count
7 to 4120 and capacity 202 to 3703 MiB, windows 6 to 658 and 28 to
3000 MiB, runtime working set 3637 to 12430 MiB, private bytes 2566 to
3191 MiB. This is existing numeric evidence, not a full RSS attribution.
Pinned victory-gpu copystat.rs::log_memory emits separate numeric lines.
The offline tool reads four specific groups without exporting source lines:

    python3 tools/memory_report.py local-selected-phase.log > local-memory.json

Select startup, transition or another operator-confirmed phase locally;
do not assume the parser knows scene boundaries. Each group's relative
input-line ordinals and valid/invalid counts, first/last/min/max and signed
endpoint change are independent. No timestamps are inferred, no missing
samples filled. The runtime prints rounded MiB despite the MB label.
Exact full-line numeric patterns accept whitespace variations but reject
changed/extra payloads; the primary memory marker also requires the
private-memory signature to avoid unrelated video-memory lines.

The main group separates current host copies/windows/snapshots/staging and
textures from cumulative upload/shared/card buffer creation. The holders
group reports descriptor-slot and list/heap-pass window capacity, not
exclusive owners; a window can appear in both. The coverage group compares
window capacity with title address-space coverage, not unique physical
pages. Shader cache group distinguishes container/translation sizes from
pipeline file size (not resident RAM). Never add these categories to RSS or
use their endpoint changes as allocation bandwidth. Decreasing cumulative
counters may indicate restarts or ordering; retain them as observations.
Fields missing in a phase remain unknown. Compare independently sampled
host RSS and available RAM only with local phase evidence; do not align
samples by position across files.

Read-only tool; no new launch, instrumentation, eviction or budget change.
Keep raw logs local, share reviewed numeric summaries. Existing memory
guard stays unchanged. No prolonged tests until coordinator/owner clear a
bounded plan. No claim leak, ownership, causal bottleneck or gameplay FPS.
Exit 0 at least one valid record, 1 unavailable, 2 no valid record.
