// SPDX-License-Identifier: GPL-3.0-or-later
// Append only to disposable pinned prepared host.rs. No shared submit hooks.
#[cfg(all(test, windows, feature = "diagnostics"))]
mod ai2_guest_close_refusal {
    use super::*;
    use crate::object::This;
    use crate::resource::ai2_record_resource as guest;
    use crate::texback::{self, ai2_guest_close_observe as obs};
    use crate::list::ai2_guest_close_list::OwnedList;
    use windows::Win32::Graphics::Dxgi::Common::DXGI_FORMAT_R8_UNORM;
    use windows::core::Interface;
    use windows::Win32::Graphics::Dxgi::{IDXGIAdapter1, DXGI_ADAPTER_FLAG_SOFTWARE};
    use windows_sys::Win32::System::Memory::{VirtualAlloc, VirtualFree, VirtualQuery,
        MEMORY_BASIC_INFORMATION, MEM_COMMIT, MEM_RESERVE, MEM_RELEASE, MEM_PRIVATE, PAGE_READWRITE};

    const ALLOCATION: usize = 65536;
    const PREFIX: usize = 256;
    const SIZE: usize = 2560;

    struct Owned {
        page: *mut u8,
        this: This,
        seed: u8,
    }

    impl Owned {
        fn new(seed: u8) -> Self {
            let page = unsafe { VirtualAlloc(std::ptr::null(),ALLOCATION,
                MEM_RESERVE | MEM_COMMIT,PAGE_READWRITE) }.cast::<u8>();
            assert!(!page.is_null());
            let mut owned = Self { page, this: std::ptr::null(), seed };
            owned.check_page();
            for i in 0..ALLOCATION {
                unsafe { page.add(i).write(owned.expected(i)); }
            }
            owned.this = guest::create(owned.at());
            owned.verify();
            owned
        }
        fn at(&self) -> usize { (unsafe { self.page.add(PREFIX) }) as usize }
        fn expected(&self,i: usize) -> u8 {
            if (PREFIX..PREFIX+SIZE).contains(&i) {
                self.seed.wrapping_add((i as u8).wrapping_mul(37))
            } else { self.seed ^ 0xA5 }
        }
        fn check_page(&self) {
            let mut info: MEMORY_BASIC_INFORMATION = unsafe { std::mem::zeroed() };
            let n = unsafe { VirtualQuery(self.page.cast(),&mut info,std::mem::size_of_val(&info)) };
            assert_eq!(n,std::mem::size_of_val(&info));
            assert_eq!(info.BaseAddress as usize,self.page as usize);
            assert_eq!(info.AllocationBase as usize,self.page as usize);
            assert_eq!(info.State,MEM_COMMIT);
            assert_eq!(info.Protect,PAGE_READWRITE);
            assert_eq!(info.Type,MEM_PRIVATE);
            assert!(info.RegionSize>=ALLOCATION);
            assert_eq!(self.at()%256,0);
        }
        fn verify(&self) {
            self.check_page();
            let bytes = unsafe { std::slice::from_raw_parts(self.page,ALLOCATION) };
            for (i,&b) in bytes.iter().enumerate() {
                assert_eq!(b,self.expected(i),"owned byte {i}");
            }
        }
    }

    impl Drop for Owned {
        fn drop(&mut self) {
            if !self.this.is_null() {
                guest::release(self.this,self.at());
                self.this = std::ptr::null();
                if !std::thread::panicking() { self.verify(); }
            }
            assert_ne!(unsafe { VirtualFree(self.page.cast(),0,MEM_RELEASE) },0);
        }
    }

    fn preflight() -> &'static Host {
        assert_eq!(std::env::var("VICTORY_D3D12_WARP").as_deref(),Ok("1"));
        assert_eq!(std::env::var("VICTORY_SWEEP").as_deref(),Ok("0"));
        assert_eq!(std::env::var("VICTORY_TEXTURE_BACK").as_deref(),Ok("7x3f61"));
        assert!(std::env::var_os("VICTORY_COPY_MODE").is_none());
        assert!(std::env::var_os("VICTORY_GPU_TIMING").is_none());
        assert_eq!(crate::copystat::mode(),0);
        assert!(!timing());
        let h = host().expect("owned WARP host");
        let warp = warp_adapter().expect("strict WARP adapter");
        let desc = unsafe { warp.cast::<IDXGIAdapter1>().unwrap().GetDesc1().unwrap() };
        let actual = unsafe { h.device.GetAdapterLuid() };
        assert_ne!(desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE.0 as u32,0);
        assert_eq!((actual.HighPart,actual.LowPart),(desc.AdapterLuid.HighPart,desc.AdapterLuid.LowPart));
        no_submission(h);
        eprintln!("guest_close_adapter actual_high={} actual_low={} warp_high={} warp_low={} software=1",
            actual.HighPart,actual.LowPart,desc.AdapterLuid.HighPart,desc.AdapterLuid.LowPart);
        h
    }

    fn no_submission(h: &Host) {
        assert_eq!(*h.submitted.lock().unwrap(),0);
        assert_eq!(STARTED.load(Ordering::Acquire),0);
        assert_eq!(FINISHED.load(Ordering::Acquire),0);
        assert_eq!(unsafe { h.fence.GetCompletedValue() },0);
        unsafe { h.device.GetDeviceRemovedReason().unwrap(); }
    }

    const SHAPES: [(usize,usize);4] = [(7,3),(3,1),(7,3),(3,1)];
    fn footprints(device: &ID3D12Device,texture: &ID3D12Resource)
        -> ([D3D12_PLACED_SUBRESOURCE_FOOTPRINT;4],[u32;4],u64) {
        let desc = unsafe { texture.GetDesc() };
        assert_eq!(desc.Dimension,D3D12_RESOURCE_DIMENSION_TEXTURE2D);
        assert_eq!((desc.Width,desc.Height,desc.DepthOrArraySize,desc.MipLevels),(7,3,2,2));
        assert_eq!(desc.Format,DXGI_FORMAT_R8_UNORM);
        assert_eq!(desc.SampleDesc.Count,1);
        let mut info = D3D12_FEATURE_DATA_FORMAT_INFO{Format:desc.Format,PlaneCount:0};
        unsafe { device.CheckFeatureSupport(D3D12_FEATURE_FORMAT_INFO,
            (&mut info as *mut D3D12_FEATURE_DATA_FORMAT_INFO).cast(),
            std::mem::size_of_val(&info) as u32).unwrap(); }
        assert_eq!(info.PlaneCount,1);
        let mut f = [D3D12_PLACED_SUBRESOURCE_FOOTPRINT::default();4];
        let mut rows = [0u32;4];
        let mut row_bytes = [0u64;4];
        let mut total = 0;
        unsafe { device.GetCopyableFootprints(&desc,0,4,0,Some(f.as_mut_ptr()),
            Some(rows.as_mut_ptr()),Some(row_bytes.as_mut_ptr()),Some(&mut total)); }
        let mut extent = 0;
        for (i,(w,h)) in SHAPES.into_iter().enumerate() {
            let p = f[i].Footprint;
            assert_eq!((p.Width,p.Height,p.Depth),(w as u32,h as u32,1));
            assert_eq!(p.Format,DXGI_FORMAT_R8_UNORM);
            assert_eq!((rows[i],row_bytes[i]),(h as u32,w as u64));
            assert!(p.RowPitch>=w as u32 && p.RowPitch%256==0);
            assert_eq!(f[i].Offset%512,0);
            assert!(f[i].Offset>=extent);
            extent = f[i].Offset.checked_add(u64::from(p.RowPitch)*u64::from(rows[i])).unwrap();
        }
        assert!(total>0 && total<=extent && extent<=65536);
        (f,rows,extent)
    }

    fn run(refuse: bool) {
        let h = preflight();
        let a = Owned::new(0x43);
        let list = OwnedList::new();
        let (selected, host_id) = {
            let l = list.host();
            let id = l as *const HostList as usize;
            { let d = l.deferred(); assert!(d.back_wanted.is_empty());
              assert!(d.texture_backs.is_empty()); }
            assert!(texback::wanted(a.this));
            l.texture_written(a.this);
            let d = l.deferred();
            assert_eq!(d.back_wanted.len(),1);
            assert!(d.texture_backs.is_empty());
            (obs::selected(&d.back_wanted[0]),id)
        };
        assert_eq!(selected.owner(),a.this as usize);
        assert_eq!(selected.range(),(a.at(),a.at()+SIZE));
        assert!(selected.valid());
        assert!(std::sync::Arc::ptr_eq(&selected.copy,
            &crate::resource::host_copy(a.this).expect("owned host texture")));
        let (f,rows,extent) = footprints(&h.device,&selected.copy.texture);
        let shapes = std::array::from_fn(|i| obs::shape(&f[i],rows[i]));
        a.verify();
        obs::arm(&selected,refuse);
        let status = list.close();
        let seen = obs::finish();
        assert_eq!(status,crate::object::S_OK);
        assert_eq!(seen,obs::Seen { valid:true,extent,count:4,shapes });
        assert!(selected.valid());
        let (recorded,width) = {
            let l = list.host();
            assert_eq!(l as *const HostList as usize,host_id);
            let d = l.deferred();
            assert!(d.back_wanted.is_empty());
            assert_eq!(d.texture_backs.len(),usize::from(!refuse));
            if refuse { (0,None) }
            else {
                let (width,actual) = obs::recorded(&d.texture_backs[0],&selected);
                assert_eq!(actual,shapes);
                assert!(width>=extent);
                (1,Some(width))
            }
        };
        a.verify();
        no_submission(h);
        // All list borrows and deferred guards have ended before guest release.
        list.release();
        a.verify();
        assert!(selected.valid());
        drop(a);
        assert!(!selected.valid());
        drop(selected);
        no_submission(h);
        let width = width.map_or_else(|| "unavailable".to_owned(), |v| v.to_string());
        eprintln!("guest_close_case refused={} selected=1 current=1 consumed=1 subresources=4 extent={} width={} wanted_after=0 recorded={} guest_status={} submitted=0 fence=0 healthy=1 preserved=2560 guards=62976 cleanup=1",
            u8::from(refuse),extent,width,recorded,status);
    }

    #[test]
    #[ignore = "fresh isolated WARP process; ordinary guest close baseline"]
    fn actual_guest_close_control() { run(false); }

    #[test]
    #[ignore = "fresh isolated WARP process; controlled pre-allocation refusal"]
    fn actual_guest_close_refusal() { run(true); }
}
