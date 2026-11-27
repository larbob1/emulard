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

// Reuses the page helper from the historical native-passing codec fixture.
struct ScratchNativePages {
    ids: [usize; 2],
    separate: bool,
}

impl ScratchNativePages {
    fn new(separate: bool) -> Self {
        use super::super::xmem;
        let mut ids = [0usize; 2];
        if separate {
            for id in &mut ids {
                let mut n = 1;
                assert_eq!(xmem::XMemAllocatePhysicalPages(0, &mut n, id), 1);
                assert_eq!(n, 1);
            }
        } else {
            let mut n = ids.len();
            assert_eq!(xmem::XMemAllocatePhysicalPages(0, &mut n, ids.as_mut_ptr()), 1);
            assert_eq!(n, 2);
        }
        Self { ids, separate }
    }

    fn reset(&self) {
        use super::super::xmem;
        for (id, offset) in self.ids.iter().zip([PAGE - 16, 0]) {
            let mut window = xmem::page_window(std::slice::from_ref(id), offset, 16).unwrap();
            window.bytes().fill(0xA5);
        }
    }

    fn seen(&self) -> [u8; 32] {
        use super::super::xmem;
        let mut out = [0u8; 32];
        for ((id, offset), chunk) in self.ids.iter().zip([PAGE - 16, 0])
            .zip(out.chunks_exact_mut(16)) {
            let mut window = xmem::page_window(std::slice::from_ref(id), offset, 16).unwrap();
            chunk.copy_from_slice(window.bytes());
        }
        out
    }

    fn assert_path(&self) {
        use super::super::xmem;
        // The real page_window result establishes the path in this isolated
        // fixture, not whether a particular gameplay request takes it.
        assert_eq!(xmem::page_window(&self.ids, PAGE - 8, 16).is_some(), !self.separate);
    }
}

impl Drop for ScratchNativePages {
    fn drop(&mut self) {
        use super::super::xmem;
        // No title view or temporary window is retained across this call.
        assert_eq!(xmem::XMemFreePhysicalPages(self.ids.len(), self.ids.as_ptr()), 1);
    }
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
    let retained_ptr = scratch.idle.as_ptr();
    let retained_hits = scratch.hits;
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

    // File-owned compressed source must not acquire or evict the raw slot.
    let mut bad = packed.clone();
    *bad.last_mut().unwrap() ^= 1;
    for (source, expected) in [
        (packed.as_slice(), Ok(())),
        (bad.as_slice(), Err(INVALID_DATA)),
        (packed.as_slice(), Ok(())),
    ] {
        let (_packed_dir, packed_file) = file_with(source);
        let mut baseline = [0xA5; 32];
        let mut candidate = baseline;
        let mut r = request(ZLIB, baseline[8..24].as_mut_ptr().cast(),
            16, packed_file.cast_const(), 0, source.len());
        assert_eq!(execute(&r), expected);
        r.destination = candidate[8..24].as_mut_ptr().cast();
        assert_eq!(execute_scratch_review(&r, &mut scratch), expected);
        assert_eq!(candidate, baseline);
        assert_eq!(&candidate[..8], &[0xA5; 8]);
        assert_eq!(&candidate[24..], &[0xA5; 8]);
        if expected.is_ok() {
            assert_eq!(&candidate[8..24], &bytes[..16]);
        }
        assert_eq!(scratch.calls, 1);
        assert_eq!(scratch.hits, retained_hits);
        assert_eq!(scratch.idle.capacity(), retained);
        assert_eq!(scratch.idle.as_ptr(), retained_ptr);
        release(packed_file.cast::<Instance<File>>());
    }

    // Raw file-to-page requests bypass the address bounce even when the
    // physical fallback itself allocates a temporary destination buffer.
    for separate in [false, true] {
        let mut pages = ScratchNativePages::new(separate);
        pages.assert_path();
        for (offset, expected) in [
            (0usize, Ok(())),
            (bytes.len() - 3, Err(END_OF_FILE)),
            (17, Ok(())),
        ] {
            pages.reset();
            let mut r = request(PAGE_DESTINATION, pages.ids.as_mut_ptr().cast(),
                16, file.cast_const(), offset as u64, 16);
            r.page_offset = (PAGE - 8) as u64;
            assert_eq!(execute(&r), expected);
            let baseline = pages.seen();
            pages.reset();
            assert_eq!(execute_scratch_review(&r, &mut scratch), expected);
            let candidate = pages.seen();
            assert_eq!(candidate, baseline);
            assert_eq!(&candidate[..8], &[0xA5; 8]);
            assert_eq!(&candidate[24..], &[0xA5; 8]);
            if expected.is_ok() {
                assert_eq!(&candidate[8..24], &bytes[offset..offset + 16]);
            } else if separate {
                // A failed read into disjoint fallback is not published.
                assert_eq!(&candidate[8..24], &[0xA5; 16]);
            }
            // For direct physical EOF, compare actual baseline bytes,
            // without assuming how many bytes the host read before EOF.
            assert_eq!(scratch.calls, 1);
            assert_eq!(scratch.hits, retained_hits);
            assert_eq!(scratch.idle.capacity(), retained);
            assert_eq!(scratch.idle.as_ptr(), retained_ptr);
        }
    }
    scratch.trim();
    assert_eq!(scratch.idle.capacity(), 0);
    release(file.cast::<Instance<File>>());
}
