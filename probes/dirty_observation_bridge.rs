// SPDX-License-Identifier: GPL-3.0-or-later
// Review-only: appended to shadow.rs by a proposed transform, not registered.
// Slice-relative 4 KiB chunks, NOT stable backing pages or per-flight coverage.
#[cfg(feature = "diagnostics")]
mod dirty_observation {
    use std::sync::atomic::{AtomicU64, Ordering::Relaxed};
    use std::sync::OnceLock;

    const LIMIT: u64 = 4096;
    const MAX_BYTES: usize = 65536;
    const CHUNK: usize = 4096;
    static ON: OnceLock<bool> = OnceLock::new();
    static ADMITTED: AtomicU64 = AtomicU64::new(0);
    // Every row: completed samples, compared bytes, chunks, unequal chunks.
    static COUNT: [[AtomicU64; 4]; 3] = [const { [const { AtomicU64::new(0) }; 4] }; 3];

    fn enabled() -> bool {
        *ON.get_or_init(|| std::env::var_os("VICTORY_DIRTY_OBSERVE").is_some_and(|v| v == "1"))
    }

    fn admit(counter: &AtomicU64, cap: u64) -> bool {
        // Fixed, single-attempt admission. Contention loses a sample rather
        // than adding a retry loop under the caller's existing locks.
        let n = counter.load(Relaxed);
        n < cap && counter.compare_exchange(n, n + 1, Relaxed, Relaxed).is_ok()
    }

    fn summarize(a: &[u8], b: &[u8]) -> Option<[u64; 4]> {
        if a.is_empty() || a.len() != b.len() || a.len() > MAX_BYTES {
            return None;
        }
        let chunks = a.len().div_ceil(CHUNK);
        let unequal = a.chunks(CHUNK).zip(b.chunks(CHUNK)).filter(|(x,y)| x != y).count();
        Some([1, a.len() as u64, chunks as u64, unequal as u64])
    }

    pub(super) fn sample(path: usize, a: &[u8], b: &[u8]) {
        if !enabled() || path >= COUNT.len() || a.is_empty() || a.len() != b.len()
            || a.len() > MAX_BYTES || !admit(&ADMITTED, LIMIT) { return; }
        if let Some(row) = summarize(a,b) {
            // Bounded per-process totals cannot wrap. Independently updated
            // fields are not an atomic snapshot; no per-frame ratios.
            for i in [1, 2, 3, 0] { COUNT[path][i].fetch_add(row[i], Relaxed); }
        }
    }

    pub(super) fn snapshot() -> Option<[[u64; 4]; 3]> {
        enabled().then(|| std::array::from_fn(|p| std::array::from_fn(|i| COUNT[p][i].load(Relaxed))))
    }

    #[cfg(test)]
    mod tests {
        use super::*;
        #[test]
        fn unequal_chunks_count_crossings_and_tail() {
            let a = vec![0; 8193];
            let mut b = a.clone();
            assert_eq!(summarize(&a,&b), Some([1,8193,3,0]));
            b[4095] = 1; b[4096] = 2; b[8192] = 3;
            assert_eq!(summarize(&a,&b), Some([1,8193,3,3]));
        }
        #[test]
        fn rejects_empty_mismatch_and_oversized() {
            assert_eq!(summarize(&[],&[]), None);
            assert_eq!(summarize(&[1],&[1,2]), None);
            let big = vec![0; MAX_BYTES+1];
            assert_eq!(summarize(&big,&big), None);
            let max = vec![0; MAX_BYTES];
            assert_eq!(summarize(&max,&max), Some([1,MAX_BYTES as u64,16,0]));
        }
        #[test]
        fn admission_cap_is_exact_serially_and_bounded_under_contention() {
            let n = AtomicU64::new(0);
            for _ in 0..4 { assert!(admit(&n,4)); }
            assert!(!admit(&n,4));
            assert_eq!(n.load(Relaxed),4);
            let n = AtomicU64::new(0);
            std::thread::scope(|s| {
                for _ in 0..8 { s.spawn(|| { for _ in 0..1000 { admit(&n,128); } }); }
            });
            assert!(n.load(Relaxed) <= 128);
            assert!(n.load(Relaxed) > 0);
        }
        #[test]
        fn sampled_inputs_never_change() {
            let a = vec![0; 8193];
            let mut b = a.clone(); b[0]=1;
            let old = b.clone();
            let _ = summarize(&a,&b);
            assert_eq!(b,old);
            assert_eq!(a,vec![0;8193]);
        }
    }
}

#[cfg(feature = "diagnostics")]
pub(crate) fn dirty_observation_snapshot() -> Option<[[u64; 4]; 3]> {
    dirty_observation::snapshot()
}
