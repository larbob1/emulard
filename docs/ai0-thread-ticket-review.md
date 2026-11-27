# EXT-05 — multidimensional compute thread ticket review

Review-only. No changes to the translator, cache, builder, switches, or runtime.
See [claim #55](https://github.com/larbob1/emulard/issues/55#issuecomment-7224457904) and [audit register](https://github.com/larbob1/emulard/issues/11#issuecomment-7224279556).

## Source and scope

External [implementation](https://github.com/trustno1-coder/VIctory-NVIDIA/commit/854f57ff7a856aba3fc55540968289c2da7c4c86) and [test](https://github.com/trustno1-coder/VIctory-NVIDIA/commit/2dc3df1c72275a1086330ad3b7cba7f9494fe874), credited to Vice-Tay c125c0c / fxceless #1243. External reported RTX 5070 Ti coverage 32/64 to 64/64; not our native result.

Pinned raw upstream 51700c6d43a3507fa65e50fe4bb64074ce706cd4:
- lower.rs 6e7aa710b1ae931ae72696add85a96bfcc3077a3: setup 1094+, wave_base 3683, console_thread 3716, thread_id 4174.
- wave64_tests.rs 4c63fda6029768eeb981dcdc7fcd30b249ddc31e: native_of 53, lowered_on 112; existing paired tests.
- shader_cache.rs c5365c4c5dce2f28d4142719663640e8d162d350: build 50 calls translation_fingerprint.
- emit/mod.rs 282d7c0757c70b2a71c58bd989191962314d55e1 and build.rs b10212507580930db77c14d9757f942bb6b3e09c: automatic translator-source fingerprint and quoted switch discovery.

The original flat rounding can assign two 16-by-2 tiled waves of a 32-by-2 group identical console indices. The external packed counter allocates full waves from the low half and tails from the high half, placing tails after floor(group/width)*width. That is sound in the model if there are full waves and at most one partial wave. The hypothetical partition 16+16+32 of 64 produces out-of-range IDs under that rule. This does not establish that a supported GPU schedules such a partition; it identifies an assumption to prove or guard. A constant store of one measures coverage, not duplicate writes.

The pinned paired translator instead advances 64 console lanes per 32-host-lane wave. Do not replace this stride with host width, change own-LDS scratch/barrier behavior, or change paired/exchange admission as part of the ordinary-wave correction. Do not infer safety of sparse hardware lane ranks from the model.

## Required implementation review

1. Recover actual prepared lower.rs and all paired/translation/cache compositions; identify the ordinary multi-wave console-lane branch independently of paired and split/exchange paths.
2. Preserve the existing paired stride and barriers. Define when all entry lanes participate, the full/partial-wave partition contract, and behavior for an unsupported layout; check LDS capacity and synchronization. Do not silently omit threads or introduce a potentially divergent group barrier.
3. Use one immutable process configuration for translation and cache identity. Pinned build.rs already discovers quoted VICTORY_* literals and fingerprints source; verify actual prepared scanner, disk cache, process-local positive/negative shader and linked PSO caches, warm-up and both modes. No live environment mutation in parallel tests.
4. Native title-free test: use per-index atomic visit counts (not constant stores), independent out-of-range guard counter, expected exact visits and correct values for each x/y/z coordinate. Require 32x2, 8x8, 16x4, 1D control, partial groups, multi-wave full groups, supported host Wave32/Wave64, and paired-wave regression. Keep explicit capability receipts and report unavailable hardware as untested, not passed.
5. Require DXIL validation, release/diagnostics builds, cache separation on cold/warm paths, and matched real Proton correctness before an acceptance claim. Do not register shared native CI or run owner hardware from AI0. AI1 exact review, AI2 affected owner, AI3 acceptance and AI4 REQUIRED/NOT REQUIRED rationale.

## Model

`python -m unittest discover -s tools -p test_ai0_thread_ticket.py`

The model is arithmetic only; no native compiler or GPU correctness, no timing or FPS claim. Existing AI2 proposals and all AI0 draft branches are unchanged.
