// SPDX-License-Identifier: MIT
#[cfg(test)]
#[path = "baseline.rs"]
mod baseline;

#[cfg(test)]
mod ai1_composition {
    use super::*;

    fn check(desc: Desc) {
        let original = baseline::Desc {
            dimension: match desc.dimension {
                Dimension::Tex1d => baseline::Dimension::Tex1d,
                Dimension::Tex2d => baseline::Dimension::Tex2d,
                Dimension::Tex3d => baseline::Dimension::Tex3d,
            },
            width: desc.width, height: desc.height, depth: desc.depth,
            mips: desc.mips, element_bytes: desc.element_bytes,
            block: desc.block, samples: desc.samples,
            swizzle: baseline::Swizzle(desc.swizzle.0),
        };
        let a = baseline::Layout::new(&original);
        let b = Layout::new(&desc);
        assert_eq!(a.is_ok(), b.is_ok());
        let (a,b) = match (a,b) {
            (Ok(a), Ok(b)) => (a,b),
            (Err(a), Err(b)) => {
                assert_eq!(format!("{a:?}"), format!("{b:?}"));
                return;
            }
            _ => unreachable!(),
        };
        assert_eq!((a.size,a.alignment,a.slice_size,a.slices,a.block,a.thick,a.first_tail_mip),
                   (b.size,b.alignment,b.slice_size,b.slices,b.block,b.thick,b.first_tail_mip));
        assert_eq!(a.addressable(), b.addressable());
        let tiled: Vec<u8> = (0..a.size).map(|i| (i.wrapping_mul(0x9e3779b9) >> 24) as u8).collect();
        let n = desc.element_bytes as usize;
        let slices = if desc.dimension == Dimension::Tex3d { 1 } else { desc.depth };
        for mip in 0..desc.mips {
            let m = &b.mips[mip as usize];
            let row = m.width as usize * n + 5;
            let plane = row * m.height as usize + 7;
            let len = plane * m.depth as usize;
            for slice in 0..slices {
                let mut x = vec![0xcc; len];
                let mut y = x.clone();
                let ar = a.detile(&tiled,mip,slice,&mut x,row,plane);
                let br = b.detile(&tiled,mip,slice,&mut y,row,plane);
                assert_eq!(format!("{ar:?}"),format!("{br:?}"));
                assert_eq!(x,y);
                if !b.addressable() {
                    assert!(br.is_err());
                    assert!(y.iter().all(|&v| v == 0xcc));
                    continue;
                }
                assert!(br.is_ok());
                // Coordinate-by-coordinate oracle, independent of the run
                // planner. Addresses come from the unmodified baseline.
                let mut expected = vec![0xcc;len];
                let mut expected_tiled = vec![0xbb;tiled.len()];
                for z in 0..m.depth {
                    for yy in 0..m.height {
                        for xx in 0..m.width {
                            let zz = if desc.dimension == Dimension::Tex3d { z } else { slice };
                            let at = a.offset(mip,xx,yy,zz).unwrap() as usize;
                            assert_eq!(b.offset(mip,xx,yy,zz).unwrap() as usize,at);
                            let linear = z as usize * plane + yy as usize * row + xx as usize * n;
                            expected[linear..linear+n].copy_from_slice(&tiled[at..at+n]);
                            expected_tiled[at..at+n].copy_from_slice(&x[linear..linear+n]);
                        }
                    }
                }
                assert_eq!(y,expected);
                let mut ta = vec![0xbb;tiled.len()];
                let mut tb = ta.clone();
                assert!(a.tile(&mut ta,mip,slice,&x,row,plane).is_ok());
                assert!(b.tile(&mut tb,mip,slice,&y,row,plane).is_ok());
                assert_eq!(ta,expected_tiled);
                assert_eq!(tb,expected_tiled);
                // Every rejection must preserve the whole output sentinel.
                for (bad_mip,bad_slice,bad_row,bad_plane,src_len,dst_len) in [
                    (desc.mips,slice,row,plane,tiled.len(),len),
                    (mip,slices,row,plane,tiled.len(),len),
                    (mip,slice,m.width as usize*n-1,plane,tiled.len(),len),
                    (mip,slice,row,plane,tiled.len()-1,len),
                    (mip,slice,row,plane,tiled.len(),0),
                ] {
                    let mut da = vec![0x55;dst_len];
                    let mut db = da.clone();
                    let ra = a.detile(&tiled[..src_len],bad_mip,bad_slice,&mut da,bad_row,bad_plane);
                    let rb = b.detile(&tiled[..src_len],bad_mip,bad_slice,&mut db,bad_row,bad_plane);
                    assert!(ra.is_err() && rb.is_err());
                    assert_eq!(format!("{ra:?}"),format!("{rb:?}"));
                    assert_eq!(da,db);
                    assert!(db.iter().all(|&v|v==0x55));
                }
            }
        }
    }

    #[test]
    fn actual_combined_layout_copy_and_refusal_parity() {
        for swizzle in [Swizzle::LINEAR,Swizzle::SW_256B_S,Swizzle::SW_256B_D,
                        Swizzle::SW_4KB_S,Swizzle::SW_4KB_D,Swizzle::SW_64KB_S,
                        Swizzle::SW_64KB_D,Swizzle::SW_4KB_S_X] {
            for element_bytes in [1,2,4,8,16] {
                for (width,height,mips) in [(1,1,1),(3,5,1),(73,39,6)] {
                    check(Desc{dimension:Dimension::Tex2d,width,height,depth:2,mips,
                               element_bytes,block:1,samples:1,swizzle});
                }
            }
            for element_bytes in [8,16] {
                check(Desc{dimension:Dimension::Tex2d,width:77,height:41,depth:2,mips:6,
                           element_bytes,block:4,samples:1,swizzle});
            }
        }
        for swizzle in [Swizzle::LINEAR,Swizzle::SW_4KB_S,Swizzle::SW_64KB_S] {
            check(Desc{dimension:Dimension::Tex3d,width:17,height:9,depth:4,mips:4,
                       element_bytes:4,block:1,samples:1,swizzle});
        }
        check(Desc{dimension:Dimension::Tex2d,width:0,height:1,depth:1,mips:1,
                   element_bytes:4,block:1,samples:1,swizzle:Swizzle::LINEAR});
    }
}
