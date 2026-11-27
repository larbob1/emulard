# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile the actual patched stream parser and native fixtures with portable stubs."""
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

PATCH = Path(__file__).resolve().parents[1] / "patches" / "paired-wave-dropped-scene-draws.patch"

def postimages():
    hunks = []
    current = False
    for line in PATCH.read_text(encoding="utf-8").splitlines():
        if line.startswith("--- "):
            current = False
        elif line.startswith("+++ "):
            current = line.endswith("/pipeline.rs")
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
type Shader = (&'static str, Vec<u8>);
fn copy(stage: &'static str, code: &Bytecode) -> Option<Shader> {
    if code.code.is_null() || code.size == 0 { return None; }
    Some((stage, unsafe { std::slice::from_raw_parts(code.code, code.size) }.to_vec()))
}
#[cfg(windows)]
mod host {
    #[derive(Default)]
    pub struct GraphicsState;
    impl GraphicsState {
        pub unsafe fn read(&mut self, _: u32, _: *const u8) {}
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
        self.assertLess(parser.index("if size > remaining"), parser.index("cast::<Bytecode>()"))
        self.assertLess(parser.index("if size > remaining"), parser.index("graphics.read("))

    @unittest.skipUnless(shutil.which("rustc"), "rustc required for portable stream tests")
    def test_compiled_parser_regressions(self):
        images = postimages()
        parser, = [s for s in images if "fn create_stream(" in s]
        fixture, = [s for s in images if "fn stream_result(" in s]
        fixture = fixture.split("    /// The stream layout", 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "stream.rs"
            binary = root / "stream-tests.exe"
            source.write_text(STUBS + parser + "\n#[cfg(test)] mod tests { use super::*;\n"
                              + fixture + "\n}\n", encoding="utf-8")
            subprocess.run(["rustc", "--edition=2021", "--test", str(source), "-o", str(binary)],
                           check=True, capture_output=True, text=True)
            result = subprocess.run([str(binary), "pipeline_stream_"], check=True,
                                    capture_output=True, text=True)
            self.assertIn("5 passed; 0 failed", result.stdout)

if __name__ == "__main__":
    unittest.main()
