    // SPDX-License-Identifier: GPL-3.0-or-later
    // Disposable native fixture. Only the test vtable dispatch is replaced.
    static FILE_LIFETIME_CANDIDATE: AtomicBool = AtomicBool::new(false);
    static FILE_LIFETIME_PREFREE: AtomicU32 = AtomicU32::new(0);

    pub(super) extern "system" fn file_release_review(this: *mut Instance<File>) -> u32 {
        if !FILE_LIFETIME_CANDIDATE.load(Ordering::Acquire) {
            return release::<File>(this);
        }
        // Same reference-count operation and last-reference ownership as release.
        let left = unsafe { &*this }.refs.fetch_sub(1, Ordering::AcqRel) - 1;
        if left == 0 {
            let removed = {
                let mut entries = WALLS_FILES.lock().unwrap_or_else(|e| e.into_inner());
                if let Some(index) = entries.iter().position(|entry| entry.0 == this as usize) {
                    entries.remove(index);
                    true
                } else {
                    false
                }
            };
            // Registry guard has ended; object is still allocated here.
            if removed {
                FILE_LIFETIME_PREFREE.fetch_add(1, Ordering::Relaxed);
            }
            drop(unsafe { Box::from_raw(this) });
        }
        left
    }

    fn file_lifetime_ref(object: *mut c_void, byte_offset: usize) -> u32 {
        let f: extern "system" fn(*mut c_void) -> u32 = call(object, byte_offset);
        f(object)
    }

    fn file_lifetime_snapshot(a: usize, b: usize, label_a: &str, label_b: &str) -> (usize, usize, usize, bool, bool) {
        let entries = WALLS_FILES.lock().unwrap_or_else(|e| e.into_inner());
        let ac = entries.iter().filter(|e| e.0 == a).count();
        let bc = entries.iter().filter(|e| e.0 == b).count();
        let am = entries.iter().find(|e| e.0 == a).is_some_and(|e| e.1 == label_a);
        let bm = entries.iter().find(|e| e.0 == b).is_some_and(|e| e.1 == label_b);
        assert!(!entries.iter().any(|e| e.0 == 0));
        (entries.len(), ac, bc, am, bm)
    }

    fn file_lifetime_case(candidate: bool) {
        // Runner must use one ignored test per fresh process.
        assert!(WALLS_FILES.lock().unwrap_or_else(|e| e.into_inner()).is_empty());
        assert_eq!(FILE_LIFETIME_PREFREE.load(Ordering::Relaxed), 0);
        assert!(!FILE_LIFETIME_CANDIDATE.swap(candidate, Ordering::AcqRel));
        let dir = tempfile::tempdir().unwrap();
        let pa = dir.path().join("fixture-a.bin");
        let pb = dir.path().join("fixture-b.bin");
        std::fs::write(&pa, [11u8, 22]).unwrap();
        std::fs::write(&pb, [33u8, 44]).unwrap();
        let la = pa.to_string_lossy();
        let lb = pb.to_string_lossy();
        assert!(la != lb);
        let a = open(&pa);
        let b = open(&pb);
        assert!(!a.is_null() && !b.is_null() && a != b);
        // Save integer identities while live; never dereference after final release.
        let (ak, bk) = (a as usize, b as usize);
        let snapshot = || file_lifetime_snapshot(ak, bk, &la, &lb);
        let s0 = snapshot();
        assert_eq!(s0, (2, 1, 1, true, true));
        let a2 = file_lifetime_ref(a, 0x08);
        let b2 = file_lifetime_ref(b, 0x08);
        assert_eq!((a2, b2), (2, 2));
        let a1 = file_lifetime_ref(a, 0x10);
        let b1 = file_lifetime_ref(b, 0x10);
        assert_eq!((a1, b1), (1, 1));
        let s1 = snapshot();
        assert_eq!(s1, s0);
        let p1 = FILE_LIFETIME_PREFREE.load(Ordering::Relaxed);
        assert_eq!(p1, 0);
        let a0 = file_lifetime_ref(a, 0x10);
        assert_eq!(a0, 0);
        let s2 = snapshot();
        assert_eq!(s2, if candidate { (1, 0, 1, false, true) } else { s0 });
        let p2 = FILE_LIFETIME_PREFREE.load(Ordering::Relaxed);
        assert_eq!(p2, u32::from(candidate));
        let b0 = file_lifetime_ref(b, 0x10);
        assert_eq!(b0, 0);
        let s3 = snapshot();
        assert_eq!(s3, if candidate { (0, 0, 0, false, false) } else { s0 });
        let p3 = FILE_LIFETIME_PREFREE.load(Ordering::Relaxed);
        assert_eq!(p3, 2 * u32::from(candidate));
        // Close/delete synthetic files after both actual file objects were released.
        dir.close().unwrap();
        FILE_LIFETIME_CANDIDATE.store(false, Ordering::Release);
        eprintln!("storage_file_lifetime mode={} a2={} a1={} a0={} b2={} b1={} b0={} open={} nonlast={} after_a={} after_b={} other={} prefree1={} prefree2={} prefree3={}",
            u8::from(candidate), a2, a1, a0, b2, b1, b0, s0.0, s1.0, s2.0, s3.0,
            s2.2, p1, p2, p3);
    }

    #[test]
    #[ignore = "isolated native file lifetime baseline"]
    fn storage_file_lifetime_baseline() {
        file_lifetime_case(false);
    }

    #[test]
    #[ignore = "isolated native file lifetime candidate"]
    fn storage_file_lifetime_candidate() {
        file_lifetime_case(true);
    }
