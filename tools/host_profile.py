#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only Linux process resource sampler; no raw identifiers exported."""
import argparse
import json
import os
import re
from pathlib import Path
import sys
import time

NS = 1_000_000_000
MAX_THREADS = 4096
# Linux procfs reports these fields in kB (1024 bytes). Keep only the
# explicit numeric allowlist; status also contains private identifiers.
PROCESS_MEMORY = {
    "VmRSS": "process_status_rss_bytes",
    "RssAnon": "process_anon_rss_bytes",
    "RssFile": "process_file_rss_bytes",
    "RssShmem": "process_shmem_rss_bytes",
    "VmSwap": "process_anon_swap_bytes",
    "VmSize": "process_virtual_bytes",
    "VmHWM": "process_status_rss_highwater_bytes",
}
SYSTEM_MEMORY = {
    "MemTotal": "system_total_bytes",
    "MemAvailable": "system_available_bytes",
    "SwapTotal": "system_swap_total_bytes",
    "SwapFree": "system_swap_free_bytes",
}
MEMORY_FIELDS = tuple(PROCESS_MEMORY.values()) + tuple(SYSTEM_MEMORY.values())


def parse_memory(text, fields):
    values = {}
    seen = set()
    for line in text.splitlines():
        key, sep, raw = line.partition(":")
        if not sep or key not in fields:
            continue
        name = fields[key]
        if key in seen:
            values[name] = None
            continue
        seen.add(key)
        m = re.fullmatch(r"\s*([0-9]{1,17})\s+kB\s*", raw)
        n = int(m[1]) * 1024 if m else None
        values[name] = n if n is not None and n <= 2**64 - 1 else None
    return {name: values.get(name) for name in fields.values()}


def read_memory(path, fields):
    try:
        return parse_memory(path.read_text(errors="replace"), fields)
    except OSError:
        return dict.fromkeys(fields.values())


def parse_stat(text):
    # comm can contain spaces, parentheses and newlines. The last ')' is
    # the delimiter, not the first. Never return comm or the PID.
    end = text.rfind(")")
    if end < 0:
        raise ValueError("invalid process stat")
    fields = text[end + 1:].split()
    if len(fields) < 22:
        raise ValueError("short process stat")
    user, system, birth, rss = (int(fields[i]) for i in (11, 12, 19, 21))
    if min(user, system, birth) < 0:
        raise ValueError("invalid process counters")
    return birth, user + system, max(0, rss)


def parse_io(text):
    found = {}
    for line in text.splitlines():
        key, sep, value = line.partition(":")
        if key in ("read_bytes", "write_bytes") and sep:
            if key in found:
                raise ValueError("duplicate I/O field")
            found[key] = int(value.strip())
    if len(found) != 2 or min(found.values()) < 0:
        raise ValueError("invalid I/O counters")
    return found


def read_snapshot(root, pid, clock=time.monotonic_ns):
    proc = root / str(pid)
    before = clock()
    birth, ticks, rss = parse_stat((proc / "stat").read_text(errors="replace"))
    stat_after = clock()
    io = None
    try:
        io = parse_io((proc / "io").read_text(errors="replace"))
    except (OSError, ValueError):
        pass
    # Cheap status/meminfo counters, not a page-table walk or smaps scan.
    # The values are sequentially sampled within the stat identity bracket;
    # they need not match the earlier stat RSS exactly.
    memory = read_memory(proc / "status", PROCESS_MEMORY)
    memory.update(read_memory(root / "meminfo", SYSTEM_MEMORY))
    threads = {}
    incomplete = False
    try:
        tasks = list((proc / "task").iterdir())
        if len(tasks) > MAX_THREADS:
            incomplete = True
            tasks = []
        for entry in tasks:
            if not entry.name.isdecimal():
                continue
            try:
                tbirth, tticks, _ = parse_stat((entry / "stat").read_text(errors="replace"))
                threads[(entry.name, tbirth)] = tticks
            except (OSError, ValueError):
                incomplete = True
    except OSError:
        incomplete = True
    # Detect reuse while reading optional files; process totals are sampled
    # at the first read, not at the later identity check.
    after_birth, _, _ = parse_stat((proc / "stat").read_text(errors="replace"))
    after = clock()
    if birth != after_birth:
        raise ValueError("process identity changed")
    return {"birth": birth, "ticks": ticks, "rss_pages": rss, "io": io,
            "threads": threads, "threads_incomplete": incomplete,
            "memory": memory,
            "time_ns": (before + stat_after) // 2, "read_ns": after - before}


def interval(a, b, hz, page_size):
    if a["birth"] != b["birth"]:
        raise ValueError("process identity changed")
    elapsed_ns = b["time_ns"] - a["time_ns"]
    if elapsed_ns <= 0 or b["ticks"] < a["ticks"]:
        raise ValueError("invalid elapsed time or CPU counter reset")
    seconds = elapsed_ns / NS
    cpu_seconds = (b["ticks"] - a["ticks"]) / hz
    stable = set(a["threads"]) & set(b["threads"])
    thread_deltas = [b["threads"][key] - a["threads"][key] for key in stable]
    # Per-thread observations do not exactly coincide with process stat;
    # report only stable endpoints and never infer missing work.
    thread_valid = (bool(stable) and not a["threads_incomplete"]
                    and not b["threads_incomplete"] and min(thread_deltas) >= 0)
    io = None
    if a["io"] is not None and b["io"] is not None:
        deltas = {key: b["io"][key] - a["io"][key] for key in a["io"]}
        if min(deltas.values()) >= 0:
            io = deltas
    return {
        "elapsed_seconds": seconds,
        "cpu_seconds": cpu_seconds,
        "cpu_core_equivalents": cpu_seconds / seconds,
        "rss_end_bytes": b["rss_pages"] * page_size,
        "memory_end": {name: b.get("memory", {}).get(name) for name in MEMORY_FIELDS},
        "read_bytes": io["read_bytes"] if io is not None else None,
        "write_bytes": io["write_bytes"] if io is not None else None,
        "stable_threads": len(stable),
        "thread_count_start_observed": len(a["threads"]),
        "thread_count_end_observed": len(b["threads"]),
        "stable_thread_metrics_available": thread_valid,
        "thread_endpoint_sets_match": (not a["threads_incomplete"] and not b["threads_incomplete"]
                                       and set(a["threads"]) == set(b["threads"])),
        "hottest_stable_thread_core_equivalents": (
            max(thread_deltas) / hz / seconds if thread_valid else None),
        "snapshot_read_seconds_max": max(a["read_ns"], b["read_ns"]) / NS,
    }


def memory_observations(rows):
    result = {}
    for field in MEMORY_FIELDS:
        observations = [(i + 1, row.get("memory_end", {}).get(field))
                        for i, row in enumerate(rows)]
        observed = [(i, v) for i, v in observations if v is not None]
        result[field] = {
            "observed_endpoints": len(observed),
            "first_observed_interval": observed[0][0] if observed else None,
            "last_observed_interval": observed[-1][0] if observed else None,
            "first_observed_bytes": observed[0][1] if observed else None,
            "last_observed_bytes": observed[-1][1] if observed else None,
            "min_observed_bytes": min((v for _, v in observed), default=None),
            "max_observed_bytes": max((v for _, v in observed), default=None),
        }
    return result


def summarize(rows, requested, stop_reason=None):
    elapsed = sum(r["elapsed_seconds"] for r in rows)
    cpu = sum(r["cpu_seconds"] for r in rows)
    io_rows = [r for r in rows if r["read_bytes"] is not None]
    io_seconds = sum(r["elapsed_seconds"] for r in io_rows)
    thread_rows = [r for r in rows if r["stable_thread_metrics_available"]]
    return {
        "requested_intervals": requested,
        "completed_intervals": len(rows),
        "complete": len(rows) == requested and stop_reason is None,
        "stop_reason": stop_reason,
        "elapsed_seconds": elapsed,
        "mean_cpu_core_equivalents": cpu / elapsed if elapsed else None,
        "peak_interval_cpu_core_equivalents": max((r["cpu_core_equivalents"] for r in rows), default=None),
        "peak_sampled_rss_bytes": max((r["rss_end_bytes"] for r in rows), default=None),
        "memory_observations": memory_observations(rows),
        "memory_note": "Optional status and system meminfo fields at interval-end snapshots, sequential reads not atomic with stat or each other. First observed endpoint is not the initial snapshot. Missing fields remain null. RSS classes may include shared physical pages; VmSize is virtual address space, VmSwap excludes some shared memory swap, VmHWM is kernel-reported lifetime high-water. System available memory is a kernel estimate, not process ownership. No sums, allocation or leak attribution, GPU VRAM, or guard enforcement.",
        "io_observed_intervals": len(io_rows),
        "io_observed_seconds": io_seconds,
        "mean_observed_read_bytes_per_second": sum(r["read_bytes"] for r in io_rows) / io_seconds if io_seconds else None,
        "mean_observed_write_bytes_per_second": sum(r["write_bytes"] for r in io_rows) / io_seconds if io_seconds else None,
        "thread_observed_intervals": len(thread_rows),
        "peak_hottest_stable_thread_core_equivalents": max(
            (r["hottest_stable_thread_core_equivalents"] for r in thread_rows), default=None),
        "intervals": rows,
        "note": "One selected Linux process only. One CPU core equivalent is one CPU-second per elapsed second; not machine utilization. RSS includes shared pages, not VRAM or private allocation. I/O is kernel-accounted bytes, not title throughput or queue starvation. Stable threads omit churn and sampling is non-atomic. Snapshot overhead is reported; no GPU, frame, lock, or causal critical-path evidence. Other Proton/Wine processes excluded. IDs, names and paths not exported.",
    }


def sample(pid, count, period, root=Path("/proc"), sleeper=time.sleep,
           reader=read_snapshot, hz=None, page_size=None):
    if not 1 <= pid or not 1 <= count <= 3600 or not 0.25 <= period <= 60:
        raise ValueError("invalid sampling arguments")
    hz = os.sysconf("SC_CLK_TCK") if hz is None else hz
    page_size = os.sysconf("SC_PAGE_SIZE") if page_size is None else page_size
    if hz <= 0 or page_size <= 0:
        raise ValueError("invalid host units")
    rows = []
    reason = None
    try:
        prev = reader(root, pid)
        for _ in range(count):
            sleeper(period)
            current = reader(root, pid)
            rows.append(interval(prev, current, hz, page_size))
            prev = current
    except KeyboardInterrupt:
        reason = "interrupted"
    except OSError:
        reason = "process_unavailable"
    except ValueError:
        reason = "invalid_or_changed_process"
    return summarize(rows, count, reason)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pid", type=int, help="existing runtime process ID")
    parser.add_argument("--intervals", type=int, default=60)
    parser.add_argument("--period", type=float, default=1.0, help="sleep seconds between snapshots")
    args = parser.parse_args()
    if not sys.platform.startswith("linux"):
        parser.error("Linux only")
    try:
        report = sample(args.pid, args.intervals, args.period)
    except (ValueError, OSError):
        print(json.dumps({"status": "invalid_sampling_configuration"}))
        return 1
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
