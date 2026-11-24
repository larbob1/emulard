#!/usr/bin/env bash
# Read-only local probe. No identifiers, paths, serial numbers or uploads.
set -u
export LC_ALL=C
printf '=== Compatibility preflight ===\n'
printf 'Kernel architecture: '; uname -m
if grep -qm1 -w avx2 /proc/cpuinfo 2>/dev/null; then echo 'AVX2: yes'; else echo 'AVX2: not detected'; fi
grep -E '^(MemTotal|MemAvailable|SwapTotal|SwapFree):' /proc/meminfo 2>/dev/null || :
for tool in git python3 cargo rustc wine vulkaninfo nvidia-smi; do
  if command -v "$tool" >/dev/null 2>&1; then printf '%s: available\n' "$tool"; else printf '%s: not found\n' "$tool"; fi
done
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=driver_version,memory.total,memory.free --format=csv,noheader 2>/dev/null || echo 'GPU query failed'
fi
if command -v timeout >/dev/null 2>&1 && command -v vulkaninfo >/dev/null 2>&1; then
  if timeout 20s vulkaninfo --summary >/dev/null 2>&1; then echo 'Vulkan enumeration: passed'; else echo 'Vulkan enumeration: failed or timed out'; fi
fi
echo 'No D3D12 or runtime compatibility has been verified.'
echo 'Review this output locally before sharing.'
