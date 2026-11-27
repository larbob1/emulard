# Host resource profiling on Linux/Proton (P18)

Use the already working executable and prefix; do not change the runtime for
this measurement. The read-only Linux sampler needs only Python 3 and ordinary
permission to read the selected process's /proc files. No root, launch wrapper,
new dependencies or runtime flags are required. Use a separate terminal.

1. Start the known-working runtime normally, reach the reference scene and
   allow warmup. Identify its actual Linux PID in your process monitor (not
   Steam, a launcher or wineserver). Do not share process names/command lines.
2. While running the same steady scene, substitute that PID:

       python3 tools/host_profile.py 12345 --intervals 60 --period 1 > host-baseline.json

   The period is a sleep between snapshots; elapsed time is measured, not
   assumed. Align this capture with the gameplay log window as closely as
   possible. Repeat on the exact same executable with one experiment changed
   after native validation and owner approval. If the process exits or is
   replaced, the tool stops and reports partial coverage. Do not combine
   partial captures with complete captures as equivalent evidence.
3. Review numeric JSON before sharing. Pair with frame_report.py, visual
   correctness and driver/Proton/build metadata. Capture GPU utilization,
   GPU memory and system-wide pressure separately using the existing system
   monitor; this sampler cannot measure those.

## Interpret

- CPU core equivalents = consumed process CPU seconds / observed wall
  seconds. 1.0 is one fully busy logical CPU on average; 4.0 is four, not
  4% or 400% of the entire machine. A lightly loaded process can be blocked
  waiting for GPU, locks, I/O or other processes; this does not prove which.
- Hottest stable thread is sampled only for threads observed at both endpoints
  with the same birth identity. Thread churn, non-atomic reads and scheduling
  granularity limit accuracy; values may slightly exceed one because endpoints
  differ. Do not infer CPU critical path or contention from a busy thread alone.
- RSS is sampled resident memory including shared pages, not unique physical
  allocation, GPU memory, or a peak between samples.
- Kernel-accounted read/write bytes are not storage request throughput,
  cache-hit rate or queue starvation. Missing access or counter resets omit
  affected I/O intervals; denominator covers only observed intervals.
- This is one Linux process, excluding other Wine/Proton processes and drivers.
  Overhead varies with thread count and appears in snapshot_read_seconds_max.
  Compare sampler off/on before attributing small changes. No timestamp-to-frame
  correlation or synchronized GPU measurements are implied. Stop on correctness
  regression; no change to process priority or scheduling is made.

Exit 0 = all requested intervals collected, 1 = invalid configuration, 2 =
partial or unavailable observation. No PID, thread ID, path or process name is
exported. A process with the same PID and same start tick is theoretically
indistinguishable; the identity check is best effort, not a kernel pidfd.
Synthetic tests cover parser and sampling arithmetic; actual Proton measurements
are still required. Do not upload raw logs, proprietary content or profiles.
