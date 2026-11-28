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


# Derived from the exact A native inventory, replacing only the two A names.
# Rust 1.98.1 pretty formatter (5836138644aa) flushes the complete serial
# test-name prefix before run_test (lib.rs 791af5f8ee2a); no empty/partial
# terminal prefix is accepted. This remains a source-derived Windows oracle.
INVENTORIES = {
    False: (221, "e666509a02d3153ce45854ce6b6fc2f72bead213"),
    True: (8, "b76b75a74ac67a1db129498ff3ed8b5e7c726216"),
}
TERMINAL_STATUS = 0xE6000001
NAME = re.compile(rb"[A-Za-z0-9_]+(?:::[A-Za-z0-9_]+)*: test")


def canonical(data):
    require(type(data) is bytes, "raw bytes required")
    if b"\r" in data:
        require(data.count(b"\r\n") == data.count(b"\r") == data.count(b"\n"),
                "noncanonical newline")
        data = data.replace(b"\r\n", b"\n")
    require(all(b == 10 or 32 <= b <= 126 for b in data),
            "noncanonical output byte")
    return data


def inventory_digest(names):
    return hashlib.sha1(b"".join(name + b"\n" for name in sorted(names))).hexdigest()


def parse_inventory(result, expected_count, expected_digest):
    require(type(result.returncode) is int and result.returncode == 0,
            "discovery exit mismatch")
    require(result.stderr == b"", "unexpected discovery stderr")
    lines = canonical(result.stdout).split(b"\n")
    footer = f"{expected_count} tests, 0 benchmarks".encode("ascii")
    require(lines[-3:] == [b"", footer, b""], "discovery footer mismatch")
    rows = lines[:-3]
    require(len(rows) == expected_count and all(NAME.fullmatch(row) for row in rows),
            "discovery record grammar/count mismatch")
    names = {row[:-6] for row in rows}
    require(len(names) == expected_count, "duplicate discovery name")
    require(all((PREFIX + c).encode("ascii") in names for c in ("prearm", "terminal")),
            "missing exact test")
    require(inventory_digest(names) == expected_digest, "discovery identity mismatch")
    return names


def case_prefix(case):
    return f"\nrunning 1 test\ntest {PREFIX}{case} ... ".encode("ascii")


def verify_startup(result, total):
    require(type(result.returncode) is int and result.returncode == 0,
            "startup exit mismatch")
    pattern = (re.escape(case_prefix("prearm")) +
               rb"ok\n\ntest result: ok\. 1 passed; 0 failed; 0 ignored; 0 measured; " +
               str(total - 1).encode("ascii") +
               rb" filtered out; finished in [0-9]+\.[0-9]{2}s\n\n")
    require(re.fullmatch(pattern, canonical(result.stdout)), "startup framing mismatch")
    require(canonical(result.stderr) == STARTUP.encode("ascii") + b"\n",
            "startup receipt mismatch")


def verify_terminal(result, words):
    code = result.returncode
    require(type(code) is int and code in (TERMINAL_STATUS, TERMINAL_STATUS - 2**32),
            "terminal status mismatch")
    require(type(words) is tuple and len(words) == 8 and
            all(type(w) is int for w in words) and words == EXPECTED,
            "terminal receipt mismatch")
    require(canonical(result.stdout) == case_prefix("terminal"),
            "terminal framing mismatch")
    require(result.stderr == b"", "unexpected terminal stderr")
    return TERMINAL_STATUS


def clean_env():
    prefixes = ("VICTORY_", "RUST_TEST_", "AI1_", "AI2_", "AI3_", "AI4_", "AI5_", "AI6_")
    exclude = {"CARGO_TARGET_DIR", "CARGO_BUILD_TARGET_DIR", "RUST_BACKTRACE",
               "RUST_LIB_BACKTRACE", "RUSTFLAGS", "CARGO_ENCODED_RUSTFLAGS"}
    return {k: v for k, v in os.environ.items()
            if not k.upper().startswith(prefixes) and k.upper() not in exclude}


def ordinary(path, directory):
    p = path.absolute()
    require(not p.is_symlink() and not p.is_junction(), "linked path")
    require(p.resolve(strict=True) == p, "noncanonical path")
    for parent in p.parents:
        require(not parent.is_symlink() and not parent.is_junction(), "linked ancestor")
    require(p.is_dir() if directory else p.is_file(), "unexpected path type")
    return p


def digest(path):
    with ordinary(path, False).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def launch(binary, args, env, cwd):
    # Direct child only; communicate drains both pipes, timeout is never success.
    try:
        result = subprocess.run([str(binary), *args], cwd=cwd, env=env,
                                timeout=60, capture_output=True)
    except subprocess.TimeoutExpired as exc:
        print(f"child_timeout stdout={exc.stdout!r} stderr={exc.stderr!r}", flush=True)
        raise
    except OSError as exc:
        print(f"child_launch_failure {exc}", flush=True)
        raise
    print(f"child_observed_exit={result.returncode} stdout={result.stdout!r} "
          f"stderr={result.stderr!r}", flush=True)
    return result


def checked_launch(binary, args, env, cwd, identity):
    require(digest(binary) == identity, "executable changed before launch")
    result = launch(binary, args, env, cwd)
    require(digest(binary) == identity, "executable changed during launch")
    return result


def run_profile(binary, profile, identity, cwd):
    env = clean_env()
    sets = {}
    for ignored, (count, pin) in INVENTORIES.items():
        args = ["--list", "--format", "pretty", "--color", "never"]
        if ignored:
            args.append("--ignored")
        sets[ignored] = parse_inventory(
            checked_launch(binary, args, env, cwd, identity), count, pin)
    require(sets[True] <= sets[False], "ignored discovery inconsistent")
    for case in ("prearm", "terminal"):
        args = [PREFIX + case, "--exact", "--ignored", "--test-threads=1",
                "--format", "pretty", "--color", "never", "--nocapture"]
        if case == "prearm":
            verify_startup(checked_launch(binary, args, env, cwd, identity), 221)
            detail = "exit=0"
        else:
            with receipt() as (name, read):
                result = checked_launch(binary, args, {**env, ENV: name}, cwd, identity)
                words = read()
                status = verify_terminal(result, words)
                detail = f"exit={status:#010x} receipt={words}"
        require(digest(binary) == identity, "executable changed before acceptance")
        print(f"case_accepted profile={profile} case={case} sha256={identity} "
              f"discovered=221 ignored=8 {detail}", flush=True)
    print(f"profile_complete profile={profile} cases=2", flush=True)


def self_check():
    from types import SimpleNamespace
    from unittest.mock import patch

    def result(code, out, err=b""):
        return SimpleNamespace(returncode=code, stdout=out, stderr=err)

    names = {(PREFIX + c).encode("ascii") for c in ("prearm", "terminal")}
    pin = inventory_digest(names)
    inv = b"".join(n + b": test\n" for n in sorted(names)) + b"\n2 tests, 0 benchmarks\n"
    start = (case_prefix("prearm") + b"ok\n\ntest result: ok. 1 passed; 0 failed; "
             b"0 ignored; 0 measured; 220 filtered out; finished in 0.01s\n\n")
    stderr = STARTUP.encode("ascii") + b"\n"
    terminal = case_prefix("terminal")
    good = bad = 0

    def accept(fn, *args):
        nonlocal good
        fn(*args)
        good += 1

    def reject(fn, *args):
        nonlocal bad
        try:
            fn(*args)
        except ValueError:
            bad += 1
            return
        raise AssertionError("negative parser control accepted")

    for newline in (b"\n", b"\r\n"):
        translate = lambda s: s.replace(b"\n", newline)
        accept(parse_inventory, result(0, translate(inv)), 2, pin)
        accept(verify_startup, result(0, translate(start), translate(stderr)), 221)
        for code in (TERMINAL_STATUS, TERMINAL_STATUS - 2**32):
            accept(verify_terminal, result(code, translate(terminal)), EXPECTED)
    for out, err, code in (
        (inv + b"\n", b"", 0), (inv, b"foreign", 0), (inv, b"", 1),
        (inv.replace(b"\n", b"\r"), b"", 0),
        (inv.replace(b"\n", b"\v"), b"", 0),
        (b"foreign\n" + inv, b"", 0),
        (inv.replace(b"actual_terminal", b"actual_prearm"), b"", 0),
        (inv.replace(b"actual_terminal", b"actual_other"), b"", 0),
        (inv + b"2 tests, 0 benchmarks\n", b"", 0),
    ):
        reject(parse_inventory, result(code, out, err), 2, pin)
    reject(parse_inventory, result(0, inv), 2, "0" * 40)
    for out, err, code in (
        (start + b"\n", stderr, 0), (start, stderr + stderr, 0),
        (start, b"prefix " + stderr, 0), (start, stderr, 1),
        (start.replace(b"220 filtered", b"219 filtered"), stderr, 0),
        (start.replace(b"\n", b"\r"), stderr, 0),
        (start.replace(b"ok\n", b"ok \n"), stderr, 0),
        (start.replace(b"\n", b"\r\n", 1), stderr, 0),
        (start + b"\xff", stderr, 0), (start, stderr, False),
    ):
        reject(verify_startup, result(code, out, err), 221)
    for code in (0, 1, -1, TERMINAL_STATUS + 2**32, TERMINAL_STATUS - 2**33,
                 True, float(TERMINAL_STATUS)):
        reject(verify_terminal, result(code, terminal), EXPECTED)
    for out, err in (
        (b"", b""), (terminal[:-1], b""), (terminal + b"ok", b""),
        (terminal + b"\n", b""), (terminal + b"test result: ok", b""),
        (terminal, b"panicked"), (terminal, b"foreign"),
        (terminal, stderr), (terminal.replace(b"\n", b"\r"), b""),
        (terminal.replace(b"\n", b"\v"), b""),
        (case_prefix("prearm"), b""), (terminal + terminal, b""),
    ):
        reject(verify_terminal, result(TERMINAL_STATUS, out, err), EXPECTED)
    for i in range(8):
        words = list(EXPECTED)
        words[i] ^= 1
        reject(verify_terminal, result(TERMINAL_STATUS, terminal), tuple(words))
    with patch(__name__ + ".digest", side_effect=["expected", "different"]), \
            patch(__name__ + ".launch", return_value=result(0, start, stderr)):
        reject(checked_launch, None, [], {}, None, "expected")
    with patch(__name__ + ".digest", return_value="expected"), \
            patch(__name__ + ".launch", side_effect=subprocess.TimeoutExpired("child", 60)):
        try:
            checked_launch(None, [], {}, None, "expected")
        except subprocess.TimeoutExpired:
            bad += 1
        else:
            raise AssertionError("timeout control accepted")
    print(f"parser_controls valid={good} rejected={bad}; not native receipts", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--runtime", type=Path)
    for profile in ("debug", "release"):
        parser.add_argument("--" + profile, type=Path)
        parser.add_argument("--" + profile + "-root", type=Path)
        parser.add_argument("--" + profile + "-sha256")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return
    require(sys.platform == "win32", "Windows required")
    require(all(getattr(args, k) is not None for k in (
        "runtime", "debug", "release", "debug_root", "release_root",
        "debug_sha256", "release_sha256")), "explicit build receipt arguments required")
    cwd = ordinary(args.runtime, True)
    roots = [ordinary(args.debug_root, True), ordinary(args.release_root, True)]
    for i, root in enumerate(roots):
        for other in [cwd, *roots[:i]]:
            require(root != other and root not in other.parents and other not in root.parents,
                    "overlapping build/runtime roots")
    binaries = [ordinary(args.debug, False), ordinary(args.release, False)]
    identities = [args.debug_sha256, args.release_sha256]
    require(identities[0] != identities[1], "identical expected profile hashes")
    require(not binaries[0].samefile(binaries[1]), "aliased binaries")
    for binary, root, identity in zip(binaries, roots, identities):
        require(root in binary.parents, "executable outside build root")
        require(re.fullmatch(r"[0-9a-f]{64}", identity), "invalid expected SHA256")
        require(digest(binary) == identity, "build receipt executable mismatch")
    self_check()
    for profile, binary, identity in zip(("debug", "release"), binaries, identities):
        run_profile(binary, profile, identity, cwd)
    print("runner_complete profiles=2 cases=4", flush=True)


if __name__ == "__main__":
    try:
        main()
    except subprocess.TimeoutExpired:
        sys.exit("FAIL: child timed out")
    except (OSError, ValueError) as exc:
        sys.exit(f"FAIL: {exc}")
