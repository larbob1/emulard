# SPDX-License-Identifier: GPL-3.0-or-later
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from preview_ai0_detile_run import START, END, OLD, NEW, FIXTURE, blob, preview, clone_method


class DetileLastRunReview(unittest.TestCase):
    def fixture_source(self):
        return (START + "\n" + OLD + END + "(dummy) {}\n").encode()

    def test_append_only_and_exact_edit(self):
        source = self.fixture_source()
        generated = preview(source, FIXTURE.read_bytes(), blob(source))
        self.assertTrue(generated.startswith(source))
        clone = clone_method(source.decode())
        self.assertEqual(clone.count(NEW), 1)
        self.assertNotIn(OLD, clone)
        self.assertIn("walk_last_inline", clone)
        self.assertEqual(generated.count(b"#[cfg(test)]"), 2)

    def test_refuse_wrong_blob_or_duplicate(self):
        source = self.fixture_source()
        with self.assertRaises(ValueError):
            preview(source, FIXTURE.read_bytes())
        twice = source + source
        with self.assertRaises(ValueError):
            preview(twice, FIXTURE.read_bytes(), blob(twice))

    def test_refuse_anchor_drift(self):
        source = self.fixture_source().replace(OLD.encode(), b"        // changed\n")
        with self.assertRaises(ValueError):
            preview(source, FIXTURE.read_bytes(), blob(source))

    def test_portable_exact_planner_blocks(self):
        rustc = shutil.which("rustc")
        self.assertIsNotNone(rustc, "Rust compiler required for planner parity")
        prefix = """
struct Mip { width: u32 }
struct Layout { offsets: Vec<usize> }
impl Layout {
    fn column(&self, _: &Mip, x: u32) -> u64 { self.offsets[x as usize] as u64 }
"""
        def function(name, block):
            return (
                "fn " + name + "(&self, m: &Mip, n: usize, linear: bool) -> "
                "(Vec<(usize,usize,usize)>,Vec<(usize,usize,usize)>,Option<usize>,usize) {\n"
                "let bytes = m.width as usize * n;\n" + block +
                "(body.to_vec(),last.to_vec(),chunk_size,runs.capacity())\n}\n"
            )
        tests = """
}
#[test]
fn compare_plans() {
    for n in [1,2,4,8,16] {
        for width in 1..=129 {
            for group in [1,2,3,4,7,16,129] {
                let layout = Layout { offsets: (0..width).map(|x| (x + (x/group)*3)*n).collect() };
                let m = Mip { width: width as u32 };
                for linear in [false,true] {
                    let a = layout.old(&m,n,linear);
                    let b = layout.new(&m,n,linear);
                    assert_eq!((&a.0,&a.1,a.2), (&b.0,&b.1,b.2));
                    if !linear && width <= group {
                        assert!(a.3 > 0);
                        assert_eq!(b.3,0);
                    }
                    if linear { assert_eq!(a.3,0); assert_eq!(b.3,0); }
                }
            }
        }
    }
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "planner.rs"
            executable = Path(tmp) / "planner"
            source.write_text(prefix + function("old", OLD) + function("new", NEW) + tests)
            subprocess.run([rustc, "--edition=2021", "--test", str(source), "-o", str(executable)],
                           check=True, timeout=90)
            subprocess.run([str(executable)], check=True, timeout=30)


if __name__ == "__main__":
    unittest.main()
