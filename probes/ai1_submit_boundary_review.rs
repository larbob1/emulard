// SPDX-License-Identifier: GPL-3.0-or-later
#[cfg(all(test, feature = "diagnostics"))]
mod ai1_submit_boundary_review {
    use super::*;
    use std::sync::{Arc, atomic::{AtomicUsize, Ordering}};
    use windows::core::Interface;

    fn buffer(device: &ID3D12Device, kind: D3D12_HEAP_TYPE,
              state: D3D12_RESOURCE_STATES, size: u64) -> ID3D12Resource {
        let heap = D3D12_HEAP_PROPERTIES {
            Type: kind, CreationNodeMask: 1, VisibleNodeMask: 1, ..Default::default()
        };
        let desc = D3D12_RESOURCE_DESC {
            Dimension: D3D12_RESOURCE_DIMENSION_BUFFER, Width: size,
            Height: 1, DepthOrArraySize: 1, MipLevels: 1,
            SampleDesc: DXGI_SAMPLE_DESC { Count: 1, Quality: 0 },
            Layout: D3D12_TEXTURE_LAYOUT_ROW_MAJOR, ..Default::default()
        };
        let mut result: Option<ID3D12Resource> = None;
        unsafe {
            device.CreateCommittedResource(&heap, D3D12_HEAP_FLAG_NONE, &desc,
                state, None, &mut result).expect("owned buffer");
        }
        result.expect("resource")
    }


    #[derive(Debug, PartialEq, Eq)]
    struct Event {
        phase: u8, index: usize, target: u64, completed: u64,
        started: u64, finished: u64, retired: usize,
        first: [u64; 2],
    }
    struct Observer {
        out: [usize; 2],
        events: Vec<Event>,
    }
    thread_local! {
        static OBS: std::cell::RefCell<Option<Observer>> = const { std::cell::RefCell::new(None) };
    }
    pub(super) fn wait_failed() {
        OBS.with(|o| {
            if o.borrow().is_some() {
                eprintln!("actual wait or signal failure: aborting isolated owned fixture");
                std::process::abort();
            }
        });
    }
    pub(super) fn record(h: &Host, phase: u8, index: usize, target: u64) {
        OBS.with(|slot| {
            let mut slot = slot.borrow_mut();
            let Some(o) = slot.as_mut() else { return };
            let completed = unsafe { h.fence.GetCompletedValue() };
            if completed < target || completed == u64::MAX ||
                unsafe { h.device.GetDeviceRemovedReason() }.is_err() {
                eprintln!("unconfirmed actual fence at phase {phase}: {completed}/{target}");
                std::process::abort();
            }
            let mut first = [0; 2];
            for (i, ptr) in o.out.iter().copied().enumerate() {
                // Owned boxes remain alive in the fixture; synchronous caller,
                // no concurrent access or writes while this observer runs.
                first[i] = unsafe { (ptr as *const u64).read_unaligned() };
            }
            o.events.push(Event {
                phase, index, target, completed,
                started: STARTED.load(Ordering::Acquire),
                finished: FINISHED.load(Ordering::Acquire),
                retired: RETIRED.lock().unwrap().len(),
                first,
            });
        });
    }

    struct RetiredWitness(Arc<AtomicUsize>);
    impl Drop for RetiredWitness {
        fn drop(&mut self) { self.0.fetch_add(1, Ordering::SeqCst); }
    }

    fn bytes(list: usize, i: usize) -> u8 {
        (i as u8).wrapping_mul(3) ^ if list == 0 { 0x5a } else { 0xc3 }
    }

    #[test]
    fn actual_sync_submit_boundary() {
        const ROW: usize = 64;
        const PITCH: usize = 80;
        const OFFSET: usize = 8;
        const OUT: usize = 176;
        const MARK: [u64; 2] = [0x0123456789abcdef, 0xfedcba9876543210];
        assert_eq!(std::env::var("VICTORY_D3D12_WARP").as_deref(), Ok("1"));
        assert!(!late() && !relay() && !crate::shadow::cards());
        let mode = std::env::var("AI1_EXPECT_GROUPS").unwrap().parse::<u64>().unwrap();
        assert!(mode == 1 || mode == 2);
        let groups = if timing() { 2 } else { 1 };
        assert_eq!(groups, mode);
        let host = host().expect("real runtime WARP host");
        let adapter = host.adapter.as_ref().expect("host adapter identity");
        let desc = unsafe { adapter.cast::<IDXGIAdapter1>().unwrap().GetDesc1().unwrap() };
        assert_ne!(desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE.0 as u32, 0);
        assert_eq!(STARTED.load(Ordering::Acquire), 0);
        assert_eq!(FINISHED.load(Ordering::Acquire), 0);
        assert_eq!(*host.submitted.lock().unwrap(), 0);
        assert_eq!(unsafe { host.fence.GetCompletedValue() }, 0);
        assert!(RETIRED.lock().unwrap().is_empty());

        let mut out = [Box::new([0xe7u8; OUT]), Box::new([0xe7u8; OUT])];
        let retired = Arc::new(AtomicUsize::new(0));
        let prepared = Arc::new(AtomicUsize::new(0));
        let mut uploads = Vec::new();
        let mut reads = Vec::new();
        let mut lists = Vec::new();
        for i in 0..2 {
            let upload = buffer(&host.device, D3D12_HEAP_TYPE_UPLOAD,
                                D3D12_RESOURCE_STATE_GENERIC_READ, 128);
            let read = buffer(&host.device, D3D12_HEAP_TYPE_READBACK,
                              D3D12_RESOURCE_STATE_COPY_DEST, 512);
            let mut p = std::ptr::null_mut();
            unsafe {
                upload.Map(0, Some(&D3D12_RANGE { Begin: 0, End: 0 }), Some(&mut p)).unwrap();
                assert!(!p.is_null());
                for j in 0..128 { p.cast::<u8>().add(j).write(bytes(i, j)); }
                upload.Unmap(0, Some(&D3D12_RANGE { Begin: 0, End: 128 }));
            }
            let list = host.new_list().unwrap();
            unsafe {
                list.list.CopyBufferRegion(&read, 0, &upload, 64, 64);
                list.list.CopyBufferRegion(&read, 256, &upload, 0, 64);
            }
            let dst = unsafe { out[i].as_mut_ptr().add(OFFSET) };
            list.defer_read_back(read.clone(), dst, [ROW, 2, PITCH]);
            // Intentionally overlap the first eight readback bytes: if the
            // completion write precedes the readback, the marker is clobbered.
            list.defer_write(dst, crate::queue::Written::Value(MARK[i]), 8);
            let r = retired.clone();
            let p = prepared.clone();
            list.defer_host(move || {
                assert_eq!(STARTED.load(Ordering::Acquire), 1);
                assert_eq!(FINISHED.load(Ordering::Acquire), 0);
                assert_eq!(p.fetch_add(1, Ordering::SeqCst), i);
                retire(RetiredWitness(r.clone()));
                assert_eq!(r.load(Ordering::SeqCst), 0);
            });
            list.close();
            uploads.push(upload);
            reads.push(read);
            lists.push(list);
        }
        assert_eq!(prepared.load(Ordering::SeqCst), 0);
        assert_eq!(retired.load(Ordering::SeqCst), 0);
        assert!(out.iter().all(|x| x.iter().all(|&b| b == 0xe7)));
        // Actual synchronous runtime path; not a reimplementation. The
        // subprocess watchdog is external; production's INFINITE wait is
        // unchanged. This fixture only asserts the positive path.
        let runs: Vec<&HostList> = lists.iter().collect();
        OBS.with(|o| {
            assert!(o.borrow().is_none());
            *o.borrow_mut() = Some(Observer {
                out: [unsafe { out[0].as_mut_ptr().add(OFFSET) } as usize,
                      unsafe { out[1].as_mut_ptr().add(OFFSET) } as usize],
                events: Vec::with_capacity(12),
            });
        });
        let result = host.submit(&runs, false);
        if result.is_some() { std::process::abort(); }
        drop(result);
        let completed = unsafe { host.fence.GetCompletedValue() };
        if completed != groups || unsafe { host.device.GetDeviceRemovedReason() }.is_err() {
            eprintln!("unconfirmed actual submit completion: {completed}");
            std::process::abort();
        }
        let events = OBS.with(|o| o.borrow_mut().take().unwrap().events);
        let sentinel = u64::from_le_bytes([0xe7; 8]);
        let raw = |list| u64::from_le_bytes(std::array::from_fn(|i| bytes(list, 64+i)));
        let mut expected = Vec::new();
        let mut event = |phase, index, target, finished, retired, first| {
            expected.push(Event { phase, index, target, completed: target,
                                  started: 1, finished, retired, first });
        };
        for i in 0..groups {
            event(0, i as usize, i+1, 0, 2, [sentinel, sentinel]);
        }
        event(1, 0, groups, 0, 2, [sentinel, sentinel]);
        event(2, 0, groups, 1, 0, [sentinel, sentinel]);
        event(3, 0, groups, 1, 0, [sentinel, sentinel]);
        event(4, 0, groups, 1, 0, [raw(0), sentinel]);
        event(5, 0, groups, 1, 0, [MARK[0], sentinel]);
        event(3, 1, groups, 1, 0, [MARK[0], sentinel]);
        event(4, 1, groups, 1, 0, [MARK[0], raw(1)]);
        event(5, 1, groups, 1, 0, [MARK[0], MARK[1]]);
        assert_eq!(events, expected, "ordered actual wait/retire/readback/publication");
        assert_eq!(*host.submitted.lock().unwrap(), groups);
        assert_eq!(STARTED.load(Ordering::Acquire), 1);
        assert_eq!(FINISHED.load(Ordering::Acquire), 1);
        assert_eq!(prepared.load(Ordering::SeqCst), 2);
        assert_eq!(retired.load(Ordering::SeqCst), 2);
        assert!(RETIRED.lock().unwrap().is_empty());
        for i in 0..2 {
            let mut expected = [0xe7u8; OUT];
            for j in 0..ROW {
                expected[OFFSET + j] = bytes(i, 64+j);
                expected[OFFSET + PITCH + j] = bytes(i, j);
            }
            expected[OFFSET..OFFSET+8].copy_from_slice(&MARK[i].to_le_bytes());
            assert_eq!(*out[i], expected, "list {i} data, pitch gaps and completion ordering");
        }
        // Keep all resources alive through receipt and byte oracle.
        drop(runs);
        drop(lists);
        drop(reads);
        drop(uploads);
    }
}
