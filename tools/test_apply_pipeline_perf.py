# SPDX-License-Identifier: GPL-3.0-or-later
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from apply_pipeline_perf import PATCHES, transform

class PipelinePerfTests(unittest.TestCase):
    def test_all_anchors(self):
        for replacements in PATCHES.values():
            source = "\n".join(old for old, _ in replacements)
            result = transform(source, replacements)
            for _, new in replacements:
                self.assertIn(new, result)

    def test_fail_closed(self):
        for replacements in PATCHES.values():
            source = "\n".join(old for old, _ in replacements)
            for old, _ in replacements:
                with self.assertRaises(ValueError):
                    transform(source.replace(old, "", 1), replacements)
                with self.assertRaises(ValueError):
                    transform(source + "\n" + old, replacements)


@unittest.skipUnless(shutil.which("rustc"), "rustc required for portable cache tests")
class PipelinePublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.work.cleanup)
        root = Path(cls.work.name)
        replacements = PATCHES["crates/victory-gpu/src/pipeline/library.rs"]
        # Compile the actual runtime replacement, not a separately maintained model.
        helper, = [new for old, new in replacements if old.startswith("fn replace_library(")]
        source = root / "publication.rs"
        source.write_text(helper + r'''
use std::{fs, path::Path};
const LIBRARY_FILE: &str = "host-pipelines.bin";
const NEXT_FILE: &str = "host-pipelines.next";

fn main() {
    let args: Vec<_> = std::env::args().collect();
    let dir = Path::new(&args[2]);
    let primary = dir.join(LIBRARY_FILE);
    let next = dir.join(NEXT_FILE);
    let tmp = dir.join("host-pipelines.tmp");
    match args[1].as_str() {
        "zero" => {
            assert!(validate_serialized_size(0).is_err());
            assert!(validate_serialized_size(1).is_ok());
            assert!(validate_serialized_size(4096).is_ok());
        }
        "direct" => {
            fs::write(&primary, b"old").unwrap();
            fs::write(&tmp, b"new").unwrap();
            replace_library(dir, &tmp).unwrap();
            assert_eq!(fs::read(&primary).unwrap(), b"new");
            assert!(!next.exists());
            assert!(!tmp.exists());
        }
        "supersede" => {
            fs::write(&primary, b"old").unwrap();
            fs::write(&next, b"pending").unwrap();
            fs::write(&tmp, b"newest").unwrap();
            replace_library(dir, &tmp).unwrap();
            assert_eq!(fs::read(&primary).unwrap(), b"old");
            assert_eq!(fs::read(&next).unwrap(), b"newest");
            assert!(!tmp.exists());
            // Same promotion operation as Blob::of on restart.
            fs::rename(&next, &primary).unwrap();
            assert_eq!(fs::read(&primary).unwrap(), b"newest");
        }
        "retry" => {
            fs::write(&primary, b"old").unwrap();
            fs::create_dir(&next).unwrap();
            fs::write(&tmp, b"newest").unwrap();
            assert!(replace_library(dir, &tmp).is_err());
            assert_eq!(fs::read(&primary).unwrap(), b"old");
            assert_eq!(fs::read(&tmp).unwrap(), b"newest");
            fs::remove_dir(&next).unwrap();
            replace_library(dir, &tmp).unwrap();
            assert_eq!(fs::read(&primary).unwrap(), b"newest");
            assert!(!tmp.exists());
        }
        "fallback" => {
            fs::create_dir(&primary).unwrap();
            fs::write(&tmp, b"pending").unwrap();
            replace_library(dir, &tmp).unwrap();
            assert_eq!(fs::read(&next).unwrap(), b"pending");
            assert!(primary.is_dir());
            fs::write(&tmp, b"newest").unwrap();
            replace_library(dir, &tmp).unwrap();
            fs::remove_dir(&primary).unwrap();
            fs::rename(&next, &primary).unwrap();
            assert_eq!(fs::read(&primary).unwrap(), b"newest");
        }
        _ => panic!("unknown scenario"),
    }
}
''', encoding="utf-8")
        cls.binary = root / ("publication.exe" if os.name == "nt" else "publication")
        subprocess.run(["rustc", "--edition=2021", str(source), "-o", str(cls.binary)],
                       check=True, capture_output=True, text=True)

    def run_case(self, case):
        with tempfile.TemporaryDirectory() as work:
            subprocess.run([str(self.binary), case, work], check=True,
                           capture_output=True, text=True)

    def test_zero_size(self):
        self.run_case("zero")

    def test_direct_publication(self):
        self.run_case("direct")

    def test_pending_publication_supersedes_old_next(self):
        self.run_case("supersede")

    def test_failed_pending_publication_preserves_primary_for_retry(self):
        self.run_case("retry")

    def test_primary_refusal_falls_back_and_latest_pending_wins(self):
        self.run_case("fallback")

if __name__ == "__main__":
    unittest.main()
