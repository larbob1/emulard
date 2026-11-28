# AI6 P18/P24 ordinary whole-memory-wait positive gate

Approval: #46 comment 7231297808; claim 7231304187; AI2 review 7231251397; AI3 review 7231140144. Base 08472987ffee011796d48d7c90114439a6a68908; upstream 51700c6d43a3507fa65e50fe4bb64074ce706cd4; builder 31bc201ad006b304542e8b03405c1a9090d76804.

## Scope

Disposable prepared checkout only. The two Rust probes are not compiled by normal builds. The preparation script requires the actual pinned paired-wave source, verifies all raw Git blobs plus LF prepared identities, then verifies unique forward and inverse observer anchors before writing two scratch files. No shared builder, workflow, or production patch changes. Queue/list/fence/device prepared pins are predictions until actual builder output matches; host prepared pin was previously observed in #111. Postimage hashes are printed, not yet independently frozen; reviewer and native registration must pin them before execution.

| Source | Expected prepared LF blob |
|---|---|
| queue.rs | af59e827f75e050e3be49722ab0a704c0ec6cbb6 |
| host.rs | 88acbb3b2cf550cdf2303685fcc32249f9e46328 |
| list.rs | 3bf89f3c9b17f14c2ec4fa4480e3378e6ac8857e |
| fence.rs | b82033550223aa628bd75a700c22465f3a5ca389 |
| device.rs | dfbf2b2253a8f739e418e7fbcc3a810a66e19252 |

Fixture queue blob 755602d634e6e6c083c7f88611a17a44306cbc76; host helper blob facafd3fcaa231cd04c8002bb1dae95205f7966c.

## Actual route and oracle

Fresh legacy interface, direct host, strict WARP LUID, ordinary whole waits. B registers wide equality wait with same low 32 bits but differing upper 32 bits; actual execute detaches exactly one list, order [0], and signal queues behind it. Before A, verify exact held Value/Run/Signal, WAITING contains only B, owned marker readable and unequal, both outputs unchanged, guest fence zero. No manual unmet_waits, no manual release, no force. A copies 64 nonuniform bytes to shared default buffer, transitions to COPY_SOURCE, copies to its own readback; B copies reversed rows from that same shared resource to a separate readback. Both have 64 active CPU bytes and 24 untouched guards/padding per output. A deferred marker separate from outputs; guest fence separate.

Fixed capacity thread-local observer exact phases:

0. B held; both outputs sentinel, marker initial, fence 0.
1. A actual queue Signal, event registration and wait succeeded; same-domain fence 1 and device healthy before FINISHED/bury.
2. A full owned CPU bytes/guards after actual read_backs, before bottom marker.
3. Actual ordinary Held::Value removal, all=false, exact owned marker read via ReadProcessMemory with full 8-byte receipt, wait holds for new but not old value.
4. B actual completion fence 2 healthy before FINISHED/bury.
5. B full owned CPU bytes/guards after actual read_backs, guest fence still 0.
6. Actual Held::Signal prepublication, guest fence still 0.
7. Final guest fence 17, both outputs correct, marker correct, no held or WAITING residue; final host completion and health.

Observer never takes queue/held/WAITING/submitted locks or re-enters the queue, uses no dynamic collection or tracing while active; fence::completed is atomic, marker read uses a checked kernel byte count, outputs are owned initialized boxes and sole fixture thread. No borrowed HostList across detach or recycle. Abort isolated process rather than unwind on uncertainty after B submission. Fresh allocator/list/queue/fence objects remain alive until known drain.

## Proposed native registration (not authorized yet)

AI1 owns registration after AI2/AI3 exact review and actual builder pins. Prepare with pinned builder in disposable checkout; run `python tools/prepare_ai6_dependent_consumer.py <prepared-checkout>` to verify dry run, then `--apply` only on that isolated tree. Record raw/prepared/fixture/post LF hashes; require exact independently frozen post hashes and no extra modifications. Cargo locked victory-gpu diagnostics debug/release; select exact compiler-artifact test executable and log SHA256. Clean inherited VICTORY_*, RUST_TEST_* and AI6_* environment, set explicit fixture flags:

VICTORY_D3D12_WARP=1, VICTORY_QUEUE_WAIT=1, VICTORY_SPLIT_WAITS=0, VICTORY_CUT_WAITS=0, VICTORY_WAIT_FORCE=0, VICTORY_WAIT_ASK=0, VICTORY_LATE_WAIT=0, VICTORY_ASYNC_SUBMIT=0, VICTORY_JOIN_PARTS=0, VICTORY_ASYNC_PRESENT=0. GPU_TIMING absent, shadow card/relay absent and actual off verified. No default changes.

Exact ignored filter expected `queue::ai6_dependent_consumer::actual_whole_wait_dependent_consumer` (verify with --list --ignored). Run one fresh direct process per profile with --exact --ignored --test-threads=1 --nocapture, bounded external 60s watchdog, preserve partial streams on timeout and no retry. Expect one named ok and one 1 passed/0 failed/0 ignored result; require exactly one matching strict adapter receipt and ordered event receipt with 2 healthy fences, 64/64 active bytes, 48 combined guard bytes, guest fence 17, forced 0, residue 0. No zero-test success. No native CI invocation from this branch.

## Limits

Not compiled or run at creation. No actual prepared output claim for predicted sources or actual fixture postimages yet. Covers one positive legacy synchronous whole wait with owned buffers, not newer ABI, split/cut/join/late/card/relay, arbitrary title memory, texture readback failure, real device removal, error recovery, production behavior, throughput or gameplay FPS. #71 HOLD, existing CPU native 0/28 frozen.
