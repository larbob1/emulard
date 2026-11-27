# EXT-16 — GPU texture detile admission and integration review

Review only. [Claim](https://github.com/larbob1/emulard/issues/55#issuecomment-7224954335).

## Source evidence

External [fxceless 3461f52](https://github.com/fxceless/victory-fork/commit/3461f52faab6eff2f8526b1eb36037973674414f), default off. gpudetile.rs ac10870ba3cdf63292a05d63ed4d2b637d3f7cdf: raw_layout237, jobs288–348, record353–370, payload parity520–596 and test598. texture.rs 504a44282359ce6566826612f9d625de2f38d7a0: record_detile1034, staging1660+, separate device-local spare pool. It copies tiled bytes to an upload buffer, dispatches conversion to a linear UAV in the submission prelude, then copies into the texture. Reported WARP parity is external evidence only; test returns if software adapter unavailable and compares row payloads rather than padding. No measured Emulard result.

Pinned upstream 51700c6d43a3507fa65e50fe4bb64074ce706cd4 formats texture.rs fa719c93953d9e6589c4d2cd27a13d773863c316 (addressable518, offset534, detile588); GPU texture.rs caf17099100edb798b9eb1913bcc58ffa186201e (staging/refresh and detile1185). #64/#65 CPU detile previews, #32/#80 mapping publication and #79 fence review are relevant; no actual prepared composition.

## Concrete admission questions

External jobs zips footprints and rows and divides/modulos by mips, assumes complete input from D3D, checks full footprint arithmetic against UINT32_MAX but does not receive actual buffer extent. Shader writes full 32-bit words, including rounded tail of 1/2-byte elements. The external test itself notes last-row padding can lie outside total. This is an allocation-contract question, not proof of a native out-of-bounds write: actual resource rounding/pooling and legal footprints must be checked. Explicit x-group bound, checked arithmetic, dimensions, full expected mip/slice set, nonoverlap, raw aligned source word loads, tables/mask bounds, and actual allocation width should be independently established. No unsupported layout may silently produce a partial dispatch plan.

The conservative destination model uses exact expected count, equal logical/footprint row/depth counts, alignment, rounded final write, 32-bit capacity, dispatch limits and disjoint bounding spans. It may reject safe layouts. It does not prove source offsets, actual D3D footprint metadata, source word alignment or shader execution. Before a port, require all admission and allocation failures to select existing CPU path before recording any GPU upload that consumes the intermediate buffer.

## Ownership and correctness gates

- Compare actual prepared Layout::offset and detile for supported swizzle/element sizes, mips, arrays, thick 3D, compressed blocks, tails, odd widths and held-level masks. Reject unsupported XOR/plane/sample layouts until proven. Guard coherent capture and initialize raw padding and mask; do not use failed partial reads as valid data.
- Require byte-exact copied payload with independent CPU reference, sentinel/canary around rounded writes and unused ranges, full subresource coverage and actual destination capacity. Verify no silent WARP skip. Explicit success/unsupported/failure receipts, release and diagnostics builds.
- Review prelude allocation/record/close/submit failure; recording a submission marker is not proof of execution. Repeated list use, two submissions, failed first prelude, cross-queue wait, UAV-to-copy transitions, raw input immutability until consumption, pinned output/staging until confirmed fence and bounded pool accounting. A second pool can raise peak VRAM; count active and spare bytes separately, not simply CPU bytes saved.
- Only after actual native correctness and AI1/AI2/AI3 review plus AI4 disposition, compare matched Proton with fixed explicit mode (not alternating live texture cohorts), correct rendering, CPU critical path, GPU dispatch/copy overhead, VRAM/RAM, frame tails and streaming stalls. No timing instrumentation or default changes in this PR.

Standalone: `python -m unittest discover -s tools -p test_ai0_gpu_detile_plan.py`. Five proposed tests. No shader or runtime patch, no native execution, no GPU performance claim.
