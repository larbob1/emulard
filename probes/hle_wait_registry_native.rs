// SPDX-License-Identifier: GPL-3.0-or-later
// Append only to an exact, disposable prepared list.rs. Registry-only.
// No actual queue submission, cut, GPU work, or contention injection.
#[cfg(all(test, windows))]
mod hle_wait_registry_native {
    use super::*;
    use std::ptr::{null, null_mut};

    type Record = (u64, u32, u64, bool);

    fn record(w: &ValueWait) -> Record {
        (w.address, w.comparison, w.reference, w.wide)
    }

    fn registry() -> Vec<(usize, Record)> {
        VALUE_WAITS.lock().unwrap_or_else(|e| e.into_inner())
            .iter().map(|(key, w)| (*key, record(w))).collect()
    }

    fn forget_test_key(key: usize) {
        VALUE_WAITS.lock().unwrap_or_else(|e| e.into_inner())
            .retain(|(k, _)| *k != key);
    }

    struct OwnedList {
        list: This,
        allocator: This,
    }

    impl OwnedList {
        fn new() -> Self {
            let mut this = Self { list: null(), allocator: null() };
            // Exact pinned signature: device, kind, IID, output.
            assert_eq!(create_allocator(null(), 0, &ALLOCATOR_IIDS[0], &mut this.allocator), S_OK);
            assert!(!this.allocator.is_null());
            assert_eq!(create_list(null(), 0, 0, this.allocator, null(),
                                   &LIST_IIDS[1], &mut this.list), S_OK);
            assert!(!this.list.is_null());
            this
        }
        fn key(&self) -> usize { self.list as usize }
        fn release_last(&mut self) {
            let list = std::mem::replace(&mut self.list, null());
            assert!(!list.is_null());
            assert_eq!(list_release(list), 0);
        }
    }

    impl Drop for OwnedList {
        fn drop(&mut self) {
            if !self.list.is_null() { list_release(self.list); }
            if !self.allocator.is_null() { allocator_release(self.allocator); }
        }
    }

    fn mode() -> (String, bool) {
        let bits = ["VICTORY_QUEUE_WAIT", "VICTORY_SPLIT_WAITS", "VICTORY_CUT_WAITS"]
            .map(|key| std::env::var(key).expect("explicit route switch required"));
        let mode = bits.concat();
        assert!(matches!(mode.as_str(), "000" | "100" | "110"));
        assert_eq!(std::env::var("AI6_WAIT_MODE").unwrap(), mode);
        assert!(!crate::queue::cuts(), "cut route outside registry scope");
        let cleanup = match std::env::var("AI6_EXPECT_CLEANUP").unwrap().as_str() {
            "0" => false,
            "1" => true,
            _ => panic!("explicit baseline/candidate expectation required"),
        };
        let ask = std::env::var("VICTORY_WAIT_ASK").unwrap();
        assert!(matches!(ask.as_str(), "0" | "1"));
        (mode, cleanup)
    }

    fn add(list: This, r: Record) {
        let (address, comparison, reference, wide) = r;
        if wide { wait_value64(list, address, comparison, reference); }
        else { wait_value(list, address, comparison, reference); }
    }

    fn expected(key: usize, records: &[Record]) -> Vec<(usize, Record)> {
        records.iter().copied().map(|r| (key, r)).collect()
    }

    // Both arms use this exact fixture. Baseline stale records are adverse
    // evidence, asserted as such and erased only after the recorded result.
    #[test]
    #[ignore = "fresh process; explicit 000/100/110 and baseline/candidate switches"]
    fn actual_wait_registry_lifecycle() {
        let (mode, cleanup) = mode();
        assert!(registry().is_empty(), "not an isolated registry");
        // Heap owners remain live and immutable through all ValueWait reads.
        let low = Box::new(7u32);
        let wide = Box::new(0x1_0000_0007u64);
        let lo = std::ptr::from_ref(low.as_ref()) as u64;
        let hi = std::ptr::from_ref(wide.as_ref()) as u64;
        assert_eq!(lo % 4, 0);
        assert_eq!(hi % 8, 0);
        let mut lo_bytes = [0; 4];
        let mut hi_bytes = [0; 8];
        assert!(crate::host::read_into(lo as *const u8, &mut lo_bytes));
        assert!(crate::host::read_into(hi as *const u8, &mut hi_bytes));
        assert_eq!(u32::from_le_bytes(lo_bytes), 7);
        assert_eq!(u64::from_le_bytes(hi_bytes), 0x1_0000_0007);
        let a_records = [(lo, 3, 7, false), (lo, 3, 8, false),
                         (hi, 3, 0x1_0000_0007, true), (hi, 3, 7, true)];
        let b_records = [(hi, 3, 0x1_0000_0008, true), (lo, 3, 7, false)];

        let mut a = OwnedList::new();
        let mut b = OwnedList::new();
        let (ak, bk) = (a.key(), b.key());
        assert_ne!(ak, bk);
        for r in a_records { add(a.list, r); }
        for r in b_records { add(b.list, r); }
        let mut both = expected(ak, &a_records);
        both.extend(expected(bk, &b_records));
        assert_eq!(registry(), both);

        // Failed reset must not erase anything. Valid reset only erases A.
        assert_eq!(reset(a.list, null(), null()), E_INVALIDARG);
        assert_eq!(registry(), both);
        assert_eq!(close(a.list), S_OK);
        assert_eq!(reset(a.list, a.allocator, null()), S_OK);
        assert_eq!(registry(), expected(bk, &b_records));
        for r in a_records { add(a.list, r); }
        let mut both = expected(bk, &b_records);
        both.extend(expected(ak, &a_records));
        assert_eq!(registry(), both);

        // Refused/unexposed creations must not touch the live recordings.
        let unknown = [0u8; 16];
        assert!(!LIST_IIDS.contains(&unknown));
        let mut refused: This = null();
        assert_eq!(create_list(null(), 0, 0, a.allocator, null(), &unknown,
                               &mut refused), object::E_NOINTERFACE);
        assert!(refused.is_null());
        assert_eq!(create_list(null(), 0, 0, a.allocator, null(), &LIST_IIDS[1],
                               null_mut()), object::S_FALSE);
        assert_eq!(registry(), both);

        assert_eq!(object::add_ref(a.list), 2);
        assert_eq!(list_release(a.list), 1);
        assert_eq!(registry(), both);
        a.release_last();
        // No new List allocation between release and this observation.
        let stale_expected = if cleanup { expected(bk, &b_records) } else { both };
        assert_eq!(registry(), stale_expected);
        println!("AI6 final-release mode={mode} cleanup={cleanup} expected_stale={}",
                 if cleanup { 0 } else { a_records.len() });
        forget_test_key(ak); // explicitly remove only baseline test residue
        assert_eq!(registry(), expected(bk, &b_records));

        // No queue submission. Exercise the actual registry consumers only.
        let mut c = OwnedList::new();
        let ck = c.key();
        for r in a_records { add(c.list, r); }
        if mode == "110" {
            let taken = waits_by_list(&[c.list, b.list, c.list]);
            assert_eq!(taken.len(), 3);
            assert_eq!(taken[0].iter().map(record).collect::<Vec<_>>(), a_records.to_vec());
            assert_eq!(taken[1].iter().map(record).collect::<Vec<_>>(), b_records.to_vec());
            assert!(taken[2].is_empty());
            assert!(registry().is_empty());
            c.release_last();
            b.release_last();
            // The copied values are not tied to the recording's lifetime.
            assert_eq!(taken[0].iter().map(ValueWait::met).collect::<Vec<_>>(),
                       vec![true, false, true, false]);
            assert_eq!(taken[1].iter().map(ValueWait::met).collect::<Vec<_>>(),
                       vec![false, true]);
        } else if mode == "100" {
            let unmet = unmet_waits(&[c.list, c.list]);
            assert_eq!(unmet.iter().map(record).collect::<Vec<_>>(),
                       vec![a_records[1], a_records[3]]);
            assert_eq!(registry(), expected(bk, &b_records));
            c.release_last();
            assert_eq!(unmet.iter().map(ValueWait::met).collect::<Vec<_>>(), vec![false, false]);
            let unmet_b = unmet_waits(&[b.list]);
            assert_eq!(unmet_b.iter().map(record).collect::<Vec<_>>(), vec![b_records[0]]);
            b.release_last();
            assert!(!unmet_b[0].met());
        } else {
            // Disabled mode still records waits; actual execute not tested.
            let mut both = expected(bk, &b_records);
            both.extend(expected(ck, &a_records));
            assert_eq!(registry(), both);
            c.release_last();
            let stale_expected = if cleanup { expected(bk, &b_records) } else { both };
            assert_eq!(registry(), stale_expected);
            forget_test_key(ck);
            b.release_last();
            assert_eq!(registry(), if cleanup { vec![] } else { expected(bk, &b_records) });
            forget_test_key(bk);
        }
        assert!(registry().is_empty());
        assert_eq!((*low, *wide), (7, 0x1_0000_0007));
        println!("AI6 registry-only mode={mode} cleanup={cleanup} ask={} completed",
                 std::env::var("VICTORY_WAIT_ASK").unwrap());
    }
}
