# SPDX-License-Identifier: GPL-3.0-or-later
"""Extracted copy-block parity; actual component conversion remains a native gate."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from preview_ai0_rect_copy import START, END, OLD, NEW, FIXTURE, blob, clone, preview


class RectCopyReview(unittest.TestCase):
    def source(self):
        return (START + ") {\n" + OLD + END + "\nenum Kind {}\n").encode()

    def test_append_only_exact_clone(self):
        src = self.source()
        result = preview(src, FIXTURE.read_bytes(), blob(src))
        self.assertTrue(result.startswith(src))
        generated = clone(src.decode())
        self.assertIn(NEW, generated)
        self.assertNotIn(OLD, generated)
        self.assertEqual(result.count(b"#[cfg(test)]"), 2)

    def test_pin_anchor_and_fixture_refusal(self):
        src = self.source()
        with self.assertRaises(ValueError):
            preview(src, FIXTURE.read_bytes())
        for changed in (src + src, src.replace(OLD.encode(), b"// drift\n")):
            with self.assertRaises(ValueError):
                preview(changed, FIXTURE.read_bytes(), blob(changed))
        with self.assertRaises(ValueError):
            preview(src, b"bad fixture", blob(src))

    def test_portable_copy_blocks(self):
        rustc = shutil.which("rustc")
        self.assertIsNotNone(rustc, "Rust compiler required")
        def function(name, block):
            return (
                "fn " + name + "(src: &[u8], dst: &mut [u8], stride: usize) {\n"
                "for (rect,out) in src.chunks_exact(3*stride).zip(dst.chunks_exact_mut(6*stride)) {\n"
                "let v = |i:usize| &rect[i*stride..(i+1)*stride];\n" + block +
                "out[5*stride..].copy_from_slice(v(0));\n}\n}\n"
            )
        tests = """
#[test]
fn copy_blocks_match_oracle_and_preserve_tails() {
    for stride in 1usize..=128 {
        for rects in [0usize,1,2,7] {
            for src_tail in [0,stride-1,3*stride-1] {
                let src:Vec<u8> = (0..3*stride*rects+src_tail)
                    .map(|i| (i.wrapping_mul(37)^ (i>>8)) as u8).collect();
                for dst_rects in [0,rects.saturating_sub(1),rects,rects+1] {
                    for dst_tail in [0,6*stride-1] {
                        let mut a = vec![0xcd; 6*stride*dst_rects+dst_tail];
                        let mut b = a.clone();
                        let mut expected = a.clone();
                        for r in 0..rects.min(dst_rects) {
                            for (slot,original) in [0,1,2,0,2,0].into_iter().enumerate() {
                                let at = (r*3+original)*stride;
                                let to = (r*6+slot)*stride;
                                expected[to..to+stride].copy_from_slice(&src[at..at+stride]);
                            }
                        }
                        old(&src,&mut a,stride);
                        new(&src,&mut b,stride);
                        assert_eq!(a,expected);
                        assert_eq!(b,expected);
                    }
                }
            }
        }
    }
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "rect.rs"
            exe = Path(tmp) / "rect"
            src.write_text(function("old", OLD) + function("new", NEW) + tests)
            subprocess.run([rustc, "--edition=2021", "--test", str(src), "-o", str(exe)],
                           check=True, timeout=90)
            subprocess.run([str(exe)], check=True, timeout=30)


if __name__ == "__main__":
    unittest.main()
