// SPDX-License-Identifier: GPL-3.0-or-later
//! Standalone review of one worker-local Vec slot for raw file bounce buffers.
//! No runtime hooks. Cap is a synthetic fixture parameter, not a policy.
//! Counts capacity reuse, not allocator calls or process resident memory.

#[derive(Debug, PartialEq, Eq)]
enum Acquisition { ReusedCapacity, FreshCapacity }

struct Scratch {
    idle: Vec<u8>,
    limit: usize,
}

impl Scratch {
    fn new(limit: usize) -> Self {
        Self { idle: Vec::new(), limit }
    }

    fn retained(&self) -> usize { self.idle.capacity() }

    fn trim(&mut self) { self.idle = Vec::new(); }

    fn run<T, E>(&mut self, size: usize,
                 op: impl FnOnce(&mut [u8]) -> Result<T, E>)
                 -> (Result<T, E>, Acquisition) {
        // Take ownership before executing user work. On unwind the local
        // drops, and the slot stays empty. Oversize discards idle storage
        // before creating a new allocation, to avoid extra overlap.
        let mut data = std::mem::take(&mut self.idle);
        if size > self.limit || self.limit == 0 {
            data = Vec::new();
        }
        let hit = size != 0 && data.capacity() >= size;
        // Clear before resize, even when prior request had the same length:
        // preserve the original vec![0; size] semantics.
        data.clear();
        data.resize(size, 0);
        let result = op(&mut data);
        if result.is_ok() && self.limit != 0 && data.capacity() <= self.limit {
            data.clear();
            self.idle = data;
        }
        (result, if hit { Acquisition::ReusedCapacity } else { Acquisition::FreshCapacity })
    }
}

// Mimics only the existing read-then-copy order. The real kernel guard
// hooks and file read implementation are not part of this isolated model.
fn bounce(slot: &mut Scratch, destination: &mut [u8], input: &[u8], fail: bool)
          -> (Result<(), ()>, Acquisition) {
    slot.run(input.len(), |data| {
        assert!(data.iter().all(|&x| x == 0));
        if fail {
            let half = input.len() / 2;
            data[..half].copy_from_slice(&input[..half]);
            return Err(());
        }
        data.copy_from_slice(input);
        destination[..data.len()].copy_from_slice(data);
        Ok(())
    })
}

#[test]
fn repeated_reads_reuse_capacity_and_preserve_bytes() {
    let mut slot = Scratch::new(65536);
    let mut dest = vec![0xA5; 4096 + 8];
    let mut hits = 0;
    for i in 0..100u8 {
        let data = vec![i; 4096];
        let (result, acquisition) = bounce(&mut slot, &mut dest, &data, false);
        assert_eq!(result, Ok(()));
        hits += usize::from(acquisition == Acquisition::ReusedCapacity);
        assert_eq!(&dest[..4096], &data[..]);
        assert_eq!(&dest[4096..], &[0xA5; 8]);
    }
    assert_eq!(hits, 99);
    assert!((4096..=65536).contains(&slot.retained()));
}

#[test]
fn same_and_varying_sizes_are_zero_initialized() {
    let mut slot = Scratch::new(65536);
    for size in [8192, 4096, 4096, 8192, 0, 32, 8192] {
        let (result, _) = slot.run(size, |data| {
            assert_eq!(data.len(), size);
            assert!(data.iter().all(|&x| x == 0));
            data.fill(0xFF);
            Ok::<_, ()>(())
        });
        assert!(result.is_ok());
        assert!(slot.retained() <= 65536);
    }
}

#[test]
fn partial_read_failure_never_copies_and_discards_slot() {
    let mut slot = Scratch::new(65536);
    let mut dest = [0xA5; 128];
    assert!(bounce(&mut slot, &mut dest, &[1; 128], false).0.is_ok());
    dest.fill(0xA5);
    assert_eq!(bounce(&mut slot, &mut dest, &[2; 128], true).0, Err(()));
    assert_eq!(dest, [0xA5; 128]);
    assert_eq!(slot.retained(), 0);
    assert_eq!(bounce(&mut slot, &mut dest, &[3; 128], false),
               (Ok(()), Acquisition::FreshCapacity));
    assert_eq!(dest, [3; 128]);
}

#[test]
fn oversize_and_actual_capacity_limit() {
    let mut slot = Scratch::new(1024);
    assert!(slot.run(512, |_| Ok::<_, ()>(())).0.is_ok());
    assert!(slot.retained() <= 1024);
    assert!(slot.run(1025, |_| Ok::<_, ()>(())).0.is_ok());
    assert_eq!(slot.retained(), 0);
    // Growth may round above the cap even when request size is <= limit.
    // Check actual capacity, not requested length, after every operation.
    for size in [1, 7, 15, 129, 513, 1000, 1024, 1] {
        assert!(slot.run(size, |_| Ok::<_, ()>(())).0.is_ok());
        assert!(slot.retained() <= 1024);
    }
}

#[test]
fn disabled_retains_no_capacity_and_empty_is_valid() {
    let mut slot = Scratch::new(0);
    for size in [0, 64, 64, 0] {
        let (result, acquisition) = slot.run(size, |data| {
            assert_eq!(data.len(), size);
            Ok::<_, ()>(())
        });
        assert!(result.is_ok());
        assert_eq!(acquisition, Acquisition::FreshCapacity);
        assert_eq!(slot.retained(), 0);
    }
}

#[test]
fn panic_leaves_slot_empty() {
    let mut slot = Scratch::new(1024);
    assert!(slot.run(512, |_| Ok::<_, ()>(())).0.is_ok());
    let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        slot.run::<(), ()>(512, |data| {
            data.fill(3);
            panic!("fixture panic");
        });
    }));
    assert!(result.is_err());
    assert_eq!(slot.retained(), 0);
}

#[test]
fn multiple_slots_have_bounded_idle_capacity_and_trim() {
    const WORKERS: usize = 16;
    const LIMIT: usize = 65536;
    let mut slots: Vec<_> = (0..WORKERS).map(|_| Scratch::new(LIMIT)).collect();
    for (i, slot) in slots.iter_mut().enumerate() {
        assert!(slot.run(4096 * (i + 1), |_| Ok::<_, ()>(())).0.is_ok());
    }
    let total: usize = slots.iter().map(Scratch::retained).sum();
    assert!(total <= WORKERS * LIMIT);
    for slot in &mut slots { slot.trim(); }
    assert_eq!(slots.iter().map(Scratch::retained).sum::<usize>(), 0);
}
