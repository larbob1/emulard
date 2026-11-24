# Runtime bring-up

The baseline is a pinned public upstream revision, with a local source patch. This project does not contain an independently complete compatibility runtime.

## Milestone 1: synthetic CPU fixture

On Linux with Clang and LLD:

```sh
clang -O2 -Wall -Wextra -Werror probes/abi_smoke.c -o /tmp/abi-native
/tmp/abi-native
clang --target=x86_64-pc-windows-msvc -O2 -ffreestanding -fno-stack-protector -c probes/abi_smoke.c -o /tmp/abi.obj
lld-link /entry:mainCRTStartup /subsystem:console /nodefaultlib /out:abi_smoke.exe /tmp/abi.obj
```

The native arithmetic test returned zero, and the cross-compiled fixture was inspected as an x64 PE32+ console executable with an empty import directory. Execution under Wine is unverified. This fixture tests only basic calling convention and arithmetic, not system services.

## Milestone 2: graphics capability probe

On a Windows build host with a recent Windows SDK and CMake:

```sh
cmake -S probes -B build-probes -A x64
cmake --build build-probes --config Release
ctest --test-dir build-probes -C Release --output-on-failure
```

Run graphics_caps.exe from the resulting Release directory. It checks for a hardware D3D12 device, shader model 6.6, mesh shader support and wave operations. It has not yet been compiled against the Windows SDK or executed. A successful probe is necessary for the intended graphics path but does not establish runtime compatibility.

## Milestone 3: build the patched runtime

```sh
python tools/build_runtime.py ../runtime-checkout
```

On Windows, add --build to test the memory scheduler and build release and diagnostics binaries. The script uses a new detached checkout outside this repository and disables pushing to the source remote. It never copies title assets into this repository. No build of the runtime has yet been verified.

The candidate now also invalidates read scheduling after deferred title-memory writes, while retaining independent write high-water marks. A fourth Rust regression case covers invalidation. Source anchors have been reviewed; full Rust compilation and GPU testing remain outstanding. The change does not solve all GPU ordering or memory lifetime problems.

Keep generated binaries and all diagnostic reports local. Inspect logs before sharing.
