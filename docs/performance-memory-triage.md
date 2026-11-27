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

## B003 holder and sweep follow-up (D15)

AI4 #27 7210742582 reports 17s windows 6/28 to 658/3000 MiB, COM-holder
proxy 4/16 to 648/2960 MiB, Arc-holder proxy 3/16 to 658/3000 MiB,
asked spans 8 to 1231 MiB, copied-page accounting 9 to 1199 MiB and
address union 24 to 2276 MiB. Cumulative sweep accounting 1/4 to 3/16
MiB (two separate release events in full run). No new launch.
The fifth parsed group is the existing memory let go since the start line:
window/staging cumulative releases and current asked-span sum. Declining
asked-span is not a cumulative reset. Release accounting does not measure
actual physical reclamation (retire may defer destruction).

Source-level qualification: shadow::memory deduplicates LOOSE Arc pointers;
shadow::window_use and windows iterate map entries without deduplication.
Window holder metrics are COM reference count >1 and Arc strong count >1,
not direct identification of descriptor slots or particular lists, and can
include other owners and repeated entries. Do not calculate percentages of
unique windows, sum proxy groups, or infer eligibility from their difference.
Age changes cannot safely replace Arc/COM/retire protections. #35 review
remains blocked on independent ownership for recorded/replayed lists that
skip heap refresh; a retained ID3D12DescriptorHeap is not proof the Rust
HostHeap wrapper and its resources are retained. No production authorization.
