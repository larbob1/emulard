# AI6 B0/B1 ordinary buffer readback publication witness (P18/P24)

Scratch-only candidate, authorized in #46 comment 7231867998, implementation claim 7231892498. Base 08472987ffee011796d48d7c90114439a6a68908; upstream 51700c6d43a3507fa65e50fe4bb64074ce706cd4. Derived from #124 positive whole-wait fixture, not composed with #124. No production patch, policy change, default change, title access, native registration or performance evidence.

## Prepared source and preparation

Use only an independent disposable paired-wave prepared checkout and Python 3.12+. The preparer defaults to dry-run; its apply mode verifies six raw/prepared source pairs, exact builder and both fixture blobs, four host and three queue unique reversible anchors, exact LF postimages, path type and root isolation, full non-.git inventory before/after (only host.rs and queue.rs may differ). Failed preparation blocks compilation; no automatic retry. Actual builder execution and inventory receipts are required by a future AI1-owned registration.

| Source | Prepared | Fixture | Predicted postimage |
| --- | --- | --- | --- |
| host.rs | 88acbb3b2cf550cdf2303685fcc32249f9e46328 | 7c76e807a58d1eb972b1d7bedc515f1361fa812d | 84fb1319bf8c0c97d88b55a397a98d19bdbfc0f3 |
| queue.rs | af59e827f75e050e3be49722ab0a704c0ec6cbb6 | bad14b4e49047f026f01e3a0cd5d6d33bab83c87 | 8490c97f3e3063d3adcd606f10da79d12dab01bd |

Prepared reconstruction from actual fetched raw and patch inputs: host 11+5 hunks, queue 4+1 hunks and two tile transform replacements, exact inverse. All seven new anchors unique and inverse restores pristine prepared source. These are static predictions, not executed preparation or native build receipts.

## Exact route and test protocol (future registration only)

Fresh strict WARP legacy ABI Windows process per case/profile. Diagnostic debug and release builds, locked Cargo, exact discovered ignored filters:
- queue::ai6_readback_witness::actual_readback_b0
- queue::ai6_readback_witness::actual_readback_b1

Clear inherited VICTORY_ and RUST_TEST_ flags; explicitly D3D12_WARP=1, QUEUE_WAIT=1, SPLIT_WAITS=0, CUT_WAITS=0, WAIT_FORCE=0, WAIT_ASK=0, LATE_WAIT=0, ASYNC_SUBMIT=0, JOIN_PARTS=0, ASYNC_PRESENT=0, CARD_BUFFERS=0, RELAY=0, WIDE_BACK=0 (all VICTORY_ prefix; GPU_TIMING absent). Verify effective predicates, independent actual/reference software adapter LUID, initial and final host fence/device health, same executable within each profile. No other cases run in the process. Require external 60s direct watchdog and preserve partial stdout/stderr. No watchdog/abort/other exit accepted.

Owned upload/shared/readback buffers, two 88-byte initialized outputs (64 active and 24 guards each), an aligned wide equality marker with identical low half, guest fence initially 0. Real consumer list recorded with wait, detached into actual Value/Run/Signal, producer runs actual queue and host. B0 observes selected tuple before ordinary Map/copy/Unmap. B1 skips exactly the selected producer tuple before Map, after actual healthy GPU fence and before the unchanged deferred marker publication. This is a deliberate test-only refusal seam, not a real driver Map failure. No independent thread, joined submission, late/relay/card/cut/force route, or consumer dispatch on B1. Fixed thread-local observer state; no new allocation, locks, I/O or wait under runtime guards; raw reads only fixture-owned initialized memory on sole synchronous fixture thread. Pre-removal gate requires eligible B wait, base0, !all, !joining and joined.is_empty(); ordinary RAII return drops held/RELEASING/Leave before independent post-execute snapshot. No removal or fake completion. B1 exits with all resources live, not normal teardown.

B0: exact normal named libtest success and exit0 (two profiles), one canonical adapter row and one case row on stderr, no displaced/duplicate prefixes:
```
readback_case id=0 selected=1 refused=0 published=1 stopped=0 healthy_fences=2 producer_bytes=64 consumer_bytes=64 guard_bytes=48 marker=wide_equal guest_fence=17 held=0 waiting=0 forced=0 retired=0 events=0,1,2,3,4,5,6,7
```
B1: exact ignored discovery and exact filter invocation, one adapter and one case row on stderr, dedicated exit86, reject libtest normal success summary, unexpected exit/abort/timeout/missing/duplicate/displaced receipts. No libtest pass count for B1:
```
readback_case id=1 selected=1 refused=1 published=1 stopped=1 healthy_fences=1 producer_bytes=0 consumer_bytes=0 sentinel_bytes=176 guard_bytes=48 marker=wide_equal guest_fence=0 held=3 waiting=1 forced=0 retired=0 terminal=86
```
Adapter format: readback_adapter actual_high=... actual_low=... warp_high=... warp_low=... software=1, canonical ASCII signed/unsigned ranges, exact equality. B1 actual full independent memory/fence and held queue oracle after guard return, retired registry empty not global ownership proof. Report two normal control passes and two adverse witnesses separately. Actual runtime/native counts currently 0/2 and 0/2.

AI1/AI3 exact source review required before any registration. No general publication repair, normal failure recovery, forced/late/cut/join/texture route proof, gameplay launch, merge, task closure or FPS claim. #71 HOLD.

## Narrow phase correction after failed native #131

Exact original #129 `696c4cd695de5bf1c8072b802156d4d4a239ea04` and failed native #131 `b9df7391793f27fcdd9cbcc8a293b51d35816ad1` preserved. [Run 46095264304](https://github.com/larbob1/emulard/actions/runs/46095264304): actual preparation, manifests and debug compilation passed; first B0 debug emitted adapter only and failed the normal receipt gate, child exit unlogged; other three cases not run. Source diagnosis: healthy advances phase 1 to 2 and 4 to 5 before select; select must check 2 and 5. AI1 approval #46 7232015543, correction claim 7232025850. Only those two fixture conditions changed; host helper, all production anchors and other assertions unchanged. Independently reconstructed old and revised queue postimages, exact inverse, new LF length 88550. No revised native evidence yet; 0/2 B0 normal and 0/2 B1 witnesses. Exact AI1/AI3 review and separate runner registration required before a new native run. No inference about the exact prior termination site or production behavior.

## Oracle hardening follow-up to #133

AI1 approval #11 7233307109; independent AI3 oracle review #13 7233279820; AI6 claim #46 7233388028. Separate scratch child of exact #133 `8d3cf9bd651587f96125a112a477c6d256c89947`. The sentinel is now 0xff, outside the modulo-251 generated data; 0xe7 matched input byte 60, masking one omitted write in each output. Require the retained consumer rb interface identity, exactly one phase-5 selection, true at consumer readback and B0 final, false at B1 final. Existing phase correction, all prior assertions and receipts, host helper, and three queue/four host anchors unchanged. Predicted queue postimage 8490c97f3e3063d3adcd606f10da79d12dab01bd (88947 LF bytes), independently reconstructed from pinned raw queue and selected patch/transform inputs; old #133 postimage and inverses verified. No revised builder execution, compilation or native test; 0/2 B0 and 0/2 B1. New exact AI3 review and separate AI1 registration required. No production, title, merge or FPS claim.
