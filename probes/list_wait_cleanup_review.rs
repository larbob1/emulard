// GPL-3.0-or-later. Review-only append module; not a standalone executable.
// Synthetic registry records only. No target addresses are dereferenced.
#[cfg(test)]
mod ai0_list_wait_cleanup_review {
    use super::*;

    struct Handles { list: This, allocator: This }
    impl Handles {
        fn new() -> Self {
            let null = std::ptr::null();
            let mut allocator = null;
            assert_eq!(create_allocator(null, 0, &ALLOCATOR_IIDS[0], &mut allocator), S_OK);
            let mut list = null;
            let hr = create_list(null, 0, 0, allocator, null, &LIST_IIDS[1], &mut list);
            if hr != S_OK { allocator_release(allocator); }
            assert_eq!(hr, S_OK);
            assert!(!list.is_null());
            Self { list, allocator }
        }
        fn release_last(&mut self) {
            let list = std::mem::replace(&mut self.list, std::ptr::null());
            assert_eq!(list_release(list), 0);
        }
    }
    impl Drop for Handles {
        fn drop(&mut self) {
            if !self.list.is_null() { list_release(self.list); }
            allocator_release(self.allocator);
        }
    }

    fn insert(list: This, reference: u64) {
        VALUE_WAITS.lock().unwrap_or_else(|e| e.into_inner()).push((
            list as usize,
            ValueWait { address: 0, comparison: 0, reference, wide: false },
        ));
    }
    fn count(address: usize) -> usize {
        VALUE_WAITS.lock().unwrap_or_else(|e| e.into_inner())
            .iter().filter(|(list, _)| *list == address).count()
    }

    #[test]
    fn final_release_removes_only_its_own_waits() {
        let mut a = Handles::new();
        let mut b = Handles::new();
        let (aa, bb) = (a.list as usize, b.list as usize);
        insert(a.list, 1);
        insert(a.list, 2);
        insert(b.list, 3);
        assert_eq!(count(aa), 2);
        assert_eq!(count(bb), 1);
        // Retain a second reference; a non-final release must preserve waits.
        assert_eq!(crate::object::add_ref(a.list), 2);
        assert_eq!(list_release(a.list), 1);
        assert_eq!(count(aa), 2);
        a.release_last();
        assert_eq!(count(aa), 0);
        assert_eq!(count(bb), 1);
        b.release_last();
        assert_eq!(count(bb), 0);
    }

    #[test]
    fn reset_then_final_release_is_idempotent() {
        let mut a = Handles::new();
        let address = a.list as usize;
        insert(a.list, 4);
        assert_eq!(count(address), 1);
        assert_eq!(reset(a.list, a.allocator, std::ptr::null()), S_OK);
        assert_eq!(count(address), 0);
        insert(a.list, 5);
        a.release_last();
        assert_eq!(count(address), 0);
    }

    #[cfg(windows)]
    #[test]
    fn consumed_waits_survive_recording_destruction_as_values() {
        let mut a = Handles::new();
        let address = a.list as usize;
        insert(a.list, 6);
        let taken = waits_by_list(&[a.list]);
        assert_eq!(count(address), 0);
        a.release_last();
        assert_eq!(count(address), 0);
        assert_eq!(taken[0].len(), 1);
        assert_eq!(taken[0][0].reference, 6);
    }
}
