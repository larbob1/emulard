// SPDX-License-Identifier: GPL-3.0-or-later
// Append only to the pinned prepared descriptor/host.rs in disposable native CI.
#[cfg(all(test, feature = "diagnostics"))]
mod ai2_descriptor_retry_baseline {
    use super::*;

    type Snapshot = (u64, u64, u64, u8, u64, (u64, u64, u64, u8, u64));

    fn snapshot(q: &TextureQueue, index: u32) -> Snapshot {
        let w = q.slots.get(&index).expect("owned queue entry");
        (w.due, w.written, w.write, w.looks, w.mapped, w.checked)
    }

    #[test]
    fn actual_descriptor_generation_and_retry_bounds() {
        let mut q = TextureQueue::default();
        const INDEX: u32 = 7;
        q.written(INDEX, 10, 12, false);
        let old = snapshot(&q, INDEX).2;
        assert_eq!(q.due(11, 1), vec![]);
        assert_eq!(q.due(12, 1), vec![(INDEX, old)]);
        q.recheck(INDEX, old, 20, (0x1000, 64), 0x1234, 2, 12);
        q.hold(INDEX, old, 30);
        // A real descriptor write replaces the prior generation.
        q.written(INDEX, 21, 22, false);
        let current = snapshot(&q, INDEX);
        assert_ne!(current.2, old);
        assert_eq!(current, (22, 21, current.2, 0, 0, (0,0,0,0,0)));
        q.written(INDEX, 99, 99, true);
        assert_eq!(snapshot(&q, INDEX), current);
        assert!(q.same(INDEX, old).is_none());
        q.done(INDEX, old);
        q.later(INDEX, old, 100, 32);
        q.partly(INDEX, old, 100, 64);
        q.recheck(INDEX, old, 100, (0x2000, 32), 0x5678, 3, 98);
        q.hold(INDEX, old, 100);
        assert_eq!(q.room(0), 0);
        assert_eq!(snapshot(&q, INDEX), current);
        assert_eq!(q.due(22, 1), vec![(INDEX, current.2)]);
        // A mapping change creates a new generation too, keeps earlier due.
        q.partly(INDEX, current.2, 24, 16);
        q.changed(INDEX, 23, 50);
        let changed = snapshot(&q, INDEX);
        assert_ne!(changed.2, current.2);
        assert_eq!(changed, (24,23,changed.2,0,0,(0,0,0,0,0)));
        q.done(INDEX, current.2);
        assert_eq!(snapshot(&q, INDEX), changed);
        let generation = changed.2;
        assert!(q.same(INDEX, generation).is_some());
        let mut now = 24u64;
        for look in 0..270u32 {
            // Independent expected capped sequence, no unchecked large shifts.
            let delta = match look { 0=>1,1=>2,2=>4,3=>8,_=>10 };
            q.later(INDEX, generation, now, 10);
            let w = snapshot(&q, INDEX);
            assert_eq!(w.0, now + delta);
            assert_eq!(w.3, look.saturating_add(1).min(255) as u8);
            assert_eq!(w.2,generation);
            assert!(q.due(w.0 - 1, 1).is_empty());
            assert_eq!(q.due(w.0, 0), vec![]);
            assert_eq!(q.due(w.0, 1), vec![(INDEX,generation)]);
            now = w.0;
        }
        q.later(INDEX, generation, now, 0);
        assert_eq!(snapshot(&q, INDEX).0, now+1);
        q.done(INDEX, generation);
        assert!(!q.slots.contains_key(&INDEX));
        eprintln!("descriptor_generation stale_writes=2 stale_operations=7 retry_steps=271 final_looks=255 done=1");
    }

    #[test]
    fn actual_descriptor_retry_retains_prior_metadata() {
        // These are expected BASELINE witnesses, not a repaired behavior.
        // No pointers are dereferenced; fingerprint/address are opaque tokens.
        let mut q = TextureQueue::default();
        const INDEX:u32 = 9;
        q.written(INDEX, 1, 1, false);
        let write = snapshot(&q, INDEX).2;
        q.recheck(INDEX, write, 10, (0x1000, 64), 0x1234, 2, 1);
        let prior = q.checked(INDEX).unwrap();
        q.later(INDEX, write, 10, 16);
        assert_eq!(snapshot(&q,INDEX).0,12);
        assert_eq!(q.checked(INDEX),Some(prior));
        assert_eq!(q.mapped(INDEX),0);
        assert_eq!(q.due(12,1),vec![(INDEX,write)]);
        // Separate fresh generation for the partial-coverage witness.
        q.changed(INDEX, 13, 13);
        let write = snapshot(&q, INDEX).2;
        assert_eq!(q.checked(INDEX),None);
        q.partly(INDEX, write, 14, 48);
        q.later(INDEX, write, 14, 16);
        assert_eq!(q.mapped(INDEX),48);
        assert_eq!(snapshot(&q,INDEX).0,15);
        assert_eq!(q.due(15,1),vec![(INDEX,write)]);
        // Passing zero to partly still records positive prior coverage.
        q.partly(INDEX, write, 16, 0);
        assert_eq!(q.mapped(INDEX),1);
        q.changed(INDEX, 17, 17);
        let fresh = snapshot(&q, INDEX);
        assert_ne!(fresh.2,write);
        assert_eq!(q.checked(INDEX),None);
        assert_eq!(q.mapped(INDEX),0);
        q.later(INDEX, write, 999, 16);
        assert_eq!(snapshot(&q,INDEX),fresh);
        eprintln!("descriptor_retry_baseline retained_fingerprint=1 retained_mapped=48 partly_zero_mapped=1 new_generation_reset=1");
    }
}
