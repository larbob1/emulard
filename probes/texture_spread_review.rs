#[cfg(test)]
mod ai0_texture_spread_review {
    use super::*;

    #[test]
    fn actual_pattern_axis_table_parity() {
        for kind in 0..3 {
            for element_log2 in 0..5 {
                for block_log2 in [8, 12, 16] {
                    for bits in pattern(kind, element_log2, block_log2) {
                        let reference = spread(&bits);
                        let candidate = spread_incremental(&bits);
                        assert_eq!(candidate, reference);
                        assert_eq!(candidate.len(), 1usize << bits.len());
                        assert_eq!(candidate[0], 0);
                    }
                }
            }
        }
    }
}
