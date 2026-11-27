// SPDX-License-Identifier: GPL-3.0-or-later
// Test-only native file I/O characterization. Synthetic files only.
// No changes to positional reads, source ownership, or GPU notifications.

#[test]
#[ignore = "isolated native raw bounce and EOF characterization"]
fn storage_file_native_bounce_and_eof() {
    let bytes = pattern(4096);
    let (_dir, file) = file_with(&bytes);
    for (offset, size, expect) in [
        (0usize, 16usize, Ok(())),
        (4080, 16, Ok(())),
        (4090, 16, Err(END_OF_FILE)),
        (4096, 16, Err(END_OF_FILE)),
        (4100, 16, Err(END_OF_FILE)),
        (4096, 0, Ok(())),
    ] {
        // Direct scratch read and raw execute differ on a failed read:
        // the latter bounces and only copies after a successful full read.
        let mut scratch = [0xA5u8; 32];
        let mut destination = [0xA5u8; 48];
        let r = request(0, destination[8..40].as_mut_ptr().cast(), 32,
            file.cast_const(), offset as u64, size);
        assert_eq!(read_into(&r, &mut scratch[8..8 + size]), expect);
        let available = bytes.len().saturating_sub(offset).min(size);
        if available != 0 {
            assert_eq!(&scratch[8..8 + available], &bytes[offset..offset + available]);
        }
        assert!(scratch[..8].iter().all(|&v| v == 0xA5));
        assert!(scratch[8 + size..].iter().all(|&v| v == 0xA5));
        assert_eq!(execute(&r), expect);
        if expect.is_ok() && size != 0 {
            assert_eq!(&destination[8..8 + size], &bytes[offset..offset + size]);
            assert!(destination[8 + size..].iter().all(|&v| v == 0xA5));
        } else {
            assert_eq!(destination, [0xA5; 48]);
        }
        assert!(destination[..8].iter().all(|&v| v == 0xA5));
        // Compressed source acquisition must return a complete owned
        // buffer or the same error; never expose a partially read Cow.
        match (read_source(&r), expect) {
            (Ok(Cow::Owned(data)), Ok(())) => {
                assert_eq!(data.len(), size);
                if size != 0 { assert_eq!(&data[..], &bytes[offset..offset + size]); }
            }
            (Err(hr), Err(expected)) => assert_eq!(hr, expected),
            _ => panic!("wrong source acquisition result"),
        }
    }
    // Size validation happens before any read or write.
    let mut invalid = [0xA5u8; 16];
    let r = request(0, invalid.as_mut_ptr().cast(), 8, file.cast_const(), 0, 16);
    assert_eq!(execute(&r), Err(E_INVALIDARG));
    assert_eq!(invalid, [0xA5; 16]);
    release(file.cast::<Instance<File>>());
}

#[test]
#[ignore = "isolated native shared-file positional read correctness"]
fn storage_file_native_shared_offsets() {
    // Larger than the test slices and with a nonperiodic position pattern.
    let mut seed = 0x8a5cd789635d2dffu64;
    let bytes: Vec<u8> = (0..256 * 1024).map(|_| {
        seed ^= seed << 13;
        seed ^= seed >> 7;
        seed ^= seed << 17;
        seed as u8
    }).collect();
    let (_dir, file) = file_with(&bytes);
    // The file object is kept alive through all scoped thread joins.
    // Only its shared std::fs::File is read; each output is private.
    // The address is passed as usize because the opaque raw pointer
    // itself is not Send. This mirrors the existing Request lifetime
    // contract, without changing ownership or reference counts.
    let file_addr = file as usize;
    let barrier = std::sync::Barrier::new(4);
    std::thread::scope(|scope| {
        for worker in 0..4usize {
            let bytes = &bytes;
            let barrier = &barrier;
            scope.spawn(move || {
                barrier.wait();
                for i in 0..64usize {
                    // Includes overlapping source regions, repeated and
                    // reversed offsets, variable length, and EOF boundary.
                    let size = [1, 31, 4096, 65536][(worker + i) % 4];
                    let offset = if i % 8 == 0 {
                        bytes.len() - size
                    } else {
                        ((63 - i) * 7907 + worker * 17) % (bytes.len() - size + 1)
                    };
                    let mut out = vec![0xA5; size + 16];
                    let r = request(0, out[8..8 + size].as_mut_ptr().cast(), size,
                        file_addr as *const c_void, offset as u64, size);
                    assert_eq!(read_into(&r, &mut out[8..8 + size]), Ok(()));
                    assert_eq!(&out[8..8 + size], &bytes[offset..offset + size]);
                    assert_eq!(&out[..8], &[0xA5; 8]);
                    assert_eq!(&out[8 + size..], &[0xA5; 8]);
                }
            });
        }
    });
    release(file.cast::<Instance<File>>());
}
