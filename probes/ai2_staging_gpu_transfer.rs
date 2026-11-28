// SPDX-License-Identifier: GPL-3.0-or-later
// Isolated candidate-only native transfer test, never shipped.
#[cfg(all(test, feature = "diagnostics"))]
mod ai2_staging_gpu_transfer {
    use super::*;
    use std::sync::atomic::{AtomicBool, AtomicU32, AtomicU64, Ordering::Relaxed};
    use victory_formats::texture::{Desc, Dimension, Layout, Swizzle};
    use windows::core::Interface;
    use windows::Win32::Foundation::{CloseHandle, WAIT_OBJECT_0};
    use windows::Win32::Graphics::Dxgi::{IDXGIAdapter1, DXGI_ADAPTER_FLAG_SOFTWARE};
    use windows::Win32::Graphics::Dxgi::Common::{
        DXGI_FORMAT, DXGI_FORMAT_R8_UNORM, DXGI_FORMAT_R8G8B8A8_UNORM,
        DXGI_FORMAT_BC1_UNORM, DXGI_SAMPLE_DESC,
    };
    use windows::Win32::System::Threading::{CreateEventW, WaitForSingleObject};

    fn uncertain(reason: &str) -> ! {
        eprintln!("staging GPU transfer completion uncertain: {reason}");
        std::process::abort()
    }

    fn resource(device: &ID3D12Device, desc: &D3D12_RESOURCE_DESC,
                heap: D3D12_HEAP_TYPE, state: D3D12_RESOURCE_STATES) -> ID3D12Resource {
        let heap = D3D12_HEAP_PROPERTIES {
            Type: heap, CreationNodeMask: 1, VisibleNodeMask: 1, ..Default::default()
        };
        let mut result: Option<ID3D12Resource> = None;
        unsafe {
            device.CreateCommittedResource(&heap, D3D12_HEAP_FLAG_NONE, desc,
                state, None, &mut result).expect("owned transfer resource");
        }
        result.expect("resource")
    }

    fn placed(buffer: &ID3D12Resource, fp: D3D12_PLACED_SUBRESOURCE_FOOTPRINT)
        -> D3D12_TEXTURE_COPY_LOCATION {
        D3D12_TEXTURE_COPY_LOCATION {
            // Borrowed pointer; the location's ManuallyDrop field does not own a ref.
            pResource: unsafe { std::mem::transmute_copy(buffer) },
            Type: D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT,
            Anonymous: D3D12_TEXTURE_COPY_LOCATION_0 { PlacedFootprint: fp },
        }
    }

    fn subresource(texture: &ID3D12Resource, i: u32) -> D3D12_TEXTURE_COPY_LOCATION {
        D3D12_TEXTURE_COPY_LOCATION {
            pResource: unsafe { std::mem::transmute_copy(texture) },
            Type: D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX,
            Anonymous: D3D12_TEXTURE_COPY_LOCATION_0 { SubresourceIndex: i },
        }
    }

    // Independently specified bytes, not derived from detile or GPU results.
    fn pattern(case: usize, slice: usize, mip: usize, z: usize, y: usize, x: usize) -> u8 {
        ((case*41 + slice*67 + mip*53 + z*29 + y*17 + x*3) % 251) as u8
    }

    struct Case {
        dim: Dimension, w: u32, h: u32, depth: u32, mips: u32,
        elem: u32, block: u32, format: DXGI_FORMAT, logical: u64, full: u64,
    }

    #[test]
    fn actual_corrected_staging_gpu_transfer() {
        let mode = std::env::var("AI2_EXPECT_POOL").expect("explicit pool mode");
        assert!(mode == "0" || mode == "1");
        let pool = mode == "1";
        assert_eq!(std::env::var("VICTORY_STAGING_POOL").as_deref(), Ok(mode.as_str()));
        assert_eq!(std::env::var("VICTORY_D3D12_WARP").as_deref(), Ok("1"));
        assert_eq!(staging_pool(), pool);
        let adapter = crate::host::warp_adapter().expect("strict WARP");
        let desc = unsafe { adapter.cast::<IDXGIAdapter1>().unwrap().GetDesc1().unwrap() };
        assert_ne!(desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE.0 as u32, 0);
        let h = host().expect("runtime host");
        let device = &h.device;
        let actual = unsafe { device.GetAdapterLuid() };
        let wanted = desc.AdapterLuid;
        assert_eq!((actual.HighPart,actual.LowPart),(wanted.HighPart,wanted.LowPart));
        eprintln!("transfer_adapter actual_high={} actual_low={} warp_high={} warp_low={} software=1",
            actual.HighPart,actual.LowPart,wanted.HighPart,wanted.LowPart);
        let cases = [
            Case {dim:Dimension::Tex2d,w:4,h:2,depth:1,mips:1,elem:1,block:1,format:DXGI_FORMAT_R8_UNORM,logical:260,full:512},
            Case {dim:Dimension::Tex2d,w:64,h:2,depth:1,mips:1,elem:4,block:1,format:DXGI_FORMAT_R8G8B8A8_UNORM,logical:512,full:512},
            Case {dim:Dimension::Tex2d,w:8,h:4,depth:2,mips:3,elem:1,block:1,format:DXGI_FORMAT_R8_UNORM,logical:3586,full:3840},
            Case {dim:Dimension::Tex3d,w:8,h:4,depth:3,mips:1,elem:1,block:1,format:DXGI_FORMAT_R8_UNORM,logical:2824,full:3072},
            Case {dim:Dimension::Tex2d,w:8,h:8,depth:1,mips:1,elem:8,block:4,format:DXGI_FORMAT_BC1_UNORM,logical:272,full:512},
        ];
        let old_count = STAGED[0].load(Relaxed);
        let old_bytes = STAGED[1].load(Relaxed);
        let mut previous = None;
        for (case, c) in cases.iter().enumerate() {
            let volume = c.dim == Dimension::Tex3d;
            let n = if volume { c.mips } else { c.mips*c.depth };
            let layout = Layout::new(&Desc { dimension:c.dim, width:c.w,height:c.h,
                depth:c.depth,mips:c.mips,element_bytes:c.elem,block:c.block,
                samples:1,swizzle:Swizzle::LINEAR }).unwrap();
            let td = D3D12_RESOURCE_DESC {
                Dimension: if volume { D3D12_RESOURCE_DIMENSION_TEXTURE3D } else { D3D12_RESOURCE_DIMENSION_TEXTURE2D },
                Width:u64::from(c.w), Height:c.h, DepthOrArraySize:c.depth as u16,
                MipLevels:c.mips as u16, Format:c.format,
                SampleDesc:DXGI_SAMPLE_DESC {Count:1,Quality:0},
                Layout:D3D12_TEXTURE_LAYOUT_UNKNOWN, ..Default::default()
            };
            let mut fp = vec![D3D12_PLACED_SUBRESOURCE_FOOTPRINT::default();n as usize];
            let mut rows = vec![0u32;n as usize];
            let mut active = vec![0u64;n as usize];
            let mut total=0u64;
            unsafe {
                device.GetCopyableFootprints(&td,0,n,0,Some(fp.as_mut_ptr()),
                    Some(rows.as_mut_ptr()),Some(active.as_mut_ptr()),Some(&mut total));
            }
            assert_eq!(total,c.logical);
            let required=staging_extent(total,&fp,&rows,&active,&layout,c.mips).unwrap();
            assert_eq!(required,c.full);
            let (buffer,data,pooled)=staging_buffer(h,required).expect("corrected allocation");
            let width=unsafe { buffer.GetDesc().Width };
            assert_eq!(width,if pool {65536} else {required});
            assert_eq!(pooled,if pool {65536} else {0});
            assert!(staging_mapping_fits(&buffer,data,required,width));
            if pool && case>0 { assert_eq!(previous,Some(data as usize)); }
            previous=Some(data as usize);

            // Construct source independently of Layout::tile and Layout::offset.
            // This small linear case set has 256-byte console row pitch at every mip.
            let mut offsets=vec![0usize;c.mips as usize];
            let mut chain=0usize;
            for m in (0..c.mips as usize).rev() {
                offsets[m]=chain;
                let padded_rows=c.h.div_ceil(c.block).div_ceil(1u32<<m) as usize;
                let padded_width=c.w.div_ceil(c.block).div_ceil(1u32<<m) as usize*c.elem as usize;
                assert!(padded_width<=256);
                chain+=256*padded_rows;
            }
            assert_eq!(layout.size as usize,chain*c.depth as usize);
            let mut src=vec![0xcc;chain*c.depth as usize];
            let mut expected=vec![0xa5;required as usize];
            let mut active_offsets=Vec::new();
            for i in 0..n as usize {
                let mip=i%c.mips as usize;
                let slice=i/c.mips as usize;
                let row=(c.w>>mip).max(1).div_ceil(c.block) as usize*c.elem as usize;
                let height=(c.h>>mip).max(1).div_ceil(c.block) as usize;
                let depth=if volume {(c.depth>>mip).max(1) as usize} else {1};
                assert_eq!((active[i] as usize,rows[i] as usize,fp[i].Footprint.Depth as usize),(row,height,depth));
                let pitch=fp[i].Footprint.RowPitch as usize;
                for z in 0..depth {
                    for y in 0..height {
                        for x in 0..row {
                            let v=pattern(case,slice,mip,z,y,x);
                            let from=(if volume {z} else {slice})*chain+offsets[mip]+y*256+x;
                            let to=fp[i].Offset as usize+z*pitch*height+y*pitch+x;
                            src[from]=v;
                            expected[to]=v;
                            active_offsets.push(to);
                        }
                    }
                }
            }
            unsafe { std::ptr::write_bytes(data,0xa5,width as usize); }
            STAGED[0].fetch_add(1,Relaxed);
            STAGED[1].fetch_add(total,Relaxed);
            let staging=Staging {
                buffer,size:required,data,footprints:fp,rows,layout,mips:c.mips,
                bytes:total,memory:src.as_ptr(),last:Mutex::default(),dirty:AtomicBool::new(false),
                uploaded:AtomicBool::new(false),used:AtomicU64::new(0),on_demand:false,
                detiled:AtomicU32::new(0),judged:[const {AtomicU64::new(0)};2],
                waiting:AtomicU64::new(0),pooled,
            };
            staging.detile(&src);
            let mapped=unsafe { std::slice::from_raw_parts(data,width as usize) };
            assert_eq!(&mapped[..required as usize],expected.as_slice(),"detile including padding");
            assert!(mapped[required as usize..].iter().all(|&b|b==0xa5));

            // Independent queue on the SAME device as actual staging resource.
            let texture=resource(device,&td,D3D12_HEAP_TYPE_DEFAULT,D3D12_RESOURCE_STATE_COPY_DEST);
            let bd=D3D12_RESOURCE_DESC {
                Dimension:D3D12_RESOURCE_DIMENSION_BUFFER,Width:required,Height:1,
                DepthOrArraySize:1,MipLevels:1,SampleDesc:DXGI_SAMPLE_DESC{Count:1,Quality:0},
                Layout:D3D12_TEXTURE_LAYOUT_ROW_MAJOR,..Default::default()
            };
            let readback=resource(device,&bd,D3D12_HEAP_TYPE_READBACK,D3D12_RESOURCE_STATE_COPY_DEST);
            assert_eq!(unsafe {readback.GetDesc().Width},required);
            let queue:ID3D12CommandQueue=unsafe {
                device.CreateCommandQueue(&D3D12_COMMAND_QUEUE_DESC{
                    Type:D3D12_COMMAND_LIST_TYPE_DIRECT,..Default::default()
                }).unwrap()
            };
            let allocator:ID3D12CommandAllocator=unsafe {
                device.CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT).unwrap()
            };
            let list:ID3D12GraphicsCommandList=unsafe {
                device.CreateCommandList(0,D3D12_COMMAND_LIST_TYPE_DIRECT,&allocator,None).unwrap()
            };
            unsafe {
                for (i,&f) in staging.footprints.iter().enumerate() {
                    list.CopyTextureRegion(&subresource(&texture,i as u32),0,0,0,
                        &placed(&staging.buffer,f),None);
                }
                list.ResourceBarrier(&[crate::host::transition(&texture,
                    D3D12_RESOURCE_STATE_COPY_DEST,D3D12_RESOURCE_STATE_COPY_SOURCE)]);
                for (i,&f) in staging.footprints.iter().enumerate() {
                    list.CopyTextureRegion(&placed(&readback,f),0,0,0,
                        &subresource(&texture,i as u32),None);
                }
                list.Close().unwrap();
            }
            let command:ID3D12CommandList=list.cast().unwrap();
            let fence:ID3D12Fence=unsafe {device.CreateFence(0,D3D12_FENCE_FLAG_NONE).unwrap()};
            assert_eq!(unsafe {fence.GetCompletedValue()},0);
            unsafe {device.GetDeviceRemovedReason().unwrap();}
            let event=unsafe {CreateEventW(None,false,false,None).unwrap()};
            let commands=[Some(command)];
            unsafe {
                queue.ExecuteCommandLists(&commands);
                if queue.Signal(&fence,1).is_err(){uncertain("signal");}
                if fence.SetEventOnCompletion(1,event).is_err(){uncertain("event");}
                if WaitForSingleObject(event,30_000)!=WAIT_OBJECT_0{uncertain("wait");}
                let completed=fence.GetCompletedValue();
                if completed!=1 || device.GetDeviceRemovedReason().is_err(){uncertain("fence/device");}
                CloseHandle(event).unwrap();
                let mut out=std::ptr::null_mut();
                readback.Map(0,Some(&D3D12_RANGE{Begin:0,End:required as usize}),Some(&mut out)).unwrap();
                assert!(!out.is_null());
                // Only active GPU-written bytes are read, no padding assumptions.
                let mut mismatch=None;
                for &at in &active_offsets {
                    let got=out.cast::<u8>().add(at).read();
                    if got!=expected[at] { mismatch=Some((at,got,expected[at]));break; }
                }
                readback.Unmap(0,Some(&D3D12_RANGE{Begin:0,End:0}));
                assert_eq!(mismatch,None,"active byte oracle");
            }
            drop(commands);
            drop(list);
            drop(allocator);
            drop(readback);
            drop(texture);
            drop(staging); // return to pool only after confirmed transfer
            assert_eq!(STAGED[0].load(Relaxed),old_count);
            assert_eq!(STAGED[1].load(Relaxed),old_bytes);
            eprintln!("staging_transfer case={case} pool={} subresources={n} logical={total} required={required} width={width} active={} fence=1",u8::from(pool),active_offsets.len());
        }
    }
}
