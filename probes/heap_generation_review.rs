// Review-only, std-only fixture. No host graphics resources.
// Source finding: trustno1-coder/VIctory-NVIDIA 47747d62369a90bd708840622f13c7f55559a6f3
// (GPL-3.0-or-later; original fxceless PR #1324). Independently authored tests.
use std::sync::atomic::{AtomicU64, Ordering};

fn ai0_next_heap_generation(counter: &AtomicU64) -> Option<u64> {
    // Never wrap to an already-issued identity; fail creation at exhaustion.
    counter.fetch_update(Ordering::Relaxed, Ordering::Relaxed, |n| n.checked_add(1)).ok()
}

fn ai0_same_heap_generation(recorded: u64, current: u64) -> bool {
    recorded == current
}

#[cfg(test)]
mod ai0_heap_generation_tests {
    use super::*;
    use std::collections::HashMap;

    #[derive(Clone, Copy)]
    struct Ticket { address: usize, generation: u64, first: usize, count: usize }
    struct Heap { generation: u64, taken: [bool; 4] }

    fn release(registry: &mut HashMap<usize, Heap>, ticket: Ticket) {
        if let Some(h) = registry.get_mut(&ticket.address) {
            if ai0_same_heap_generation(ticket.generation, h.generation) {
                h.taken[ticket.first..ticket.first + ticket.count].fill(false);
            }
        }
    }

    #[test]
    fn replacement_at_same_address_is_not_released() {
        let mut live = HashMap::new();
        let old = Ticket { address: 7, generation: 1, first: 1, count: 2 };
        live.insert(7, Heap { generation: 1, taken: [true; 4] });
        live.remove(&7);
        release(&mut live, old); // missing registry entry
        live.insert(7, Heap { generation: 2, taken: [true; 4] });
        release(&mut live, old);
        assert_eq!(live[&7].taken, [true; 4]);
        release(&mut live, Ticket { generation: 2, ..old });
        assert_eq!(live[&7].taken, [true, false, false, true]);
    }

    #[test]
    fn completion_drains_tickets_before_later_drop() {
        let mut live = HashMap::new();
        live.insert(1, Heap { generation: 9, taken: [true; 4] });
        let mut tickets = vec![Ticket { address: 1, generation: 9, first: 0, count: 1 },
                               Ticket { address: 1, generation: 9, first: 2, count: 1 }];
        for t in tickets.drain(..) { release(&mut live, t); }
        assert_eq!(live[&1].taken, [false, true, false, true]);
        // Another recording can allocate the released slots before old State drops.
        live.get_mut(&1).unwrap().taken = [true; 4];
        for t in tickets { release(&mut live, t); }
        assert_eq!(live[&1].taken, [true; 4]);
    }

    #[test]
    fn concurrent_generation_allocation_is_unique() {
        let counter = AtomicU64::new(1);
        let mut issued = std::thread::scope(|s| {
            let workers: Vec<_> = (0..8).map(|_| s.spawn(|| {
                (0..128).map(|_| ai0_next_heap_generation(&counter).unwrap())
                    .collect::<Vec<_>>()
            })).collect();
            workers.into_iter().flat_map(|w| w.join().unwrap()).collect::<Vec<_>>()
        });
        issued.sort_unstable();
        assert_eq!(issued, (1..=1024).collect::<Vec<u64>>());
    }

    #[test]
    fn exhaustion_never_wraps() {
        let counter = AtomicU64::new(u64::MAX - 1);
        assert_eq!(ai0_next_heap_generation(&counter), Some(u64::MAX - 1));
        assert_eq!(ai0_next_heap_generation(&counter), None);
        assert_eq!(ai0_next_heap_generation(&counter), None);
        assert_eq!(counter.load(Ordering::Relaxed), u64::MAX);
    }
}
