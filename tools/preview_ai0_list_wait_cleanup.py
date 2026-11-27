#!/usr/bin/env python3
"""Pinned raw list.rs cleanup preview; not registered in the runtime builder.

Only the exact raw input is accepted. Writes a new scratch file, never the
input. Review lock ordering and actual prepared source before any port.
"""
import argparse
import hashlib
import json
from pathlib import Path

PIN = "3bf89f3c9b17f14c2ec4fa4480e3378e6ac8857e"
CHANGES = json.loads("[[\"    VALUE_WAITS\\n        .lock()\\n        .unwrap_or_else(|e| e.into_inner())\\n        .retain(|&(list, _)| list != this as usize);\",\"    forget_recorded_waits(this as usize);\"],[\"static VALUE_WAITS: std::sync::Mutex<Vec<(usize, ValueWait)>> = std::sync::Mutex::new(Vec::new());\",\"static VALUE_WAITS: std::sync::Mutex<Vec<(usize, ValueWait)>> = std::sync::Mutex::new(Vec::new());\\n\\nfn forget_recorded_waits(address: usize) {\\n    VALUE_WAITS.lock().unwrap_or_else(|e| e.into_inner())\\n        .retain(|&(list, _)| list != address);\\n}\\n\\nimpl Drop for List {\\n    fn drop(&mut self) {\\n        // Only waits still attached to this recording; detached waits are\\n        // owned by the submission. Never modify another live list's waits.\\n        forget_recorded_waits(std::ptr::from_ref(self) as usize);\\n    }\\n}\\n\"]]")
FIXTURE = Path(__file__).resolve().parent.parent / "probes/list_wait_cleanup_review.rs"
MARKER = "mod ai0_list_wait_cleanup_review"

def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data,
                        usedforsecurity=False).hexdigest()

def preview(data, fixture):
    if git_blob(data) != PIN:
        raise ValueError("unexpected raw blob")
    text = data.decode("utf-8")
    if "impl Drop for List" in text or MARKER in text or fixture.count(MARKER) != 1:
        raise ValueError("unexpected markers")
    for old, new in CHANGES:
        if text.count(old) != 1:
            raise ValueError("unexpected source anchor count")
        text = text.replace(old, new, 1)
    return (text + "\n" + fixture).encode("utf-8")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        result = preview(args.source.read_bytes(), FIXTURE.read_text(encoding="utf-8"))
        with args.output.open("xb") as f:
            f.write(result)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"preview refused: {type(exc).__name__}\n")
    print("List wait cleanup review postimage created; tests not run")

if __name__ == "__main__":
    main()
