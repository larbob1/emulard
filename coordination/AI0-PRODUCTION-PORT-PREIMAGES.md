# Production-port preimage and postimage review — #82/#64/#65

AI1 claim [7228333589](https://github.com/larbob1/emulard/issues/11#issuecomment-7228333589), integration 375861704c11106639e612f54272889b8a8a17f3, upstream 51700c6d43a3507fa65e50fe4bb64074ce706cd4. Review-only, not a patcher, registration or merge approval. D22–D25 and owner pause remain.

## Exact reconstruction

Read canonical source bytes from the GitHub connector at exact refs, independently compute Git blob SHA-1 with UTF-8 byte count and blob header, verify each fetched source identity (including scripts and fixture), and require unique replacement anchors. SHA-1 implementation checked against the standard abc vector. Reconstruct the six replacements of existing apply_gpu_copy_perf.py blob ca74c78c0eb9c32529c4c941a526ecb78a995801; the resulting shadow preimage matches the actual #87 historical prepared receipt. This is independent source reconstruction, not actual new builder execution.

| Source/state | LF Git blob |
| --- | --- |
| Raw shadow.rs | 4fa43df7932bb6692d164384cd28b1f08f3001ee |
| Prepared shadow.rs (#87) | 40f1ae02506de251d51e00ebfd36f58e58e7621b |
| #82 corrected shadow, without new fixture | 7229972b47fc789ec2c9968f48b41db6b8e785f0 |
| #82 corrected shadow, with exact #87 fixture | 5144fa26d3b669b29dc7d60c675e7f8f91e114dc |
| Raw/prepared formats texture.rs (#90) | fa719c93953d9e6589c4d2cd27a13d773863c316 |
| #64 only | b38ff33b12552b996c614b6819989db5adb9b3c2 |
| #65 only (actual spread name) | 0debdf9eb188313a25f0541e3ba4ff4972163735 |
| #64 + #65 without new fixture | 9d5f96c702a0a125f04bd34d4247091a3e23c131 |
| #64 + #65 with exact #90 fixture | 249c3b0f799afaeace8508a22d27aebe4d625f23 |

Reconstructed with-fixture shadow and texture hashes match actual historical #87/#90 receipts exactly. #64 then #65 and reverse order produce identical source bytes. The table's without-new-fixture identities retain all preexisting upstream and paired-builder code, including existing tests; they exclude only the additional validation fixtures. Do not call these binary identities or native pass receipts.

## Proposed registration gates (not implementation)

- Verify actual current paired builder preimages against the table, exact unique anchors, unchanged unrelated files, LF normalization and postimage guards; fail closed on mismatch, duplicate application, missing or changed source. Review the actual prepared full diff. No shared builder change authorized by this note.
- Keep #82 correctness correction and #64/#65 performance experiments separable. Default-off experiments required by AGENTS; no new flag semantics or default correction authorization chosen here. A compile-time optional application versus runtime-switch design requires separate review. Do not silently count an arithmetic correction as an FPS optimization.
- #93 exact eedb22903a6ab5df377135ca97612d8224a608e4 is a scratch rehearsal, not a registered runtime. Its native result is still pending at this snapshot. After receipt, actual production-only patcher and flag behavior need separate review and native builds, both disabled and enabled configurations, targeted negative anchor cases and independent AI2/AI3 review. Material composition changes invalidate prior exact receipts.
- AI4 required for actual rendering/copyback/texture parity before runtime inclusion; only under separate authorized local plan. Existing pressure guards and no-title-launch restriction retained. AI3 owns performance acceptance. No merge approval, no production edits, no timing or FPS claims.

Source evidence: #87 exact 4248ed701ff0f4ad984b9d694642461e43a5f7e1 / native 46066027550; #90 exact 573b2d5be276e80572f9548fc6dc187ea0b63dc2 / standalone 46067740495. Exact preview pins #64 a120dd694f4c57256b9ad585dbaceadd0df2d21b and #65 e0770142d98be9fe7fe76ca6f29530f4a958010e. #87 runner d827521370993e267e3dcacd3abf08bbc14a9c63; #90 fixture 8523f85ad032050819619182bc1e92246d4d0864.


## Registration contract proposal — 7228363634

Current builder blob 31bc201ad006b304542e8b03405c1a9090d76804 has mutually exclusive upstream modes, a new-directory requirement, and a single paired-wave patch chain. Existing GPU copy transform ca74c78c0eb9c32529c4c941a526ecb78a995801 runs before later mapping patchers; the proven historical preimages are the *end* of the existing paired-wave chain. Proposed optional build-time selection after the last existing patcher and before git diff --check, not an environment switch on every hot call. This is a proposed choice for review, not an approved CLI, implementation or default change.

Keep three explicit independent selection bits: C = #82 correctness correction, D = #64 detile optimization, S = #65 spread optimization. All omitted means unchanged existing prepared source. C is a correctness candidate rather than a performance experiment; do not authorize an unfixed title run or declare C default-on in this review. D/S remain opt-in. Reject these selections for other upstream modes and reject an existing checkout. Use a fresh disposable directory for every build; never reverse-patch a running or installed runtime.

| C D S | Expected shadow state | Expected texture state |
| --- | --- | --- |
| 0 0 0 | prepared | raw |
| 1 0 0 | corrected | raw |
| 0 1 0 | prepared | #64 only |
| 0 0 1 | prepared | #65 only |
| 0 1 1 | prepared | #64 + #65 |
| 1 1 0 | corrected | #64 only |
| 1 0 1 | corrected | #65 only |
| 1 1 1 | corrected | #64 + #65 |

Every source state refers to the exact without-additional-fixture blob above. Record upstream, existing patcher identity, selection bits, pre/postimage identities, complete changed-file inventory and compile profile in a receipt. Preflight both source inputs and all selected replacements in memory before the first write; validate full postimages; on any failed write or check mark the scratch checkout invalid and never compile/install it. Require no changed files outside the requested paths relative to the prepared baseline. Reject changed preimage, already applied, partial/mixed application, duplicate or absent anchor, mixed CR/LF, unsupported revision/mode and unexpected changed-file inventory. Validate zero-mode byte identity, single-mode independence and both combined texture orders. Rollback means rebuilding the exact selected control in a new directory, not mutating a runtime. Test the patcher contract using synthetic strings and actual pinned source; existing patcher tests only test anchor presence, insufficient on their own for this contract.

Native validation: exact baseline #82 expected debug failure only in isolated regression fixture, corrected regression debug/release/diagnostics; texture 10 original tests and independently pinned oracle for each D/S combination with debug and optimized execution. Test fixture injection remains test-only and changes source identity; production-only release/diagnostics builds need separate receipts. Full existing paired suite for control and selected combined candidate; retain exact nonempty test results, do not claim all eight modes native until executed. AI2/AI3 review actual selected modes and test budget before registration. AI4 local correctness required only on an explicitly authorized exact candidate, D22–D25 unchanged. No timing or FPS claim.
