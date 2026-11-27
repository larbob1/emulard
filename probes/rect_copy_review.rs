#[cfg(test)]
mod ai0_rect_copy_review {
    use super::*;

    #[test]
    fn actual_rectangle_expansion_parity() {
        let formats = [2, 6, 16, 41, 10, 34, 54, 11, 35, 28, 29, 87, 91, 999];
        for stride in [1usize, 2, 3, 4, 7, 8, 12, 16, 31, 64] {
            for rects in [0usize, 1, 2, 9] {
                // Finite inputs for the float formats, varied bytes for all others.
                let src: Vec<u8> = (0..3 * stride * rects + 1)
                    .map(|i| (i.wrapping_mul(37) & 63) as u8).collect();
                for &format in &formats {
                    for offset in [0u32, 1, (stride - 1) as u32, stride as u32, u32::MAX] {
                        // Preserve ordered, potentially overlapping component writes.
                        let elements = [(0, 28), (offset, format), (0, 54)];
                        for output_rects in [rects, rects.saturating_sub(1), rects + 1] {
                            let mut expected = vec![0xcd; 6 * stride * output_rects + 1];
                            let mut actual = expected.clone();
                            expand_rects(&src, &mut expected, stride, &elements);
                            expand_rects_coalesced(&src, &mut actual, stride, &elements);
                            assert_eq!(actual, expected, "stride={stride} rects={rects} format={format} offset={offset}");
                        }
                    }
                }
            }
        }
    }
}
