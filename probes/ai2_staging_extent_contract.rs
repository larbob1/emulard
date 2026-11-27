// SPDX-License-Identifier: GPL-3.0-or-later
// Standalone proposal model only. Not linked to victory-gpu.
#[derive(Clone, Copy, Debug)]
struct Footprint {
    offset: u64,
    pitch: u64,
    rows: u64,
    depth: u64,
    active_row: u64,
}

#[derive(Debug, PartialEq, Eq)]
struct Extent {
    logical: u64,
    required: u64,
    rounded: u64,
}

fn plan(total: u64, expected_count: usize, footprints: &[Footprint]) -> Option<Extent> {
    if total == 0 || total == u64::MAX || expected_count == 0
        || footprints.len() != expected_count {
        return None;
    }
    let mut previous_full = 0;
    for f in footprints {
        if f.offset % 512 != 0 || f.pitch % 256 != 0
            || f.active_row == 0 || f.active_row > f.pitch
            || f.rows == 0 || f.depth == 0 || f.offset < previous_full {
            return None;
        }
        let count = f.rows.checked_mul(f.depth)?;
        let active_end = f.offset.checked_add(f.pitch.checked_mul(count - 1)?)?
            .checked_add(f.active_row)?;
        let full_end = f.offset.checked_add(f.pitch.checked_mul(count)?)?;
        if active_end > total || full_end > isize::MAX as u64 {
            return None;
        }
        previous_full = full_end;
    }
    let required = total.max(previous_full);
    if required > isize::MAX as u64 { return None; }
    let rounded = required.max(64 << 10).checked_next_power_of_two()?;
    Some(Extent { logical: total, required, rounded })
}

fn width(p: &Extent, pool: bool) -> u64 {
    if pool && p.rounded <= 8 << 20 { p.rounded } else { p.required }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn f(offset: u64, pitch: u64, rows: u64, depth: u64, active_row: u64) -> Footprint {
        Footprint { offset, pitch, rows, depth, active_row }
    }

    #[test]
    fn unaligned_and_aligned_final_rows() {
        let p = plan(260, 1, &[f(0,256,2,1,4)]).unwrap();
        assert_eq!(p, Extent { logical:260, required:512, rounded:65536 });
        assert_eq!(width(&p,false),512);
        assert_eq!(width(&p,true),65536);
        assert_eq!(plan(512,1,&[f(0,256,2,1,256)]).unwrap().required,512);
    }

    #[test]
    fn array_and_depth_extents() {
        let p = plan(1284,3,&[f(0,256,2,1,4),f(512,256,2,1,4),f(1024,256,2,1,4)]).unwrap();
        assert_eq!(p.required,1536);
        assert_eq!(plan(2824,1,&[f(0,256,4,3,8)]).unwrap().required,3072);
    }

    #[test]
    fn oversize_remains_unpooled_even_with_pool_enabled() {
        let p = plan(9*1024*1024-252,1,&[f(0,256,36864,1,4)]).unwrap();
        assert_eq!(p.required,9*1024*1024);
        assert_eq!(width(&p,true),p.required);
        assert_eq!(width(&p,false),p.required);
    }

    #[test]
    fn rejects_invalid_or_truncated_metadata() {
        for (total,count,items) in [
            (0,1,vec![f(0,256,2,1,4)]),
            (u64::MAX,1,vec![f(0,256,2,1,4)]),
            (259,1,vec![f(0,256,2,1,4)]),
            (260,2,vec![f(0,256,2,1,4)]),
            (260,1,vec![f(0,0,2,1,4)]),
            (260,1,vec![f(0,256,0,1,4)]),
            (260,1,vec![f(0,256,2,0,4)]),
            (260,1,vec![f(0,256,2,1,257)]),
            (260,1,vec![f(1,256,2,1,4)]),
            (260,1,vec![f(0,255,2,1,4)]),
            (1024,2,vec![f(0,256,3,1,4),f(512,256,2,1,4)]),
            (1024,1,vec![f(0,256,u64::MAX,2,4)]),
        ] {
            assert!(plan(total,count,&items).is_none());
        }
        assert!(plan(1,0,&[]).is_none());
    }

    #[test]
    fn all_padding_writes_fit_proposed_width() {
        for pitch in [256,512,1024] {
            for rows in [1,2,3,9] {
                for depth in [1,2,4] {
                    for active in [1,pitch/2,pitch] {
                        let total = pitch*(rows*depth-1)+active;
                        let p = plan(total,1,&[f(0,pitch,rows,depth,active)]).unwrap();
                        assert_eq!(p.required,pitch*rows*depth);
                        for pool in [false,true] {
                            assert!(width(&p,pool)>=p.required);
                        }
                    }
                }
            }
        }
    }
}
