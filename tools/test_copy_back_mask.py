# SPDX-License-Identifier: GPL-3.0-or-later
"""Run actual prepared copy-back function against independent byte-level oracle."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from apply_gpu_copy_perf import REPLACEMENTS


class CopyBackMaskTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("rustc"), "rustc required for portable copy-back tests")
    def test_actual_copy_back_matrix(self):
        def find(prefix):
            new, = [new for old, new in REPLACEMENTS if old.startswith(prefix)]
            return new

        merge = find("fn merge_piece(")
        # Only the real configuration switch is needed, not other merge code.
        sparse = "fn sparse_merge_on()" + merge.split("fn sparse_merge_on()", 1)[1].split("// Compare completed", 1)[0]
        source_text = ("const DIFF_CHUNK: usize = 32;\n" + sparse
                       + find("fn first_difference(") + find("fn last_difference(")
                       + find("fn back_piece("))
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            source = root / "copy_back.rs"
            binary = root / "copy-back-tests.exe"
            source.write_text(source_text, encoding="utf-8")
            subprocess.run(["rustc", "--edition=2021", "--test", str(source), "-o", str(binary)],
                           check=True, capture_output=True, text=True)
            for sparse_mode, avx_mode in [("0", "0"), ("1", "0"), ("0", "1"), ("1", "1")]:
                with self.subTest(sparse=sparse_mode, avx=avx_mode):
                    env = dict(os.environ, VICTORY_BACK_SPARSE_MERGE=sparse_mode,
                               VICTORY_BACK_AVX2=avx_mode)
                    result = subprocess.run([str(binary), "copy_back_mask_tests"], env=env,
                                            check=True, capture_output=True, text=True, timeout=60)
                    self.assertIn("5 passed; 0 failed", result.stdout)
