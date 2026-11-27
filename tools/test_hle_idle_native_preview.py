"""Preview a test-only clone of pinned Pool, with optional idle retirement."""
import argparse
from pathlib import Path
import unittest

from preview_hle_pool_native import PINNED_BLOB, git_blob

FIXTURE = Path(__file__).resolve().parents[1] / "probes" / "hle_idle_native_review.rs"
MARKER = b"mod hle_idle_native_review"
PLACEHOLDER = b"    // @POOL_CLONE@"
STRUCT = b"""struct Pool {
    /// Queued tasks and the number of idle workers.
    state: Mutex<(VecDeque<Task>, usize)>,
    ready: Condvar,
}"""
STATIC = b"""static POOL: Pool = Pool {
    state: Mutex::new((VecDeque::new(), 0)),
    ready: Condvar::new(),
};"""
IMPL = b"""impl Pool {
    fn submit(&'static self, task: Task) {
        let mut state = lock(&self.state);
        state.0.push_back(task);
        if state.0.len() > state.1 {
            std::thread::spawn(move || self.work());
        } else {
            self.ready.notify_one();
        }
    }

    fn work(&self) {
        let mut state = lock(&self.state);
        loop {
            while state.0.is_empty() {
                state.1 += 1;
                state = self.ready.wait(state).unwrap_or_else(|e| e.into_inner());
                state.1 -= 1;
            }
            let task = state.0.pop_front();
            drop(state);
            if let Some(task) = task {
                task.run(false);
            }
            state = lock(&self.state);
        }
    }
}"""
WAIT = b"""                state = self.ready.wait(state).unwrap_or_else(|e| e.into_inner());
                state.1 -= 1;"""
CANDIDATE_WAIT = b"""                if let Some(timeout) = self.timeout {
                    let (mut next, _) = self.ready.wait_timeout_while(
                        state, timeout, |s| s.0.is_empty()
                    ).unwrap_or_else(|e| e.into_inner());
                    next.1 -= 1;
                    if next.0.is_empty() {
                        self.retired.fetch_add(1, Ordering::SeqCst);
                        return;
                    }
                    state = next;
                } else {
                    state = self.ready.wait(state).unwrap_or_else(|e| e.into_inner());
                    state.1 -= 1;
                }"""
FIELDS = b"""    timeout: Option<Duration>,
    retired: AtomicUsize,
"""

def preview(source, fixture, expected=PINNED_BLOB):
    if git_blob(source) != expected:
        raise ValueError("not exact pinned xasync.rs")
    for anchor in (STRUCT, STATIC, IMPL):
        if source.count(anchor) != 1:
            raise ValueError("missing or duplicate Pool anchor")
    if MARKER in source or fixture.count(MARKER) != 1 or fixture.count(PLACEHOLDER) != 1:
        raise ValueError("missing or duplicate test module marker")
    if fixture.count(b"#[cfg(test)]") != 1 or IMPL.count(WAIT) != 1:
        raise ValueError("missing test gate or wait anchor")
    structure = STRUCT.replace(b"struct Pool", b"struct ReviewPool", 1)
    structure = structure[:-1] + FIELDS + b"}"
    implementation = IMPL.replace(b"impl Pool", b"impl ReviewPool", 1).replace(WAIT, CANDIDATE_WAIT, 1)
    clone = structure + b"\n\n" + implementation
    module = fixture.replace(PLACEHOLDER, clone, 1)
    return source + b"\n" + module


class IdleNativePreviewTests(unittest.TestCase):
    def setUp(self):
        self.source = STRUCT + b"\n\n" + STATIC + b"\n\n" + IMPL
        self.fixture = FIXTURE.read_bytes()

    def test_production_prefix_and_unique_clone(self):
        result = preview(self.source, self.fixture, git_blob(self.source))
        self.assertTrue(result.startswith(self.source + b"\n"))
        self.assertEqual(result.count(b"struct ReviewPool"), 1)
        self.assertEqual(result.count(b"impl ReviewPool"), 1)
        self.assertEqual(result.count(CANDIDATE_WAIT), 1)
        self.assertNotIn(PLACEHOLDER, result)
        module = result[len(self.source)+1:]
        self.assertIn(b"#[cfg(test)]", module)
        self.assertIn(b"if state.0.len() > state.1", module)
        self.assertIn(b"task.run(false)", module)

    def test_exact_reversal_of_clone(self):
        result = preview(self.source, self.fixture, git_blob(self.source))
        module = result[len(self.source)+1:]
        self.assertIn(STRUCT.replace(b"struct Pool", b"struct ReviewPool", 1)[:-1] + FIELDS + b"}", module)
        self.assertIn(IMPL.replace(b"impl Pool", b"impl ReviewPool", 1).replace(WAIT, CANDIDATE_WAIT, 1), module)

    def test_wrong_blob_refuses(self):
        with self.assertRaisesRegex(ValueError, "not exact"):
            preview(self.source, self.fixture)

    def test_missing_duplicate_anchor_refuses(self):
        for source in (self.source.replace(STATIC, b""), self.source + IMPL):
            with self.assertRaisesRegex(ValueError, "anchor"):
                preview(source, self.fixture, git_blob(source))

    def test_bad_module_refuses(self):
        for fixture in (self.fixture * 2, self.fixture.replace(PLACEHOLDER, b""),
                        self.fixture.replace(b"#[cfg(test)]", b"")):
            with self.assertRaises(ValueError):
                preview(self.source, fixture, git_blob(self.source))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = preview(args.source.read_bytes(), FIXTURE.read_bytes())
    with args.output.open("xb") as out:
        out.write(data)


if __name__ == "__main__":
    main()
