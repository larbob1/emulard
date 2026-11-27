#[cfg(test)]
mod ai0_detile_last_run_review {
    use super::*;

    fn check(desc: Desc) {
        let layout = Layout::new(&desc).unwrap();
        let tiled: Vec<u8> = (0..layout.size)
            .map(|i| (i.wrapping_mul(0x9e3779b9) >> 24) as u8)
            .collect();
        let slices = if desc.dimension == Dimension::Tex3d { 1 } else { desc.depth };
        for slice in 0..slices {
            for mip in 0..desc.mips {
                let m = &layout.mips[mip as usize];
                let active = m.width as usize * desc.element_bytes as usize;
                let row = active + 5;
                let plane = row * m.height as usize + 7;
                let len = plane * m.depth as usize;
                let mut expected = vec![0xcc; len];
                let mut actual = expected.clone();
                let baseline = layout.detile(&tiled, mip, slice, &mut expected, row, plane);
                let candidate = layout.walk_last_inline::<true>(&tiled, &mut actual, mip, slice, row, plane);
                assert_eq!(baseline, candidate);
                assert!(candidate.is_ok());
                assert_eq!(expected, actual);
                let mut a = vec![0xbb; tiled.len()];
                let mut b = a.clone();
                let baseline = layout.tile(&mut a, mip, slice, &expected, row, plane);
                let candidate = layout.walk_last_inline::<false>(&expected, &mut b, mip, slice, row, plane);
                assert_eq!(baseline, candidate);
                assert!(candidate.is_ok());
                assert_eq!(a, b);
                // Too-small input/output and row-pitch failure leave sentinels unchanged.
                for (src, bad_row) in [(&tiled[..tiled.len()-1], row), (&tiled[..], active-1)] {
                    let mut x = vec![0x55; len];
                    let mut y = x.clone();
                    let e = layout.detile(src, mip, slice, &mut x, bad_row, plane);
                    let f = layout.walk_last_inline::<true>(src, &mut y, mip, slice, bad_row, plane);
                    assert!(e.is_err());
                    assert_eq!(e, f);
                    assert_eq!(x, y);
                }
            }
        }
    }

    #[test]
    fn actual_layout_copy_parity() {
        for swizzle in [Swizzle::LINEAR, Swizzle::SW_256B_S, Swizzle::SW_4KB_D, Swizzle::SW_64KB_S] {
            for element_bytes in [1, 2, 4, 8, 16] {
                for (width, height, mips) in [(1, 1, 1), (3, 5, 1), (73, 39, 6)] {
                    check(Desc { dimension: Dimension::Tex2d, width, height,
                        depth: 2, mips, element_bytes, block: 1, samples: 1, swizzle });
                }
            }
        }
        check(Desc { dimension: Dimension::Tex3d, width: 17, height: 9,
            depth: 4, mips: 4, element_bytes: 4, block: 1, samples: 1,
            swizzle: Swizzle::SW_4KB_S });
    }
}
