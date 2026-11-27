// SPDX-License-Identifier: GPL-3.0-or-later
// Test-only fragment included inside the pinned dstorage::tests module.
// Uses the real runtime codecs and destination path, generated inputs only.
// No production hooks, allocator measurement, or GPU observation claims.

const CODEC_NATIVE_SENTINEL: u8 = 0xA5;

fn codec_native_execute(
    options: u64,
    packed: &[u8],
    intermediate: usize,
    destination: *mut c_void,
    len: usize,
    offset: usize,
    memory: bool,
) -> Result<(), HRESULT> {
    let execute_from = |source: *const c_void, source_options: u64| {
        let mut r = request(options | source_options, destination, len, source, 0, packed.len());
        r.intermediate_size = intermediate as u32;
        r.page_offset = offset as u64;
        execute(&r)
    };
    if memory {
        execute_from(packed.as_ptr().cast(), MEMORY_SOURCE)
    } else {
        let (_dir, file) = file_with(packed);
        let result = execute_from(file.cast_const(), 0);
        release(file.cast::<Instance<File>>());
        result
    }
}

#[test]
#[ignore = "isolated native codec fixture; fresh process with generated inputs"]
fn storage_codec_native_chain_address() {
    with_test_tables();
    let good = compress_zlib(&BC4_STREAM);
    let truncated = &good[..good.len() - 1];
    let empty = compress_zlib(&[]);
    let options = ZLIB | (4 << 1);
    for memory in [false, true] {
        for (packed, intermediate, expected) in [
            (good.as_slice(), BC4_STREAM.len(), Ok(())),
            (good.as_slice(), BC4_STREAM.len() + 31, Ok(())),
            (truncated, BC4_STREAM.len() + 31, Err(INVALID_DATA)),
            (good.as_slice(), BC4_STREAM.len() - 1, Err(INVALID_DATA)),
            (empty.as_slice(), BC4_STREAM.len() + 31, Err(INVALID_DATA)),
        ] {
            let mut guarded = [CODEC_NATIVE_SENTINEL; 32];
            let result = codec_native_execute(options, packed, intermediate,
                guarded[8..24].as_mut_ptr().cast(), 16, 0, memory);
            assert_eq!(result, expected);
            if result.is_ok() {
                assert_eq!(&guarded[8..24], &bc4_blocks()[..]);
            } else {
                // These specific invalid streams fail before BC4 output.
                assert_eq!(&guarded[8..24], &[CODEC_NATIVE_SENTINEL; 16]);
            }
            assert_eq!(&guarded[..8], &[CODEC_NATIVE_SENTINEL; 8]);
            assert_eq!(&guarded[24..], &[CODEC_NATIVE_SENTINEL; 8]);
        }
        // Same-thread decoder state must recover after the failures.
        let mut out = [CODEC_NATIVE_SENTINEL; 16];
        assert_eq!(codec_native_execute(options, &good, BC4_STREAM.len(),
            out.as_mut_ptr().cast(), out.len(), 0, memory), Ok(()));
        assert_eq!(out, bc4_blocks());
    }
}

// Test fixture allocates two physical pages, either one consecutive run or
// independent sections. Use single-page windows to initialize/read only
// the 16-byte destination and its two 8-byte guard regions.
struct CodecNativePages {
    ids: [usize; 2],
    separate: bool,
}

impl CodecNativePages {
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
            window.bytes().fill(CODEC_NATIVE_SENTINEL);
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

impl Drop for CodecNativePages {
    fn drop(&mut self) {
        use super::super::xmem;
        // No title view or temporary window is retained across this call.
        assert_eq!(xmem::XMemFreePhysicalPages(self.ids.len(), self.ids.as_ptr()), 1);
    }
}

#[test]
#[ignore = "isolated native codec fixture; fresh process with generated inputs"]
fn storage_codec_native_chain_pages() {
    with_test_tables();
    let good = compress_zlib(&BC4_STREAM);
    let empty = compress_zlib(&[]);
    let options = ZLIB | (4 << 1) | PAGE_DESTINATION;
    for separate in [false, true] {
        let mut pages = CodecNativePages::new(separate);
        pages.assert_path();
        for memory in [false, true] {
            for (packed, expected) in [
                (good.as_slice(), Ok(())),
                (&good[..good.len() - 1], Err(INVALID_DATA)),
                (empty.as_slice(), Err(INVALID_DATA)),
                (good.as_slice(), Ok(())),
            ] {
                pages.reset();
                assert_eq!(codec_native_execute(options, packed, BC4_STREAM.len() + 31,
                    pages.ids.as_mut_ptr().cast(), 16, PAGE - 8, memory), expected);
                let seen = pages.seen();
                if expected.is_ok() {
                    assert_eq!(&seen[8..24], &bc4_blocks()[..]);
                } else {
                    assert_eq!(&seen[8..24], &[CODEC_NATIVE_SENTINEL; 16]);
                }
                assert_eq!(&seen[..8], &[CODEC_NATIVE_SENTINEL; 8]);
                assert_eq!(&seen[24..], &[CODEC_NATIVE_SENTINEL; 8]);
            }
        }
    }
}

#[test]
#[ignore = "isolated native codec fixture; fresh process with generated inputs"]
fn storage_codec_native_partial_error() {
    let plain = [1u8, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16];
    let good = compress_zlib(&plain);
    let mut bad = good.clone();
    *bad.last_mut().unwrap() ^= 1;
    // Actual decoder oracle, not a hard-coded assumption that failed
    // decompression produces zero bytes.
    let mut oracle = [CODEC_NATIVE_SENTINEL; 16];
    assert_eq!(inflate(&bad, &mut oracle), Err(INVALID_DATA));
    assert_ne!(oracle, [CODEC_NATIVE_SENTINEL; 16]);

    for memory in [false, true] {
        let mut guarded = [CODEC_NATIVE_SENTINEL; 32];
        assert_eq!(codec_native_execute(ZLIB, &bad, 0,
            guarded[8..24].as_mut_ptr().cast(), 16, 0, memory), Err(INVALID_DATA));
        assert_eq!(&guarded[8..24], &oracle[..]);
        assert_eq!(&guarded[..8], &[CODEC_NATIVE_SENTINEL; 8]);
        assert_eq!(&guarded[24..], &[CODEC_NATIVE_SENTINEL; 8]);

        for separate in [false, true] {
            let mut pages = CodecNativePages::new(separate);
            pages.assert_path();
            pages.reset();
            assert_eq!(codec_native_execute(ZLIB | PAGE_DESTINATION, &bad, 0,
                pages.ids.as_mut_ptr().cast(), 16, PAGE - 8, memory), Err(INVALID_DATA));
            let seen = pages.seen();
            // Direct decoding retains actual partial bytes; a failed fill
            // into fallback storage must not publish that temporary buffer.
            let expected = if separate { [CODEC_NATIVE_SENTINEL; 16] } else { oracle };
            assert_eq!(&seen[8..24], &expected[..]);
            assert_eq!(&seen[..8], &[CODEC_NATIVE_SENTINEL; 8]);
            assert_eq!(&seen[24..], &[CODEC_NATIVE_SENTINEL; 8]);
            assert_eq!(codec_native_execute(ZLIB | PAGE_DESTINATION, &good, 0,
                pages.ids.as_mut_ptr().cast(), 16, PAGE - 8, memory), Ok(()));
            assert_eq!(&pages.seen()[8..24], &plain[..]);
        }
    }
}
