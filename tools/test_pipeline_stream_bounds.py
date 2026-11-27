# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile the actual patched stream parser and native fixtures with portable stubs."""
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

PATCH = Path(__file__).resolve().parents[1] / "patches" / "paired-wave-dropped-scene-draws.patch"

def postimages(filename="/pipeline.rs"):
    hunks = []
    current = False
    for line in PATCH.read_text(encoding="utf-8").splitlines():
        if line.startswith("--- "):
            current = False
        elif line.startswith("+++ "):
            current = line.endswith(filename)
        elif current and line.startswith("@@ "):
            match = re.match(r"@@ -(\d+),(\d+) \+(\d+),(\d+) @@", line)
            if not match:
                raise ValueError("invalid hunk header")
            hunks.append((int(match[2]), int(match[4]), []))
        elif current and hunks:
            hunks[-1][2].append(line)
    result = []
    for old, new, lines in hunks:
        if any(not line or line[0] not in " +-" for line in lines):
            raise ValueError("invalid hunk content")
        if sum(line[0] != "+" for line in lines) != old:
            raise ValueError("invalid old count")
        if sum(line[0] != "-" for line in lines) != new:
            raise ValueError("invalid new count")
        result.append("\n".join(line[1:] for line in lines if line[0] != "-") + "\n")
    return result

STUBS = r'''
extern crate self as tracing;
#[macro_export]
macro_rules! warn { ($($tt:tt)*) => {{}} }
type HRESULT = i32;
type This = *const std::ffi::c_void;
type Iid = u32;
const E_INVALIDARG: HRESULT = -1;
const S_OK: HRESULT = 0;
const PIPELINE_IIDS: [Iid; 1] = [0];

#[repr(C)]
struct Bytecode { code: *const u8, size: usize }
#[repr(C)]
struct GraphicsHead { root: This, stages: [Bytecode; 5] }
#[repr(C)]
struct ComputeHead { root: This, stage: Bytecode }
const GRAPHICS_STAGES: [&str; 5] = ["vertex", "pixel", "domain", "hull", "geometry"];
type Shader = (&'static str, Vec<u8>);
// Stub mirrors the process-lifetime interning side effect so the actual
// parser fixture detects copies on a rejected stream. No real shader code.
struct RetainedShader { stage: &'static str, container: Vec<u8> }
static SHADERS: std::sync::Mutex<Option<std::collections::HashMap<Shader, RetainedShader>>> =
    std::sync::Mutex::new(None);
fn copy(stage: &'static str, code: &Bytecode) -> Option<Shader> {
    if code.code.is_null() || code.size == 0 { return None; }
    let bytes = unsafe { std::slice::from_raw_parts(code.code, code.size) }.to_vec();
    SHADERS.lock().unwrap().get_or_insert_with(Default::default)
        .entry((stage, bytes.clone())).or_insert_with(||
            RetainedShader { stage, container: bytes.clone() });
    Some((stage, bytes))
}
#[cfg(windows)]
mod host {
    #[derive(Default)]
    pub struct GraphicsState;
    impl GraphicsState {
        pub unsafe fn read(&mut self, _: u32, _: *const u8) -> bool { true }
    }
}
fn hand_out(shaders: Vec<Shader>,
            #[cfg(windows)] _: Option<Box<host::GraphicsState>>,
            _: *const Iid, out: *mut This) -> HRESULT {
    unsafe { *out = Box::into_raw(Box::new(shaders)).cast(); }
    S_OK
}
fn shaders(p: This) -> Vec<Shader> {
    unsafe { (&*p.cast::<Vec<Shader>>()).clone() }
}
fn release(p: This) -> u32 {
    unsafe { drop(Box::from_raw(p.cast_mut().cast::<Vec<Shader>>())); }
    0
}
'''

class PipelineStreamBoundsTests(unittest.TestCase):
    def test_patch_hunks_and_parser_guards(self):
        parser, = [s for s in postimages() if "fn create_stream(" in s]
        self.assertIn("if remaining < 8", parser)
        self.assertIn("if size > remaining", parser)
        self.assertIn("bytecodes.push((stage, code))", parser)
        self.assertLess(parser.index("graphics.read("), parser.index("filter_map(|(stage, code)| copy"))
        self.assertLess(parser.index("if size > remaining"), parser.index("cast::<Bytecode>()"))
        self.assertLess(parser.index("if size > remaining"), parser.index("graphics.read("))

    def test_nested_layout_guard_wiring(self):
        host, = [x for x in postimages("/pipeline/host.rs") if "fn input_layout_extent_valid" in x]
        parser, = [x for x in postimages() if "fn create_stream(" in x]
        self.assertLess(host.index("if !input_layout_extent_valid"), host.index("std::slice::from_raw_parts"))
        self.assertLess(host.index("SemanticName.0.is_null()"), host.index("CStr::from_ptr"))
        self.assertLess(host.index("if !input_offsets_valid"), host.index("CStr::from_ptr"))
        self.assertLess(host.index("targets.NumRenderTargets as usize >"), host.index("self.targets = targets;"))
        self.assertIn("if !unsafe {\n            graphics.read", parser)
        self.assertIn("return E_INVALIDARG;", parser.split("graphics.read", 1)[1])

    @unittest.skipUnless(shutil.which("rustc"), "rustc required for input layout extent tests")
    def test_actual_nested_layout_arithmetic(self):
        host, = [x for x in postimages("/pipeline/host.rs") if "fn input_layout_extent_valid" in x]
        helper = host[host.index("fn input_layout_extent_valid"):host.index("impl GraphicsState")]
        cases = r'''
#[test]
fn empty_preserves_absence() {
    assert!(input_layout_extent_valid::<u64>(std::ptr::null(), 0));
    assert!(input_layout_extent_valid(1usize as *const u64, 0));
}
#[test]
fn null_and_misalignment_rejected() {
    assert!(!input_layout_extent_valid::<u64>(std::ptr::null(), 1));
    assert!(!input_layout_extent_valid(1usize as *const u64, 1));
}
#[test]
fn overflow_rejected() {
    assert!(!input_layout_extent_valid(8usize as *const u64, usize::MAX));
    assert!(!input_layout_extent_valid(8usize as *const u64, isize::MAX as usize / 8 + 1));
    assert!(!input_layout_extent_valid((usize::MAX & !7) as *const u64, 1));
}
#[test]
fn real_array_accepted() {
    let values = [0u64; 3];
    assert!(input_layout_extent_valid(values.as_ptr(), values.len()));
}
#[test]
fn explicit_append_and_slot_boundaries() {
    assert!(input_offsets_valid([]));
    assert!(input_offsets_valid([(31, 0, 4), (31, u32::MAX, 4), (0, u32::MAX, 8)]));
    assert!(!input_offsets_valid([(32, 0, 4)]));
    assert!(!input_offsets_valid([(u32::MAX, 0, 4)]));
}
#[test]
fn explicit_and_appended_overflows_rejected() {
    assert!(!input_offsets_valid([(0, u32::MAX - 1, 4)]));
    assert!(!input_offsets_valid([(0, u32::MAX - 4, 4), (0, u32::MAX, 4)]));
    assert!(input_offsets_valid([(0, u32::MAX - 4, 4), (1, u32::MAX, 4)]));
    assert!(input_offsets_valid([(0, u32::MAX - 4, 4), (0, 0, 4), (0, u32::MAX, 4)]));
}
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input_layout.rs"
            binary = root / "input-layout-tests.exe"
            source.write_text(helper + cases, encoding="utf-8")
            subprocess.run(["rustc", "--edition=2021", "--test", str(source), "-o", str(binary)],
                           check=True, capture_output=True, text=True)
            result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
            self.assertIn("6 passed; 0 failed", result.stdout)

    @unittest.skipUnless(shutil.which("rustc"), "rustc required for portable stream tests")
    def test_compiled_parser_regressions(self):
        images = postimages()
        parser, = [s for s in images if "fn create_stream(" in s]
        fixture, = [s for s in images if "fn stream_result(" in s]
        plain, = [s for s in images if "fn bytecode_extent_valid(" in s]
        # Compile the exact validator and creator functions, with hand_out/copy stubs.
        validator = plain.split("/// The stage's container", 1)[0]
        creators = plain[plain.index("/// Device method.\npub(crate) extern \"system\" fn create_graphics("):]
        fixture = fixture.split("    /// The stream layout", 1)[0]
        # The real D3D12 nested fixture belongs to native Windows only.
        fixture = fixture[fixture.index("    #[test]\n    fn pipeline_stream_rejected_suffix_does_not_intern_valid_prefix"):]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "stream.rs"
            binary = root / "stream-tests.exe"
            source.write_text(STUBS + validator + creators + parser + "\n#[cfg(test)] mod tests { use super::*;\n"
                              + fixture + "\n}\n", encoding="utf-8")
            subprocess.run(["rustc", "--edition=2021", "--test", str(source), "-o", str(binary)],
                           check=True, capture_output=True, text=True)
            result = subprocess.run([str(binary), "pipeline_stream_"], check=True,
                                    capture_output=True, text=True)
            self.assertIn("9 passed; 0 failed", result.stdout)

if __name__ == "__main__":
    unittest.main()
