// SPDX-License-Identifier: GPL-3.0-or-later
// Append inside dstorage.rs's existing cfg(test) tests module.
// Baseline execution only; no scratch, timing, injected host failures or flags.
// Run each ignored test in its own externally bounded native subprocess.

struct CompletionQueue(*mut c_void);
impl Drop for CompletionQueue {
    fn drop(&mut self) {
        // Close waits for running requests before their backing is released.
        void(self.0, 0x40);
        release(self.0.cast::<Instance<Queue>>());
    }
}
struct CompletionFile(*mut c_void);
impl Drop for CompletionFile {
    fn drop(&mut self) {
        release(self.0.cast::<Instance<File>>());
    }
}
struct CompletionArray(*mut c_void);
impl Drop for CompletionArray {
    fn drop(&mut self) {
        release(self.0.cast::<Instance<StatusArray>>());
    }
}

const COMPLETION_SENTINEL: u8 = 0xA5;

fn completion_offsets(size: usize) -> [usize; 3] {
    [7, size - 3, 41]
}

fn completion_expected(data: &[u8], index: usize, direct_page: bool) -> [u8; 32] {
    let mut expected = [COMPLETION_SENTINEL; 32];
    let offset = completion_offsets(data.len())[index];
    let count = if index != 1 { 16 } else if direct_page { 3 } else { 0 };
    expected[8..8 + count].copy_from_slice(&data[offset..offset + count]);
    expected
}

fn completion_statuses(array: *mut c_void) -> [HRESULT; 3] {
    [wait(array, 0), wait(array, 1), wait(array, 2)]
}

#[test]
#[ignore = "isolated actual queue completion; external watchdog required"]
fn storage_completion_native_address() {
    let data = pattern(4096);
    let (_dir, file) = file_with(&data);
    let file = CompletionFile(file);
    let mut destinations = Box::new([[COMPLETION_SENTINEL; 32]; 3]);
    let pointers = destinations.each_mut().map(|b| b[8..24].as_mut_ptr().cast::<c_void>());
    let array = CompletionArray(status_array(3));
    // Declared last: on unwind close before any input/destination is freed.
    let queue = CompletionQueue(new_queue(0));
    let offsets = completion_offsets(data.len());
    for i in 0..2 {
        let r = request(0, pointers[i],
                        16, file.0.cast_const(), offsets[i] as u64, 16);
        enqueue(queue.0, &r);
        enqueue_status(queue.0, array.0, i as u32);
    }
    void(queue.0, 0x30);
    let first = [wait(array.0, 0), wait(array.0, 1)];
    // A new request on the same queue after the failed segment.
    let r = request(0, pointers[2],
                    16, file.0.cast_const(), offsets[2] as u64, 16);
    enqueue(queue.0, &r);
    enqueue_status(queue.0, array.0, 2);
    void(queue.0, 0x30);
    let statuses = completion_statuses(array.0);
    // Drain before inspecting raw destinations; this does not prove visibility
    // at the precise status-publication instant.
    drop(queue);
    assert_eq!(first, [S_OK, END_OF_FILE]);
    assert_eq!(statuses, [S_OK, END_OF_FILE, S_OK]);
    for i in 0..3 {
        assert_eq!(destinations[i], completion_expected(&data, i, false));
    }
}

struct CompletionPages {
    ids: [usize; 2],
}
impl CompletionPages {
    fn new(separate: bool) -> Self {
        use crate::modules::xmem;
        let mut owned = Self { ids: [0; 2] };
        if separate {
            for id in &mut owned.ids {
                let mut one = 1;
                assert_eq!(xmem::XMemAllocatePhysicalPages(0, &mut one, id), 1);
                assert_eq!(one, 1);
            }
        } else {
            let mut n = 2;
            assert_eq!(xmem::XMemAllocatePhysicalPages(0, &mut n, owned.ids.as_mut_ptr()), 1);
            assert_eq!(n, 2);
        }
        assert!(owned.ids.iter().all(|id| *id != 0));
        assert_ne!(owned.ids[0], owned.ids[1]);
        for (id, offset) in owned.ids.iter().zip([PAGE - 16, 0]) {
            let mut window = xmem::page_window(std::slice::from_ref(id), offset, 16).unwrap();
            window.bytes().fill(COMPLETION_SENTINEL);
        }
        assert_eq!(xmem::page_window(&owned.ids, PAGE - 8, 16).is_some(), !separate);
        owned
    }
    fn seen(&self) -> [u8; 32] {
        use crate::modules::xmem;
        let mut bytes = [0; 32];
        for ((id, offset), chunk) in self.ids.iter().zip([PAGE - 16, 0])
            .zip(bytes.chunks_exact_mut(16)) {
            let mut window = xmem::page_window(std::slice::from_ref(id), offset, 16).unwrap();
            chunk.copy_from_slice(window.bytes());
        }
        bytes
    }
}
impl Drop for CompletionPages {
    fn drop(&mut self) {
        use crate::modules::xmem;
        // Zero is not an allocated page ID. Allow cleanup on partial setup.
        let _ = xmem::XMemFreePhysicalPages(self.ids.len(), self.ids.as_ptr());
    }
}

#[test]
#[ignore = "isolated actual physical queue completion; external watchdog required"]
fn storage_completion_native_pages() {
    let data = pattern(4096);
    let (_dir, file) = file_with(&data);
    let file = CompletionFile(file);
    for separate in [false, true] {
        let mut destinations = Box::new(std::array::from_fn::<_, 3, _>(|_| CompletionPages::new(separate)));
        let pointers = destinations.each_mut().map(|p| p.ids.as_mut_ptr().cast::<c_void>());
        let array = CompletionArray(status_array(3));
        let queue = CompletionQueue(new_queue(1));
        let offsets = completion_offsets(data.len());
        for i in 0..2 {
            let mut r = request(PAGE_DESTINATION, pointers[i],
                                16, file.0.cast_const(), offsets[i] as u64, 16);
            r.page_offset = (PAGE - 8) as u64;
            enqueue(queue.0, &r);
            enqueue_status(queue.0, array.0, i as u32);
        }
        void(queue.0, 0x30);
        let first = [wait(array.0, 0), wait(array.0, 1)];
        let mut r = request(PAGE_DESTINATION, pointers[2],
                            16, file.0.cast_const(), offsets[2] as u64, 16);
        r.page_offset = (PAGE - 8) as u64;
        enqueue(queue.0, &r);
        enqueue_status(queue.0, array.0, 2);
        void(queue.0, 0x30);
        let statuses = completion_statuses(array.0);
        drop(queue);
        assert_eq!(first, [S_OK, END_OF_FILE]);
        assert_eq!(statuses, [S_OK, END_OF_FILE, S_OK]);
        for i in 0..3 {
            // Exact EOF prefix is expected for this generated file: read_into
            // loops until EOF, with precisely three source bytes remaining.
            // Disjoint fallback never publishes a failed fill.
            assert_eq!(destinations[i].seen(), completion_expected(&data, i, !separate));
        }
    }
}
