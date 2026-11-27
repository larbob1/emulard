// SPDX-License-Identifier: GPL-3.0-or-later
//! Review-only completion evidence model. No Windows calls, actual GPU,
//! recovery/termination policy, or permission to reclaim runtime resources.

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Evidence {
    Confirmed,
    Unknown,
    Removed,
}

#[derive(Clone, Copy)]
struct Receipt {
    signal_ok: bool,
    registration_ok: bool,
    wait_ok: bool,
    completed: Option<u64>,
    device_ok: bool,
}

fn classify(target: u64, receipt: Receipt) -> Evidence {
    // D3D12 GetCompletedValue uses UINT64_MAX for removal. Never
    // interpret that sentinel as every fence having completed.
    if !receipt.device_ok || receipt.completed == Some(u64::MAX) {
        return Evidence::Removed;
    }
    // Conservative model of the synchronous wait path only. Alternative
    // independent proof/recovery after a failed wait is not modeled.
    if !receipt.signal_ok || !receipt.registration_ok || !receipt.wait_ok {
        return Evidence::Unknown;
    }
    match receipt.completed {
        Some(value) if target != 0 && target != u64::MAX && value >= target => Evidence::Confirmed,
        _ => Evidence::Unknown,
    }
}

#[derive(Debug, PartialEq, Eq)]
struct Flight {
    logical: u64,
    fence: u64,
}

#[derive(Default)]
struct Ledger {
    pending: Vec<Flight>,
    published: Vec<u64>,
    recycled: Vec<u64>,
}

impl Ledger {
    fn land_front(&mut self, receipt: Receipt, readback_ok: bool) -> Evidence {
        let Some(front) = self.pending.first() else { return Evidence::Unknown };
        let evidence = classify(front.fence, receipt);
        if evidence != Evidence::Confirmed {
            return evidence;
        }
        // Fence confirmation alone is not successful title publication.
        if !readback_ok {
            return Evidence::Unknown;
        }
        let flight = self.pending.remove(0);
        self.published.push(flight.logical);
        self.recycled.push(flight.logical);
        Evidence::Confirmed
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn receipt(completed: u64) -> Receipt {
        Receipt { signal_ok: true, registration_ok: true, wait_ok: true,
                  completed: Some(completed), device_ok: true }
    }

    fn ledger() -> Ledger {
        Ledger {
            pending: vec![Flight { logical: 3, fence: 17 }, Flight { logical: 4, fence: 29 }],
            ..Ledger::default()
        }
    }

    fn assert_held(l: &Ledger) {
        assert_eq!(l.pending, ledger().pending);
        assert!(l.published.is_empty());
        assert!(l.recycled.is_empty());
    }

    #[test]
    fn failed_signal_registration_or_wait_is_not_completion() {
        for r in [
            Receipt { signal_ok: false, ..receipt(17) },
            Receipt { registration_ok: false, ..receipt(17) },
            Receipt { wait_ok: false, ..receipt(17) },
        ] {
            let mut l = ledger();
            assert_eq!(l.land_front(r, true), Evidence::Unknown);
            assert_held(&l);
        }
    }

    #[test]
    fn unreached_or_missing_fence_is_not_completion() {
        for r in [receipt(16), Receipt { completed: None, ..receipt(17) }] {
            let mut l = ledger();
            assert_eq!(l.land_front(r, true), Evidence::Unknown);
            assert_held(&l);
        }
    }

    #[test]
    fn removal_is_not_an_infinite_completed_fence() {
        for r in [receipt(u64::MAX), Receipt { device_ok: false, ..receipt(17) }] {
            let mut l = ledger();
            assert_eq!(l.land_front(r, true), Evidence::Removed);
            assert_held(&l);
        }
    }

    #[test]
    fn confirmed_fence_does_not_imply_successful_readback() {
        let mut l = ledger();
        assert_eq!(l.land_front(receipt(17), false), Evidence::Unknown);
        assert_held(&l);
    }

    #[test]
    fn only_confirmed_prefix_publishes_and_recycles() {
        let mut l = ledger();
        assert_eq!(l.land_front(receipt(17), true), Evidence::Confirmed);
        assert_eq!(l.published, [3]);
        assert_eq!(l.recycled, [3]);
        assert_eq!(l.pending, [Flight { logical: 4, fence: 29 }]);
        assert_eq!(l.land_front(receipt(28), true), Evidence::Unknown);
        assert_eq!(l.published, [3]);
        assert_eq!(l.recycled, [3]);
        assert_eq!(l.land_front(receipt(29), true), Evidence::Confirmed);
        assert_eq!(l.published, [3, 4]);
        assert_eq!(l.recycled, [3, 4]);
        assert!(l.pending.is_empty());
        assert_eq!(l.land_front(receipt(29), true), Evidence::Unknown);
        assert_eq!(l.recycled, [3, 4]);
    }

    #[test]
    fn reserved_targets_not_confirmed() {
        assert_eq!(classify(0, receipt(17)), Evidence::Unknown);
        assert_eq!(classify(u64::MAX, receipt(17)), Evidence::Unknown);
    }
}
