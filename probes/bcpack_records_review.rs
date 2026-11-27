// SPDX-License-Identifier: GPL-3.0-or-later
// Test-only BCPack records fixture. Candidate clone is generated from
// pinned decode, preserving every step except small record storage.
// No unsafe/uninitialized memory, retained cache, or production hook.

fn records_review_layouts() -> [(u8, &'static [u8], usize, usize); 6] {
    [
        (1, &[7, 7, 4, 5, 4, 4, 5, 4, 7, 7, 7, 7], 1, 8),
        (3, &[3, 3, 7, 5, 5, 5, 5, 4, 5, 4, 7, 7], 2, 16),
        (4, &BC4_LANES, 1, 8),
        (5, &[3, 3, 7, 7, 5, 5, 5, 5, 5, 5, 5, 5], 2, 16),
        (6, &[3, 3, 7, 7, 7, 4, 4, 4, 5, 5, 5, 7, 7, 7, 7, 4], 2, 16),
        (7, &[3, 3, 7, 7, 7, 7, 7, 6, 6, 4, 5, 7, 7, 7, 7, 4], 2, 16),
    ]
}

fn records_review_input(bc: u8, widths: &[u8], per: usize, blocks: usize) -> Vec<Vec<u8>> {
    let mut records = random_records(widths, per, blocks, bc == 7);
    if bc == 6 {
        for r in &mut records {
            r[30] = 10; // valid one-subset mode 11
        }
    }
    records
}

fn records_review_pair(bc: u8, src: &[u8], len: usize, t: &Tables)
    -> (Result<(), Error>, Vec<u8>) {
    let mut baseline = vec![0xA5; len + 16];
    let mut candidate = baseline.clone();
    let a = decode(bc, src, &mut baseline[8..8 + len], t);
    let b = bcpack_records_candidate(bc, src, &mut candidate[8..8 + len], t);
    assert_eq!(a, b, "format {bc}, input {}, output {len}", src.len());
    assert_eq!(baseline, candidate, "format {bc}, input {}, output {len}", src.len());
    assert_eq!(&candidate[..8], &[0xA5; 8]);
    assert_eq!(&candidate[8 + len..], &[0xA5; 8]);
    (a, candidate[8..8 + len].to_vec())
}

#[test]
#[ignore = "isolated native record storage candidate parity"]
fn bcpack_records_native_all_layouts() {
    let t = Tables::parse(&tables()).unwrap();
    for (bc, widths, per, block) in records_review_layouts() {
        let stride = widths.len() * per;
        let edge = 4096 / stride;
        for blocks in [1, 2, edge - 1, edge, edge + 1, 257, 1024] {
            let records = records_review_input(bc, widths, per, blocks);
            let src = stream(&t, widths, per, &records);
            // Independent lane record check before testing output equality.
            let mut got = vec![0xA5; blocks * stride];
            let mut next = src.iter().copied();
            lanes(&t, widths, per, blocks, |_| next.next(), &mut got).unwrap();
            assert_eq!(got, records.concat());
            assert_eq!(records_review_pair(bc, &src, blocks * block, &t).0, Ok(()));
            let mut trailing = src.clone();
            trailing.extend_from_slice(&[0x12, 0x34]);
            assert_eq!(records_review_pair(bc, &trailing, blocks * block, &t).0, Ok(()));
            // Truncation need not always be invalid; compare the exact
            // existing result and complete destination, not assumptions.
            records_review_pair(bc, &src[..src.len() / 2], blocks * block, &t);
            let (err, unchanged) = records_review_pair(bc, &[], blocks * block, &t);
            assert!(err.is_err());
            assert!(unchanged.iter().all(|&v| v == 0xA5));
        }
        assert!(records_review_pair(bc, &[], 0, &t).0.is_err());
        assert!(records_review_pair(bc, &[], block - 1, &t).0.is_err());
    }
    assert_eq!(records_review_pair(2, &[], 16, &t).0, Err(Error("unsupported BC format")));
}

#[test]
#[ignore = "isolated native error ordering and partial output"]
fn bcpack_records_native_late_error() {
    let t = Tables::parse(&tables()).unwrap();
    for (bc, widths, per, block) in records_review_layouts() {
        if bc != 6 && bc != 7 { continue; }
        // Test both sides of the record-size cutoff. An invalid last block
        // is a block-stage error, so earlier output must remain identical.
        for blocks in [2usize, 129] {
            let mut records = records_review_input(bc, widths, per, blocks);
            let valid = stream(&t, widths, per, &records);
            let (result, want) = records_review_pair(bc, &valid, blocks * block, &t);
            assert_eq!(result, Ok(()));
            let last = records.last_mut().unwrap();
            last[30] = if bc == 6 { 14 } else { 1 };
            let invalid = stream(&t, widths, per, &records);
            let (result, got) = records_review_pair(bc, &invalid, blocks * block, &t);
            assert_eq!(result, Err(Error(if bc == 6 {
                "BC6H mode out of range"
            } else {
                "unused BC7 control code"
            })));
            let prefix = (blocks - 1) * block;
            assert_eq!(&got[..prefix], &want[..prefix]);
            assert_eq!(&got[prefix..], &[0xA5; 16]);
            assert_eq!(records_review_pair(bc, &valid, blocks * block, &t).0, Ok(()));
        }
    }
}
