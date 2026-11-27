// SPDX-License-Identifier: GPL-3.0-or-later
// Test-only fragment for victory-formats::bcpack::tests.
// The candidate does not alter the real decoder or its error ordering.

#[test]
#[ignore = "isolated native history proof"]
fn bcpack_history_native_reference_bounds() {
    assert_eq!(HISTORY, 256);
    let dictionary: Vec<usize> = (0..HISTORY).map(|x| usize::MAX - x - 1).collect();
    let zero = usize::MAX;
    for blocks in [0usize, 1, 2, 7, 16, 64, 127, 254, 255, 256, 257, 511, 512, 513, 1024] {
        let mut full = vec![0usize; HISTORY];
        let mut compact = vec![0usize; blocks.min(HISTORY)];
        for i in 0..blocks {
            // Real pick() is generic; reference fields decode to u8.
            // Check dictionary, no-reference, previous-block, and wrap cases.
            for distance in 0..HISTORY {
                assert_eq!(
                    pick(i, distance, &full, &dictionary, &zero),
                    pick(i, distance, &compact, &dictionary, &zero),
                    "blocks={blocks} i={i} distance={distance}"
                );
            }
            full[i % HISTORY] = i + 1;
            compact[i % HISTORY] = i + 1;
        }
        assert_eq!(&full[..compact.len()], &compact);
    }
    // Actual type sizes, not an estimate of allocator capacity/residency.
    for (format, entry) in [
        ("plain", std::mem::size_of::<Plain>()),
        ("bc6", std::mem::size_of::<(Bc6Ep, Bc6Ix)>()),
        ("bc7", std::mem::size_of::<(Bc7Ep, Bc7Ix)>()),
    ] {
        for blocks in [1usize, 4, 16, 64, 255, 256, 257] {
            println!("bcpack_history_extent format={} blocks={} entry_bytes={} full_bytes={} candidate_bytes={}",
                format, blocks, entry, HISTORY * entry, blocks.min(HISTORY) * entry);
        }
    }
}

#[test]
#[ignore = "isolated synthetic small chunk benchmark; baseline only"]
fn bcpack_history_native_small_chunk_timing() {
    let t = Tables::parse(&tables()).unwrap();
    // Reuse the same three valid synthetic layouts as bcpack_throughput.
    let cases: [(u8, &[u8], usize, usize); 3] = [
        (1, &[7, 7, 4, 5, 4, 4, 5, 4, 7, 7, 7, 7], 1, 8),
        (4, &BC4_LANES, 1, 8),
        (7, &[3, 3, 7, 7, 7, 7, 7, 6, 6, 4, 5, 7, 7, 7, 7, 4], 2, 16),
    ];
    for (bc, widths, per, block) in cases {
        for blocks in [1usize, 4, 16, 64, 256, 1024] {
            let records = random_records(widths, per, blocks, bc == 7);
            let src = stream(&t, widths, per, &records);
            let mut expected = vec![0u8; blocks * block];
            decode(bc, &src, &mut expected, &t).unwrap();
            let mut out = vec![0u8; expected.len()];
            let mut work = vec![0u8; blocks * widths.len() * per];
            // Verify actual lane output before any timing. No change to
            // the two-phase decoder or its failure semantics.
            let mut next = src.iter().copied();
            lanes(&t, widths, per, blocks, |_| next.next(), &mut work).unwrap();
            assert_eq!(work, records.concat());
            for _ in 0..8 {
                decode(bc, &src, &mut out, &t).unwrap();
            }
            let calls = 64usize;
            for repeat in 0..3 {
                out.fill(0xA5);
                let start = std::time::Instant::now();
                for _ in 0..calls {
                    decode(bc, std::hint::black_box(&src),
                        std::hint::black_box(&mut out), &t).unwrap();
                    std::hint::black_box(&out);
                }
                let elapsed = start.elapsed().as_nanos();
                assert_eq!(out, expected);
                println!("bcpack_small_chunk bc={} blocks={} src_bytes={} dst_bytes={} records_bytes={} repeat={} calls={} elapsed_ns={}",
                    bc, blocks, src.len(), out.len(), work.len(), repeat, calls, elapsed);
            }
        }
    }
}
