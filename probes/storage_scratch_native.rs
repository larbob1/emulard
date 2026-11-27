// SPDX-License-Identifier: GPL-3.0-or-later
// Test-only explicit worker-owned scratch candidate. No TLS, worker
// scheduling, new guard hooks, or production retention policy.

struct NativeScratch {
    idle: Vec<u8>,
    limit: usize,
    hits: usize,
    calls: usize,
}

impl NativeScratch {
    fn new(limit: usize) -> Self {
        Self { idle: Vec::new(), limit, hits: 0, calls: 0 }
    }

    fn trim(&mut self) {
        self.idle = Vec::new();
    }

    fn run<T, E>(&mut self, size: usize,
                 op: impl FnOnce(&mut [u8]) -> Result<T, E>) -> Result<T, E> {
        self.calls += 1;
        let mut data = std::mem::take(&mut self.idle);
        if size > self.limit || self.limit == 0 {
            data = Vec::new();
        }
        self.hits += usize::from(size != 0 && data.capacity() >= size);
        data.clear();
        data.resize(size, 0);
        let result = op(&mut data);
        if result.is_ok() && self.limit != 0 && data.capacity() <= self.limit {
            data.clear();
            self.idle = data;
        }
        result
    }
}

#[test]
#[ignore = "isolated native scratch raw file parity"]
fn storage_scratch_native_file_parity() {
    let mut seed = 0x8a5cd789635d2dffu64;
    let bytes: Vec<u8> = (0..256 * 1024).map(|_| {
        seed ^= seed << 13;
        seed ^= seed >> 7;
        seed ^= seed << 17;
        seed as u8
    }).collect();
    let (_dir, file) = file_with(&bytes);
    let end = bytes.len();
    for cap in [0usize, 4096, 65536] {
        let mut scratch = NativeScratch::new(cap);
        for _ in 0..4 {
            for (offset, size, dest_size, expected) in [
                (0usize, 4096usize, 4104usize, Ok(())),
                (19, 4096, 4104, Ok(())),
                (123, 32, 40, Ok(())),
                (end - 65536, 65536, 65544, Ok(())),
                (end - 3, 16, 24, Err(END_OF_FILE)),
                (end, 16, 24, Err(END_OF_FILE)),
                (end, 0, 8, Ok(())),
                (0, 131072, 131080, Ok(())),
                (0, 16, 8, Err(E_INVALIDARG)),
                (57, 4096, 4104, Ok(())),
                (99, 4096, 4104, Ok(())),
            ] {
                let mut baseline = vec![0xA5; dest_size + 16];
                let mut candidate = baseline.clone();
                let mut req = request(0, baseline[8..8+dest_size].as_mut_ptr().cast(),
                    dest_size, file.cast_const(), offset as u64, size);
                let a = execute(&req);
                req.destination = candidate[8..8+dest_size].as_mut_ptr().cast();
                let b = execute_scratch_review(&req, &mut scratch);
                assert_eq!(a, expected);
                assert_eq!(a, b);
                assert_eq!(baseline, candidate);
                assert_eq!(&candidate[..8], &[0xA5; 8]);
                assert_eq!(&candidate[8+dest_size..], &[0xA5; 8]);
                if expected.is_ok() {
                    assert_eq!(&candidate[8..8+size], &bytes[offset..offset+size]);
                    assert!(candidate[8+size..].iter().all(|&x| x == 0xA5));
                } else {
                    assert!(candidate.iter().all(|&x| x == 0xA5));
                }
                assert!(scratch.idle.capacity() <= cap);
                if expected == Err(END_OF_FILE) || (expected.is_ok() && size > cap) {
                    assert_eq!(scratch.idle.capacity(), 0);
                }
            }
            scratch.trim();
            assert_eq!(scratch.idle.capacity(), 0);
        }
        assert_eq!(scratch.calls, 40); // invalid-size requests bypass bounce
        if cap == 0 {
            assert_eq!(scratch.hits, 0);
        } else {
            assert!(scratch.hits >= 8);
        }
    }
    release(file.cast::<Instance<File>>());
}

#[test]
#[ignore = "isolated native scratch nonbounce and cleanup parity"]
fn storage_scratch_native_nonbounce() {
    let bytes = pattern(8192);
    let (_dir, file) = file_with(&bytes);
    let mut scratch = NativeScratch::new(65536);
    let mut out = vec![0xA5; 4104];
    let r = request(0, out.as_mut_ptr().cast(), out.len(), file.cast_const(), 0, 4096);
    assert_eq!(execute_scratch_review(&r, &mut scratch), Ok(()));
    let retained = scratch.idle.capacity();
    assert!(retained >= 4096);
    let mut baseline = [0xA5; 48];
    let mut candidate = baseline;
    let mut r = request(MEMORY_SOURCE, baseline[8..40].as_mut_ptr().cast(),
        32, bytes.as_ptr().cast(), 0, 16);
    assert_eq!(execute(&r), Ok(()));
    r.destination = candidate[8..40].as_mut_ptr().cast();
    assert_eq!(execute_scratch_review(&r, &mut scratch), Ok(()));
    assert_eq!(candidate, baseline);
    assert_eq!(&candidate[8..24], &bytes[..16]);
    assert_eq!(scratch.calls, 1);
    assert_eq!(scratch.idle.capacity(), retained);

    // Real single-stage zlib remains on the original codec path.
    let packed = compress_zlib(&bytes[..16]);
    let mut baseline = [0xA5; 48];
    let mut candidate = baseline;
    let mut r = request(ZLIB | MEMORY_SOURCE, baseline[8..40].as_mut_ptr().cast(),
        32, packed.as_ptr().cast(), 0, packed.len());
    assert_eq!(execute(&r), Ok(()));
    r.destination = candidate[8..40].as_mut_ptr().cast();
    assert_eq!(execute_scratch_review(&r, &mut scratch), Ok(()));
    assert_eq!(candidate, baseline);
    assert_eq!(scratch.calls, 1);
    assert_eq!(scratch.idle.capacity(), retained);
    scratch.trim();
    assert_eq!(scratch.idle.capacity(), 0);
    release(file.cast::<Instance<File>>());
}
