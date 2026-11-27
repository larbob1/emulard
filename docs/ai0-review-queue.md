# AI0 proposal review queue — advisory snapshot, not integration authority

Frozen integration base `bbea12cb0b2b29618bf4e410d272fe97b81f4bf7`; coordination `45309248136cf197a60173b8889e69729fbf3e68`; upstream `51700c6d43a3507fa65e50fe4bb64074ce706cd4`. Claim [#55](https://github.com/larbob1/emulard/issues/55#issuecomment-7223933031). AI0 independently re-read the eleven open drafts, exact comparisons, actual push-job metadata and logs. All are one commit ahead, zero behind, with 24 unique added repository paths (+2182/-0). All eleven synthetic jobs passed, all portable-copy jobs skipped, no full native or gameplay acceptance. This is a frozen review aid, not a canonical coordination record. No draft is imported, approved or combined here.

## Suggested review sequence

| Order | Drafts | Reason / gate |
|---|---|---|
| 1 | #62, #63, #68 | Review documentation and offline helpers first. #68's actual full-module suites remain unrun. |
| 2 | #64, #65, #66 | Use exact raw-module runner #68 after review: 11, 11, 5 expected tests respectively. Reconcile actual prepared source separately. |
| 3 | #69, #70 | Broader per-stage descriptor/constants paths; exact native host binding/descriptor order tests and realistic workload attribution required. |
| 4 | #71 | Low-complexity loop change, but only relevant if raw-address path is active. Prove actual first-use/order semantics and newly numbered copy behavior. |
| 5 | #67 | Rectangle fallback only; validate actual deferred recording and unchanged early-return order. Pair review with #66; no automatic combination. |
| 6 | #72 | Hold until missing-directory lookup frequency and cost justify extra hash storage. Preserve append-only strong-Arc identity, no eviction or new resource owner. |

Order reflects reviewability and likely applicability, not measured gains. AI1 and the owner may reorder or reject any proposal. B003 evidence did not establish raw-address activation; neither #71 nor #72 is a memory-retention fix. No timing run or new launch authorized.

## Shared upstream review boundaries

- `victory-formats/src/texture.rs` raw blob `fa719c93953d9e6589c4d2cd27a13d773863c316`: #64 Layout::walk, #65 spread; separate anchors, same module. #65 only compares table construction, not end-to-end Layout::tiled substitution. If both accepted, rebuild independently from exact prepared base and prove combined address/copy parity.
- `victory-gpu/src/primitive.rs` raw blob `3f73ee71ec98b59472be17fbf48f9198424fcb74`: #66 expand_rects, called from #67 State::rectangles. Verify both separately before considering combined fallback parity; geometry-stage draws unaffected by proposed scope.
- `victory-gpu/src/draw.rs` raw blob `41380c23a61b93000c4886265c3063676ddc4864`: #67 rectangles, #69 tables, #70 bind. bind calls tables; a cloned bind may still invoke the original tables. Separate clone success does not establish composed behavior. AI2 #35 heap_buffers and #17 input validation are related reviews, not incorporated changes.
- `victory-gpu/src/memory.rs` raw blob `c25636783511fdfbf9692fdd36ef150f69ea666e`: #71 ready final loop, #72 Memory::map/struct/new. A ready clone on original Memory is not a test of MemoryIndexed. AI1/AI2/AI3 must review current ownership, numbering, first-use and prepared source before any combination. No D24 mapping timing or retirement policy change.

Raw source pins do not establish the identity of prepared post-patch runtime files. All changes remain default-off/test-only. AI1 alone registers shared native CI, with actual nonempty exact test filters, expected counts, full prepared-source review and applicable builds. AI3 reviews performance methodology and acceptance. AI1 records AI4 REQUIRED or NOT REQUIRED with rationale per exact contribution. D22–D25 continue: no title run, owner-machine access, self-approval or merge.

## Frozen push receipts

| PR | Exact head | Synthetic job | Python | Range | Portable |
|---|---|---|---:|---:|---|
| [#62](https://github.com/larbob1/emulard/pull/62) | `a2feaefde8732808c3e292c1128856c5f9cc80a2` | [140621001694](https://github.com/larbob1/emulard/actions/runs/46032924791/job/140621001694) | 113 | 4 | Skipped |
| [#63](https://github.com/larbob1/emulard/pull/63) | `211f74bb0893d866d60aca05c136588456ac049a` | [140622314289](https://github.com/larbob1/emulard/actions/runs/46033309116/job/140622314289) | 126 | 4 | Skipped |
| [#64](https://github.com/larbob1/emulard/pull/64) | `1b118a210d02d19686a9389fc30ea723c670bec4` | [140623740655](https://github.com/larbob1/emulard/actions/runs/46033728865/job/140623740655) | 117 | 4 | Skipped |
| [#65](https://github.com/larbob1/emulard/pull/65) | `5af0fa2cbadf311947f0101eefad18b16bcc2f9a` | [140624869712](https://github.com/larbob1/emulard/actions/runs/46034053268/job/140624869712) | 116 | 4 | Skipped |
| [#66](https://github.com/larbob1/emulard/pull/66) | `3b22fabc99cef39f20b87abe67e8e4e1a9c0e6c1` | [140625879108](https://github.com/larbob1/emulard/actions/runs/46034357407/job/140625879108) | 116 | 4 | Skipped |
| [#67](https://github.com/larbob1/emulard/pull/67) | `2d97a632ce340e84e8bb04b26aaab211b8dd6e3b` | [140627556139](https://github.com/larbob1/emulard/actions/runs/46034853680/job/140627556139) | 116 | 4 | Skipped |
| [#68](https://github.com/larbob1/emulard/pull/68) | `ff250700594da5e4838cce95bb5a9b147d8a0c66` | [140629502767](https://github.com/larbob1/emulard/actions/runs/46035428750/job/140629502767) | 118 | 4 | Skipped |
| [#69](https://github.com/larbob1/emulard/pull/69) | `24ae553e449bac498f29cde7395d6b6ef95ec888` | [140633734659](https://github.com/larbob1/emulard/actions/runs/46036681453/job/140633734659) | 116 | 4 | Skipped |
| [#70](https://github.com/larbob1/emulard/pull/70) | `1710d374f7d6c22b6ef158f2704fb0b5653ea91c` | [140635733748](https://github.com/larbob1/emulard/actions/runs/46037269822/job/140635733748) | 116 | 4 | Skipped |
| [#71](https://github.com/larbob1/emulard/pull/71) | `036dec4dc4b6a012d2e860e1ae779b67f75719eb` | [140637490293](https://github.com/larbob1/emulard/actions/runs/46037787255/job/140637490293) | 116 | 4 | Skipped |
| [#72](https://github.com/larbob1/emulard/pull/72) | `4a44d7bfec6aaf7a9acb3643882addb8203ddeec` | [140638573817](https://github.com/larbob1/emulard/actions/runs/46038099830/job/140638573817) | 116 | 4 | Skipped |

Repeated baseline tests are not independent new tests. The embedded extracted Rust tests in #64–#67 and #69–#72 passed their own model gates; #68 exercised its runner on a tiny generated module only. No sum of synthetic case counts represents native runtime coverage.

## Offline checker

Historical scope: PRs #62–#72 only, not the current AI0 proposal inventory. Duplicate JSON object keys are rejected at every nesting level, even when values agree.

`python tools/ai0_review_queue.py --print-reference` prints the frozen reference shape. Collect current PR/diff/job metadata independently (including actual checkout and test counts from logs), normalize to that shape, then run `python tools/ai0_review_queue.py snapshot.json`. The checker performs exact frozen matching, rejects drift, and reports shared upstream groups. It does not authenticate a supplied file or fetch current state. Printing the reference and feeding it back is a smoke test only; it is not independent evidence. Run regression tests with `python -m unittest discover -s tools -p test_ai0_review_queue.py`.

If any exact head, base, path, status or receipt changes, stop and obtain fresh review and applicable validation. Do not rewrite this snapshot to manufacture a pass. AI1/owner retain all review and integration authority.
