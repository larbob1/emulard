// Review-only, std-only arithmetic fixture.
// Finding: trustno1-coder/VIctory-NVIDIA aec85efb10777281b1f3dc586239d113640ed249
// (GPL-3.0-or-later; original fix attributed to lichenlang89).
// Independently authored candidate and tests; no D3D objects are made here.

fn ai0_raw_view_bounds(width: u64, offset: u64, len: u64) -> Option<(u64, u32)> {
    if offset % 16 != 0 {
        return None;
    }
    let remaining = width.checked_sub(offset)?;
    let available = remaining / 4;
    if available == 0 {
        return None;
    }
    // Preserve the old minimum of one dword, but only within the actual buffer.
    let wanted = (len / 4).max(1);
    let count = available.min(wanted).min(u64::from(u32::MAX));
    Some((offset / 4, count as u32))
}

#[cfg(test)]
mod ai0_raw_view_bounds_tests {
    use super::ai0_raw_view_bounds as bounds;

    #[test]
    fn explicit_boundaries() {
        let cases = [
            (1024, 0, 256, Some((0, 64))),
            (1024, 768, 512, Some((192, 64))),
            (100, 96, 16, Some((24, 1))),
            (100, 112, 16, None),
            (100, 100, 16, None),
            (99, 96, 4, None),
            (0, 0, 4, None),
            (3, 0, 4, None),
            (16, 0, 0, Some((0, 1))),
            (16, 0, 1, Some((0, 1))),
            (16, 0, 3, Some((0, 1))),
            (16, 0, 5, Some((0, 1))),
            (1024, 4, 64, None),
            (1024, 8, 64, None),
            (1024, 12, 64, None),
            (1024, 1024, 64, None),
            (1024, u64::MAX, 64, None),
            (1024, u64::MAX - 15, 64, None),
            (u64::MAX, 0, u64::MAX, Some((0, u32::MAX))),
            (u64::MAX, u64::MAX - 15, u64::MAX,
                Some(((u64::MAX - 15) / 4, 3))),
        ];
        for (width, offset, len, expected) in cases {
            assert_eq!(bounds(width, offset, len), expected,
                "width={width} offset={offset} len={len}");
        }
    }

    #[test]
    fn first_element_stays_64_bit() {
        let start = (u64::from(u32::MAX) + 5) * 4;
        assert_eq!(start % 16, 0);
        assert_eq!(bounds(start + 64, start, 64),
            Some((u64::from(u32::MAX) + 5, 16)));
    }

    // Oracle uses widened byte endpoints rather than subtracting u64 ranges.
    fn oracle(width: u64, offset: u64, len: u64) -> Option<(u64, u32)> {
        let start = u128::from(offset);
        let end = u128::from(width);
        if offset % 16 != 0 || start + 4 > end {
            return None;
        }
        let requested_end = start + (u128::from(len) / 4).max(1) * 4;
        let count_end = start + u128::from(u32::MAX) * 4;
        let count = (end.min(requested_end).min(count_end) - start) / 4;
        Some((offset / 4, u32::try_from(count).unwrap()))
    }

    #[test]
    fn widened_oracle_matrix() {
        let widths = [0, 1, 3, 4, 15, 16, 17, 99, 100, 1024, 1 << 40, u64::MAX];
        let offsets = [0, 1, 4, 12, 16, 48, 96, 112, 1024, 1 << 40,
            u64::MAX - 15, u64::MAX];
        let lens = [0, 1, 3, 4, 5, 16, 512, 1 << 40, u64::MAX];
        for width in widths {
            for offset in offsets {
                for len in lens {
                    let got = bounds(width, offset, len);
                    assert_eq!(got, oracle(width, offset, len),
                        "width={width} offset={offset} len={len}");
                    if let Some((first, count)) = got {
                        assert_eq!(first * 4, offset);
                        assert!(count > 0);
                        assert!(u128::from(first) * 4 + u128::from(count) * 4
                            <= u128::from(width));
                    }
                }
            }
        }
    }
}
