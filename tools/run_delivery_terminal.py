# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the two ignored AI6 tests in each of two prepared Windows test binaries."""
import argparse
import contextlib
import ctypes
import hashlib
import os
from pathlib import Path
import re
import secrets
import struct
import subprocess
import sys

PREFIX = "delivery_terminal::ai6_delivery_terminal_native::actual_"
ENV = "AI6_TERMINAL_RECEIPT_NAME"
MAGIC = 0x41364254
EXPECTED = (MAGIC, 1, 1, 4, 0x434F4D54, 0, 0, 0)
STARTUP = "ai6_terminal_startup same=1 armed=1 reason=0 wake_failed=0 park_failed=0"


def require(condition, message):
    if not condition:
        raise ValueError(message)


@contextlib.contextmanager
def receipt():
    from ctypes import wintypes as w
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)

    def api(name, result, *args):
        func = getattr(kernel, name)
        func.restype = result
        func.argtypes = args
        return func

    create = api("CreateFileMappingW", w.HANDLE, w.HANDLE, w.LPVOID,
                 w.DWORD, w.DWORD, w.DWORD, w.LPCWSTR)
    view = api("MapViewOfFile", w.LPVOID, w.HANDLE, w.DWORD, w.DWORD,
               w.DWORD, ctypes.c_size_t)
    unmap = api("UnmapViewOfFile", w.BOOL, w.LPVOID)
    close = api("CloseHandle", w.BOOL, w.HANDLE)
    name = "Local\\ai6-terminal-" + secrets.token_hex(24)
    ctypes.set_last_error(0)
    handle = create(w.HANDLE(-1), None, 4, 0, 32, name)
    error = ctypes.get_last_error()
    if not handle:
        raise ctypes.WinError(error)
    try:
        require(error != 183, "receipt name collision")
        address = view(handle, 2, 0, 0, 32)
        if not address:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            ctypes.memmove(address, struct.pack("<8I", MAGIC, *([0] * 7)), 32)
            yield name, lambda: struct.unpack("<8I", ctypes.string_at(address, 32))
        finally:
            unmap(address)
    finally:
        close(handle)


def launch(binary, args, env):
    # communicate() drains both pipes. run() kills and waits on timeout.
    return subprocess.run([str(binary), *args], env=env, timeout=60,
                          capture_output=True, text=True, errors="strict")


def inventory(binary, env, ignored):
    args = ["--list", "--format", "pretty"]
    if ignored:
        args.append("--ignored")
    result = launch(binary, args, env)
    require(result.returncode == 0, "discovery failed")
    lines = result.stdout.splitlines()
    names = [line[:-6] for line in lines if line.endswith(": test")]
    require(len(set(names)) == len(names), "duplicate discovery name")
    require(f"{len(names)} tests, 0 benchmarks" in lines, "discovery count mismatch")
    for case in ("prearm", "terminal"):
        require(PREFIX + case in names, "missing exact test " + case)
    return set(names)


def verify_startup(result, total):
    require(result.returncode == 0, f"startup exit {result.returncode}")
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    require(len(lines) == 3 and lines[:2] == [
        "running 1 test", f"test {PREFIX}prearm ... ok"
    ], "unexpected startup framing")
    pattern = (rf"test result: ok\. 1 passed; 0 failed; 0 ignored; 0 measured; "
               rf"{total - 1} filtered out; finished in [0-9]+(?:\.[0-9]+)?s")
    require(re.fullmatch(pattern, lines[2]), "startup result/count mismatch")
    require(result.stderr.splitlines() == [STARTUP], "startup receipt mismatch")


def verify_terminal(result, words):
    require(result.returncode & 0xffffffff == 0xE6000001,
            f"unexpected terminal exit {result.returncode}")
    require(words == EXPECTED, f"terminal receipt mismatch {words!r}")
    require("test result:" not in result.stdout and "panicked" not in result.stderr,
            "contradictory terminal framing")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run_profile(binary, profile, identity):
    env = os.environ.copy()
    env.pop(ENV, None)
    all_tests = inventory(binary, env, False)
    ignored = inventory(binary, env, True)
    require(ignored <= all_tests, "ignored discovery inconsistent")
    for case in ("prearm", "terminal"):
        require(digest(binary) == identity, "executable changed before case")
        args = [PREFIX + case, "--exact", "--ignored", "--test-threads=1",
                "--format", "pretty", "--nocapture"]
        if case == "prearm":
            verify_startup(launch(binary, args, env), len(all_tests))
        else:
            with receipt() as (name, read):
                result = launch(binary, args, {**env, ENV: name})
                words = read()
                verify_terminal(result, words)
                print(f"{profile} terminal observed_exit={result.returncode & 0xffffffff:#010x} "
                      f"receipt={words}", flush=True)
        require(digest(binary) == identity, "executable changed during case")
        print(f"{profile} {case} passed sha256={identity} "
              f"discovered={len(all_tests)} ignored={len(ignored)}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--debug", required=True, type=Path)
    parser.add_argument("--release", required=True, type=Path)
    args = parser.parse_args()
    require(sys.platform == "win32", "Windows required")
    binaries = [path.resolve(strict=True) for path in (args.debug, args.release)]
    identities = [digest(path) for path in binaries]
    require(identities[0] != identities[1], "identical debug/release binaries")
    for profile, path, identity in zip(("debug", "release"), binaries, identities):
        run_profile(path, profile, identity)


if __name__ == "__main__":
    try:
        main()
    except subprocess.TimeoutExpired:
        sys.exit("FAIL: child timed out")
    except (OSError, ValueError) as exc:
        sys.exit(f"FAIL: {exc}")
