
    // Review-only fixture, independently authored from the source finding
    // fxceless/victory-fork 81d54b06f728ade90e450acb67e8c2e0735b024d
    // (PiloteCode #1407; GPL-3.0-or-later).
    #[test]
    fn ai0_parallel_compare_exact_changed_piece_ranges() {
        const PIECE: usize = 64 << 10;
        const LEN: usize = (32 << 20) + 513;
        // The resource is only an owned handle for Shadow::new; the
        // comparison reads the privately owned CPU vectors, not the GPU.
        let buffer = warp_buffer().expect("WARP required for this fixture");
        for (skew, from) in [(PIECE / 2, 0usize), (PIECE - 1, 1),
                             (0, 17), (17, PIECE + 3)] {
            let start = (8 * PIECE + skew) as u64;
            let to = LEN;
            let before = vec![0u8; to - from];
            let mut now = vec![0u8; LEN];
            let boundary = (from + PIECE).min(to - 1);
            let changed = [from, from + 1, boundary - 1, boundary,
                           (16 << 20) - 1, 16 << 20, to - 1];
            for &at in &changed { now[at] = 0x5a; }
            // Independent oracle enumerates each changed byte's absolute
            // piece, clips both endpoints to the requested interval,
            // then sorts and deduplicates the exact ranges.
            let mut expected: Vec<(usize, usize)> = changed.iter().map(|&at| {
                let absolute = start as usize + at;
                let lo = (absolute / PIECE) * PIECE;
                let hi = lo + PIECE;
                let a = lo.saturating_sub(start as usize).max(from);
                let b = (hi - start as usize).min(to);
                (a, b - a)
            }).collect();
            expected.sort_unstable();
            expected.dedup();
            let shadow = Shadow::new(buffer.clone(), now.as_mut_ptr(),
                                     0, start, LEN as u64);
            assert_eq!(shadow.differing(from, to, &before), expected,
                       "skew={skew} from={from}");
            drop(shadow);
        }
    }
