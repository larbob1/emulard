# EXT-07 — partial texture first-fill review

Review only. [Claim](https://github.com/larbob1/emulard/issues/55#issuecomment-7224713623). No runtime/builder/CI/flag changes.

## Exact evidence

External [fxceless 83a5593](https://github.com/fxceless/victory-fork/commit/83a5593b66c201b34e5e24e79019920fa1b17702) falls back from failed read_into to copy_mapped when last.hash is None, considers any nonzero byte success, sets hash/partial frame before detile. External fixture tests a committed head and uncommitted tail, not actual staging detile.

Pinned upstream 51700c6d43a3507fa65e50fe4bb64074ce706cd4:
- texture.rs caf17099100edb798b9eb1913bcc58ffa186201e: with_read 462 reuses scratch; refresh_timed 1030–1048 write-watch path detiles without setting hash; partial path 1090+ can set hash on all-zero without detile; refresh_unlocked 1161–1183 resets asked on failed read; detile 1185–1229 sets dirty before looping and can return after writing only a prefix.
- host.rs 458d146aedf6f13dac80782d283a048d80e4a931: copy_mapped 7445+ returns unit; diagnostic modes can direct-copy or skip, plaincopy optional, read_sparse/read_pieces substitute zero on failures, read_into bool and read do not report completed byte count. No stable mapping epoch guaranteed just by a kernel read.
- #32 exact 10339bc4a509a57814e25e1f40f3401614968241 mapping-only publication guard review; relevant apply_texture_snapshot.py 28e291dd040364f35f230580a1da2c3aafc57fbb and propose_texture_publication.py dd686e100eed7d07ff34b4339bfe3e231bf9410b. No composition claimed; actual prepared source required.

## Why not transplant unchanged?

Hash absence is not a reliable staging-valid flag (write-watch path), and hash presence is not proof of successful publication (all-zero partial path or detile error). A mapped all-zero texture is valid data, not absence; nonzero scratch data is not a read receipt. An unreadable page is not necessarily an unmapped hole. Multiple piece reads during a remap can mix epochs; an epoch comparison without exclusion at publication is insufficient. Direct-copy or timing-only modes are not admissible as correctness evidence. Dirty/hash/partial/asked bookkeeping must not claim success for a failed detile.

## Candidate review contract

Use explicit coverage and validated exact-byte reads into private initialized scratch. Only independently established holes may be zero-filled. Distinguish a complete mapped-zero read from no mapped bytes and unknown failures. First-fill eligibility needs actual valid-staging state, not the hash. A mapping/alias proof must cover capture and publication; use approved guard ordering and avoid on-demand judgement reentrancy. A partial fallback must not overwrite existing valid staging merely because its hash is absent. Publish validity, hash, coverage and dirty state only after all intended subresources succeed; keep retry eligible on refusal and review how later mapped pages invalidate earlier partial coverage. No new allocation/lifetime policy is selected here.

Native title-free validation: real mapped/zero/hole/failed reads including short counts, reused scratch, page edges, remap between capture and commit, alias writes, write-watch fill with absent hash, all-zero mapped texture, partial then full mapping, detile failure after earlier subresource, on-demand levels and exact bytes across formats/mips/slices. Confirm no partial staging publication and no false read-count success, preserve previously valid data; test lock ordering and memory bounds. Review #32/AI2/AI1/AI3 and AI4 disposition before implementing. No GPU, title or owner-machine test is requested.

Standalone model: `python -m unittest discover -s tools -p test_ai0_partial_texture.py`. It assumes coherent captured pieces and private detile output, models identity detiling, and does not implement the actual read/mapping/guard/detile contract. Five proposed tests; no native or FPS claim.
