# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated #71 registration-loop parity using actual prepared runtime types.

No submission, title launch, mapping, fault injection, or production installation.
The full ready clone is compiled, not called. The two exact final loop blocks
are exercised with real HostList/Shadow types in a disposable WARP checkout.
"""
import argparse
import ast
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM = "51700c6d43a3507fa65e50fe4bb64074ce706cd4"
PROPOSAL = "036dec4dc4b6a012d2e860e1ae779b67f75719eb"
SCRIPT_PIN = "bf5e1bbfe35de159756cd0dfdc32c65fcef5c68e"
PINS = {
    "memory.rs": "c25636783511fdfbf9692fdd36ef150f69ea666e",
    "host.rs": "458d146aedf6f13dac80782d283a048d80e4a931",
    "shadow.rs": "4fa43df7932bb6692d164384cd28b1f08f3001ee",
}
TEST = "memory::ai1_prefix_registration_review::actual_registration_order"

HOST_HELPER = """
#[cfg(test)]
impl Host {
    pub(crate) fn ai1_prefix_software(&self) -> bool {
        self.adapter.as_ref()
            .and_then(|a| unsafe { a.GetDesc1() }.ok())
            .is_some_and(|d| d.Flags & DXGI_ADAPTER_FLAG_SOFTWARE.0 as u32 != 0)
    }
}

#[cfg(test)]
impl HostList {
    pub(crate) fn ai1_prefix_snapshot(&self)
        -> (Vec<(u8, usize, usize, usize)>, Vec<usize>, bool, bool, usize)
    {
        let d = self.deferred();
        let steps = d.copies.iter().map(|s| match s {
            Step::Refresh(copy, at, len) => (1, std::sync::Arc::as_ptr(copy) as usize, *at, *len),
            Step::GpuWrite(copy, at, len) => (2, std::sync::Arc::as_ptr(copy) as usize, *at, *len),
            Step::Run(_) => (3, 0, 0, 0),
            _ => panic!("unexpected step in isolated registration test"),
        }).collect();
        let kept = d.kept.iter().map(|o| o.as_raw() as usize).collect();
        (steps, kept, d.textures.contains(&(usize::MAX - 0x6d)),
         d.textures.contains(&(usize::MAX - 0x6e)), d.refreshed.len())
    }
}
"""

SHADOW_HELPER = """
#[cfg(test)]
impl Shadow {
    pub(crate) fn ai1_prefix_new(start: u64, len: u64) -> std::sync::Arc<Self> {
        let host = crate::host::host().expect("software host required");
        let (buffer, data) = host.shared_buffer(len).expect("test buffer");
        let gpu = unsafe { buffer.GetGPUVirtualAddress() };
        std::sync::Arc::new(Self::new(buffer, data, gpu, start, len))
    }
}
"""

FIXTURE = """
#[cfg(all(test, feature = "diagnostics"))]
mod ai1_prefix_registration_review {
    use super::*;
    use windows::core::Interface;

    fn event(kind: u8, copy: &Arc<Shadow>) -> (u8, usize, usize, usize) {
        let (at, len) = copy.span();
        (kind, Arc::as_ptr(copy) as usize, at as usize, len as usize)
    }

    #[test]
    fn actual_registration_order() {
        assert_eq!(std::env::var("VICTORY_D3D12_WARP").as_deref(), Ok("1"));
        let host = host().expect("WARP host is mandatory");
        assert!(host.ai1_prefix_software(), "not the software adapter");
        let make = || {
            let (buffer, data) = host.shared_buffer(PAGE).expect("owned test buffer");
            let gpu = unsafe { buffer.GetGPUVirtualAddress() };
            (buffer, data.cast::<u32>(), gpu)
        };
        // These resources and their dummy address spans are used only for
        // recording and reference inspection. No GPU work is submitted.
        let mut m = Memory {
            directory: make(), faults: make(),
            copies: vec![Shadow::ai1_prefix_new(PAGE, PAGE),
                         Shadow::ai1_prefix_new(2 * PAGE, PAGE)],
            heaps: Default::default(), frame: 0, refused: Default::default(),
        };
        let a = host.new_list().expect("baseline list");
        let b = host.new_list().expect("candidate list");
        let kept = vec![
            m.directory.0.cast::<windows::core::IUnknown>().unwrap().as_raw() as usize,
            m.faults.0.cast::<windows::core::IUnknown>().unwrap().as_raw() as usize,
        ];
        let check = |m: &Memory, numbered, writes, expected: &Vec<_>,
                     first_write, refreshed| {
            baseline(m, &a, numbered, writes);
            candidate(m, &b, numbered, writes);
            let want = (expected.clone(), kept.clone(), true, first_write, refreshed);
            assert_eq!(a.ai1_prefix_snapshot(), want);
            assert_eq!(b.ai1_prefix_snapshot(), want);
        };
        let mut expected = vec![event(1, &m.copies[0]), event(1, &m.copies[1])];
        check(&m, 2, false, &expected, false, 2);
        check(&m, 2, false, &expected, false, 2);
        expected.extend([event(2, &m.copies[0]), event(2, &m.copies[1])]);
        check(&m, 2, true, &expected, true, 2);
        m.copies.push(Shadow::ai1_prefix_new(3 * PAGE, PAGE));
        expected.extend([event(1, &m.copies[2]), event(2, &m.copies[2])]);
        check(&m, 2, true, &expected, true, 3);
        // Existing first-use behavior is preserved even after a deferred
        // operation clears the per-range refresh set. Never execute it.
        a.defer(|| {});
        b.defer(|| {});
        expected.push((3, 0, 0, 0));
        check(&m, 3, true, &expected, true, 0);
        for copy in &m.copies {
            assert_eq!(Arc::strong_count(copy), 5);
        }
        // Reset only closed, never-submitted lists; no in-flight work.
        unsafe {
            a.list.Close().expect("close baseline");
            b.list.Close().expect("close candidate");
        }
        a.reset();
        b.reset();
        assert_eq!(a.ai1_prefix_snapshot(), (vec![], vec![], false, false, 0));
        assert_eq!(b.ai1_prefix_snapshot(), (vec![], vec![], false, false, 0));
        for copy in &m.copies {
            assert_eq!(Arc::strong_count(copy), 1);
        }
        expected = m.copies.iter().flat_map(|copy| [event(1, copy), event(2, copy)]).collect();
        check(&m, 3, true, &expected, true, 3);
        unsafe {
            a.list.Close().expect("close baseline");
            b.list.Close().expect("close candidate");
        }
        drop(a);
        drop(b);
        for copy in &m.copies {
            assert_eq!(Arc::strong_count(copy), 1);
        }
    }
}
"""

def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def normalize(data):
    data = data.replace(b"\r\n", b"\n")
    if b"\r" in data:
        raise ValueError("invalid source line endings")
    return data

def exact_blocks(script):
    if blob(script) != SCRIPT_PIN:
        raise ValueError("proposal preview pin mismatch")
    values = {}
    for node in ast.parse(script).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in ("START", "OLD", "NEW"):
                if target.id in values:
                    raise ValueError("duplicate proposal constant")
                values[target.id] = ast.literal_eval(node.value)
    if set(values) != {"START", "OLD", "NEW"} or not all(isinstance(v, str) for v in values.values()):
        raise ValueError("proposal constants missing")
    return values

def git(cwd, *args):
    return subprocess.check_output(["git", *args], cwd=cwd)

def append(path, suffix):
    raw = path.read_bytes()
    if b"\r\n" in raw:
        if b"\n" in raw.replace(b"\r\n", b""):
            raise ValueError("mixed source line endings")
        suffix = suffix.replace("\n", "\r\n")
    path.write_bytes(raw + suffix.encode())

def prepare(target, proposal):
    if git(proposal, "rev-parse", "HEAD").decode().strip() != PROPOSAL:
        raise ValueError("proposal checkout mismatch")
    # Read canonical Git bytes, not a Windows checkout with CRLF conversion.
    script = git(proposal, "show", "HEAD:tools/preview_ai0_ready_copy_prefix.py")
    values = exact_blocks(script)
    print(f"proposal={PROPOSAL} preview_blob={blob(script)}", flush=True)
    subprocess.run([sys.executable, str(ROOT / "tools/build_runtime.py"), str(target),
                    "--paired-wave-refresh"], check=True)
    if git(target, "rev-parse", "HEAD").decode().strip() != UPSTREAM:
        raise ValueError("upstream checkout mismatch")
    source_dir = target / "crates/victory-gpu/src"
    raw = {}
    prepared = {}
    for name, pin in PINS.items():
        raw[name] = git(target, "show", "HEAD:crates/victory-gpu/src/" + name)
        if blob(raw[name]) != pin:
            raise ValueError("raw source pin mismatch: " + name)
        prepared[name] = normalize((source_dir / name).read_bytes())
        print(f"{name} raw={pin} prepared_lf={blob(prepared[name])}", flush=True)
    if prepared["memory.rs"] != raw["memory.rs"]:
        raise ValueError("prepared memory source differs from exact reviewed source")
    source = prepared["memory.rs"].decode()
    start, old, new = (values[k] for k in ("START", "OLD", "NEW"))
    if source.count(start) != 1 or source.count(old) != 1 or "ready_skip_prefix" in source:
        raise ValueError("ready clone anchors mismatch")
    method = source[source.index(start):]
    if not method.endswith("}\n") or method.count(old) != 1:
        raise ValueError("ready clone boundary mismatch")
    clone = method.replace(start, "fn ready_skip_prefix(\n", 1).replace(old, new, 1)
    # Use the original and candidate exact blocks, without replacing the
    # production function. The whole candidate also compiles in test mode.
    def loop(name, block):
        return f"\n#[cfg(test)]\nfn {name}(m: &Memory, list: &HostList, numbered: usize, writes: bool) {{\n" + block + "}\n"
    fixture = FIXTURE.replace("mod ai1_prefix_registration_review {\n    use super::*;",
        "mod ai1_prefix_registration_review {\n    use super::*;")
    append(source_dir / "memory.rs", "\n#[cfg(test)]\n" + clone +
           loop("baseline", old) + loop("candidate", new) + fixture)
    append(source_dir / "host.rs", "\n" + HOST_HELPER)
    append(source_dir / "shadow.rs", "\n" + SHADOW_HELPER)
    for name in PINS:
        print(f"{name} test_postimage_lf={blob(normalize((source_dir/name).read_bytes()))}", flush=True)
    subprocess.run(["git", "diff", "--check"], cwd=target, check=True)

def run_exact(target, release):
    args = ["cargo", "test", "--locked", "-p", "victory-gpu", "--lib", "--features", "diagnostics"]
    if release:
        args.append("--release")
    args.extend([TEST, "--", "--exact", "--test-threads=1"])
    env = dict(os.environ, VICTORY_D3D12_WARP="1")
    result = subprocess.run(args, cwd=target, env=env, capture_output=True,
                            text=True, errors="replace", timeout=3600)
    output = result.stdout
    lines = [line for line in output.splitlines() if line.strip()]
    expected = f"test {TEST} ... ok"
    summary = r"test result: ok\. 1 passed; 0 failed; 0 ignored; 0 measured; \d+ filtered out; finished in \d+(?:\.\d+)?s"
    if (result.returncode != 0 or lines.count(expected) != 1
            or len([l for l in lines if l.startswith("test result:")]) != 1
            or not any(re.fullmatch(summary, l) for l in lines)):
        # Compiler/test diagnostics are public scratch source only, never
        # title data. Bound log length to preserve an actionable failure.
        print((result.stderr + "\n" + output)[-12000:], flush=True)
        raise ValueError("missing exact registration test receipt")
    print(("release" if release else "debug") + " diagnostics " + expected, flush=True)
    print(next(l for l in lines if l.startswith("test result:")), flush=True)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--proposal", type=Path, required=True)
    a = p.parse_args()
    if os.name != "nt":
        raise SystemExit("Windows WARP required")
    with tempfile.TemporaryDirectory(prefix="ai1-ready-prefix-") as tmp:
        target = Path(tmp) / "runtime"
        prepare(target, a.proposal.resolve())
        run_exact(target, False)
        run_exact(target, True)
    print("Registration-loop parity only; no mapping/submission or gameplay acceptance")

if __name__ == "__main__":
    main()
