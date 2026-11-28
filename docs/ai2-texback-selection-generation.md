# AI2 R2 actual selection-generation baseline (P13/P14/P21)

Scratch-only witness approved #12 7231976846, claim7231981568, AI3 concurrence7231842318, AI6 nonoverlap7231941969. Base 08472987ffee011796d48d7c90114439a6a68908; upstream 51700c6d43a3507fa65e50fe4bb64074ce706cd4. Separate from #127/#128 and #129/#131. No production fix, actual shader execution, actual remapping, GPU submission, publication, or gameplay proof.

## Exact preparation

Only append one LF and exact LF fixture bytes to each disposable prepared source. Require actual builder 31bc201ad006b304542e8b03405c1a9090d76804, paired-wave refresh, exact raw/prepared identities and all dependent pins from #128; verify prepared manifests and canonical isolated root/child, full non-.git inventory dry unchanged/apply exactly three changes, append inverse and exact postimages before compilation. No existing shared builder/workflow edits.

| Prepared source under crates/victory-gpu/src | Raw | Prepared | Fixture | Appended |
|---|---|---|---|---|
| resource.rs | 1fff3d6a42db6d2eea17de0b7d325ebec5eb6dfc | 215122c8728e95b3748b135f6c760f0690a959d8 | 80250d2d44288ba0d708f39c4ed674aec6bc5d30 | 314c10076c9fa7f07a8fb24f69b4c44f3b758185 |
| texback.rs | 3102a4f9ed2f80c86a28fcc5070b855143279574 | 3102a4f9ed2f80c86a28fcc5070b855143279574 | ac2ddc2d44ac86e7f638d760725be5b99298e243 | 37740c173c60a85fe26c9627c68221d70c051bec |
| host.rs | 458d146aedf6f13dac80782d283a048d80e4a931 | 88acbb3b2cf550cdf2303685fcc32249f9e46328 | 521f487b71107fb131593a80ec9ebad3afec6527 | 459ca0f8b55fcaa72fbcc06ffdb090e507a05311 |

Fixture paths under probes/: ai2_texback_record_resource.rs (exact reviewed #127 helper), ai2_texback_selection_observe.rs, ai2_texback_selection_generation.rs. LF postimage byte lengths 161182,12850,455473 respectively. Independent executed JS SHA1 reconstruction from exact fetched raw and patch inputs: resource two unique placed-uav hunks, host eleven presentx + five present-capture hunks, texback unchanged; all raw/fixture Git hashes matched connector, patch and append inverses true. Predicted, not actual builder receipts.

## Cases

Each ignored test is host::ai2_selection_generation::actual_selection_<suffix>. Fresh WARP process per case/profile, exact discovery, locked diagnostics debug/release, direct watchdog and exact named normal pass. Clean inherited VICTORY_/RUST_TEST_ flags; set VICTORY_D3D12_WARP=1, VICTORY_SWEEP=0, VICTORY_TEXTURE_BACK=7x3f61; COPY_MODE and GPU_TIMING absent. Require actual adapter/ref LUID equality and software1, healthy device, initial/final host submitted/STARTED/FINISHED/fence all zero, no GPU submission. All cases require full owned allocation oracle and actual resource registry cleanup before free; retain real ticket Arc identity across invalidation, selection and close. Independent eligibility Target::new creates actual additional tracked ticket, never enters deferred list. Observations clone at most two identities under short guard; no guard crosses invalidation/selection/close. Distinct owner uses two separate owned allocations and actual textures.

| id | suffix | invalidated | distinct | selected | live / recorded | missing_current |
|---:|---|---:|---:|---:|---:|---:|
|0|repeat|0|0|1|1|0|
|1|left_adjacent|0|0|1|1|0|
|2|right_adjacent|0|0|1|1|0|
|3|first_byte|1|0|1|0|1|
|4|last_byte|1|0|1|0|1|
|5|interior|1|0|1|0|1|
|6|full|1|0|1|0|1|
|7|empty_start|0|0|1|1|0|
|8|empty_interior|1|0|1|0|1|
|9|empty_last|1|0|1|0|1|
|10|empty_end|0|0|1|1|0|
|11|distinct_owner|0|1|2|2|0|

These are **expected existing baseline observations**, including six cases showing missing current selection after direct ticket seam. A successful native witness is adverse evidence, not correctness acceptance for a repair. Empty ranges are seam-only and not actual unmap reachability. In nonempty overlap cases independently eligible second intent exists while list retains invalid old ticket. Actual close may settle stale state before record None. No-submit does not imply no commands recorded; no prelude execution, GPU copy, land or marker/queue publication. No forced allocator address reuse; no fake ticket. List dropped before owned resources; retained observation tickets invalidated by actual release; no global retirement inference.

Expected strict stderr selection_adapter actual_high=<canonical signed32> actual_low=<canonical unsigned32> warp_high=... warp_low=... software=1; exactly one selection_case id=<id> second_intent=1 independent_eligible=1 invalidated=<table> distinct=<table> selected=<table> live=<table> recorded=<table> missing_current=<table> submitted=0 healthy=1 preserved=<2560*selected> guards=<62976*selected> cleanup=1. Receipt after actual owned release and free and final device/host-fence check. Require same executable hash within profile, exact 12 named tests each profile; distinguish 12 normal control observations and 12 adverse baseline observations across two profiles (24 total). No duplicate/displaced prefixes or stdout receipts; strict normal test summary and exit0 mandatory. No native compile/execution yet (0/24), no automatic registration from this PR; AI1/AI3 independent source review first.

Ordinary still-required texture refusal at selection/record/landing and actual dependent caller behavior are separate critical-path tasks. No policy edit or production inclusion authorized; #71 HOLD all24 open.
