// SPDX-License-Identifier: GPL-3.0-or-later
// Append only to disposable prepared list.rs.
#[cfg(all(test, windows, feature = "diagnostics"))]
pub(crate) mod ai2_guest_close_list {
    use super::*;

    pub(crate) struct OwnedList { allocator: This, list: This }

    impl OwnedList {
        pub(crate) fn new() -> Self {
            let mut owned = Self { allocator: std::ptr::null(), list: std::ptr::null() };
            assert_eq!(create_allocator(std::ptr::null(), 0, &ALLOCATOR_IIDS[0],
                &mut owned.allocator), S_OK);
            assert!(!owned.allocator.is_null());
            assert_eq!(create_list(std::ptr::null(), 0, 0, owned.allocator,
                std::ptr::null(), &LIST_IIDS[0], &mut owned.list), S_OK);
            assert!(!owned.list.is_null());
            assert_eq!(list_type(owned.list), 0);
            assert!(host_list(owned.list).is_some());
            owned
        }

        // The borrow cannot outlive this owner.
        pub(crate) fn host(&self) -> &crate::host::HostList {
            host_list(self.list).expect("actual guest list has host")
        }
        pub(crate) fn close(&self) -> HRESULT { super::close(self.list) }
        pub(crate) fn release(mut self) {
            let l = std::mem::replace(&mut self.list, std::ptr::null());
            assert_eq!(list_release(l), 0);
            let a = std::mem::replace(&mut self.allocator, std::ptr::null());
            assert_eq!(allocator_release(a), 0);
        }
    }
    impl Drop for OwnedList {
        fn drop(&mut self) {
            if !self.list.is_null() { list_release(self.list); }
            if !self.allocator.is_null() { allocator_release(self.allocator); }
        }
    }
}
