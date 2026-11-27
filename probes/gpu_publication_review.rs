// SPDX-License-Identifier: GPL-3.0-or-later
//! Review-only evidence contract, NOT a model of actual host.rs execution.
//! No GPU, real owners, retry, rollback, or recovery policy.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct Domain { queue: u64, fence: u64, epoch: u64 }
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct Point { domain: Domain, value: u64 }
#[derive(Clone, Copy)]
struct Receipt {
    // Claimed target of this signal/event/wait sequence, separate from query.
    waited_for: Point,
    point: Point,
    signal_ok: bool,
    registration_ok: bool,
    wait_ok: bool,
    device_ok: bool,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Evidence { Confirmed, Unknown, Removed }
fn valid(p: Point) -> bool { p.value != 0 && p.value != u64::MAX }
fn follows(previous: Point, next: Point) -> bool {
    previous.domain == next.domain && valid(previous) && valid(next)
        && next.value > previous.value
}
fn confirm(target: Point, r: Receipt) -> Evidence {
    // A foreign receipt, even a removal sentinel, is not evidence about this target.
    if target.domain != r.point.domain || !valid(target) {
        return Evidence::Unknown;
    }
    if !r.device_ok || r.point.value == u64::MAX { return Evidence::Removed; }
    if r.waited_for == target && r.signal_ok && r.registration_ok && r.wait_ok
        && r.point.value >= target.value {
        Evidence::Confirmed
    } else { Evidence::Unknown }
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Step { Handback, Readback, Write, Signal, Retire, Recycle }
const ORDER: [Step; 6] = [Step::Handback, Step::Readback, Step::Write,
    Step::Signal, Step::Retire, Step::Recycle];
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Outcome { Done, NotApplied, Indeterminate }
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Record { Pending, Fault { step: Step, outcome: Outcome }, Complete }
struct Review {
    target: Point,
    gpu: bool,
    removed: bool,
    done: Vec<Step>,
    state: Record,
}
impl Review {
    fn new(target: Point) -> Self {
        Self { target, gpu: false, removed: false, done: Vec::new(), state: Record::Pending }
    }
    fn observe(&mut self, receipt: Receipt) -> Evidence {
        // The ledger retains historical successes and faults, but same-domain
        // removal is sticky and forbids further claims of successful effects.
        // This is not a device teardown or resource ownership policy.
        if receipt.point.domain != self.target.domain { return Evidence::Unknown; }
        if self.removed { return Evidence::Removed; }
        let result = confirm(self.target, receipt);
        if result == Evidence::Removed {
            self.removed = true;
            return result;
        }
        if self.state != Record::Pending || self.gpu { return Evidence::Unknown; }
        if result == Evidence::Confirmed { self.gpu = true; }
        result
    }
    // Evidence ledger, not a dispatcher: an indeterminate attempted effect is
    // not rolled back or called successful. Fault is terminal in this model.
    // ORDER is a conservative proposed review gate; upstream synchronous
    // retirement ordering differs and must be independently audited.
    fn record(&mut self, step: Step, result: Outcome) -> bool {
        if self.removed || !self.gpu || self.state != Record::Pending ||
            ORDER.get(self.done.len()) != Some(&step) { return false; }
        if result != Outcome::Done {
            self.state = Record::Fault { step, outcome: result };
            return true;
        }
        self.done.push(step);
        if self.done.len() == ORDER.len() { self.state = Record::Complete; }
        true
    }
    fn retired(&self) -> bool { self.done.contains(&Step::Retire) }
    fn recycled(&self) -> bool { self.done.contains(&Step::Recycle) }
}
// Single-domain reservation witness. Not a queue dispatcher or shared
// synchronization mechanism; tests must not infer actual admission from it.
struct Reservations { domain: Domain, last: Option<Point> }
impl Reservations {
    fn new(domain: Domain) -> Self { Self { domain, last: None } }
    fn reserve(&mut self, target: Point) -> Option<Review> {
        if target.domain != self.domain || !valid(target)
            || self.last.is_some_and(|last| !follows(last, target)) { return None; }
        self.last = Some(target);
        Some(Review::new(target))
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    fn point(value: u64) -> Point {
        Point { domain: Domain { queue: 1, fence: 2, epoch: 3 }, value }
    }
    fn receipt(p: Point) -> Receipt {
        Receipt { waited_for: p, point: p, signal_ok: true, registration_ok: true,
            wait_ok: true, device_ok: true }
    }
    fn ready() -> Review {
        let mut r = Review::new(point(17));
        assert_eq!(r.observe(receipt(point(17))), Evidence::Confirmed);
        r
    }
    #[test]
    fn wrong_queue_fence_or_epoch_is_not_completion() {
        for domain in [Domain { queue: 9, ..point(17).domain },
            Domain { fence: 9, ..point(17).domain },
            Domain { epoch: 9, ..point(17).domain }] {
            let mut r = Review::new(point(17));
            for value in [99, u64::MAX] {
                assert_eq!(r.observe(receipt(Point { domain, value })), Evidence::Unknown);
            }
            assert!(!r.gpu);
            assert!(!r.record(Step::Handback, Outcome::Done));
        }
    }
    #[test]
    fn monotonic_targets_only_within_domain() {
        assert!(follows(point(17), point(29)));
        for value in [0, 16, 17, u64::MAX] {
            assert!(!follows(point(17), point(value)));
        }
        let mut foreign = point(29);
        foreign.domain.epoch += 1;
        assert!(!follows(point(17), foreign));
    }
    #[test]
    fn unknown_or_removed_receipts_have_no_effect() {
        for (x, want) in [
            (receipt(point(16)), Evidence::Unknown),
            (Receipt { wait_ok: false, ..receipt(point(17)) }, Evidence::Unknown),
            (Receipt { registration_ok: false, ..receipt(point(17)) }, Evidence::Unknown),
            (Receipt { signal_ok: false, ..receipt(point(17)) }, Evidence::Unknown),
            (receipt(point(u64::MAX)), Evidence::Removed),
            (Receipt { device_ok: false, ..receipt(point(17)) }, Evidence::Removed),
        ] {
            let mut r = Review::new(point(17));
            assert_eq!(r.observe(x), want);
            assert!(!r.gpu && r.done.is_empty() && !r.retired() && !r.recycled());
        }
    }
    #[test]
    fn failure_before_any_effect_has_empty_prefix() {
        let mut r = ready();
        assert!(r.record(Step::Handback, Outcome::NotApplied));
        assert_eq!(r.state, Record::Fault { step: Step::Handback, outcome: Outcome::NotApplied });
        assert!(r.done.is_empty());
        assert!(!r.record(Step::Handback, Outcome::Done));
        assert!(!r.retired() && !r.recycled());
    }
    #[test]
    fn partial_readback_failure_preserves_handback_evidence() {
        let mut r = ready();
        assert!(r.record(Step::Handback, Outcome::Done));
        assert!(r.record(Step::Readback, Outcome::Indeterminate));
        assert_eq!(r.done, [Step::Handback]);
        assert_eq!(r.state, Record::Fault { step: Step::Readback, outcome: Outcome::Indeterminate });
        assert!(!r.record(Step::Write, Outcome::Done));
        assert!(!r.retired() && !r.recycled());
    }
    #[test]
    fn uncertain_signal_does_not_erase_confirmed_write() {
        let mut r = ready();
        for s in [Step::Handback, Step::Readback, Step::Write] {
            assert!(r.record(s, Outcome::Done));
        }
        assert!(r.record(Step::Signal, Outcome::Indeterminate));
        assert_eq!(r.done, [Step::Handback, Step::Readback, Step::Write]);
        assert!(!r.record(Step::Retire, Outcome::Done));
        assert!(!r.retired() && !r.recycled());
    }
    #[test]
    fn retirement_and_recycle_are_separate_observations() {
        let mut r = ready();
        for s in ORDER[..5].iter().copied() { assert!(r.record(s, Outcome::Done)); }
        assert!(r.retired() && !r.recycled());
        assert!(r.record(Step::Recycle, Outcome::Indeterminate));
        assert!(r.retired() && !r.recycled());
        assert_eq!(r.state, Record::Fault { step: Step::Recycle, outcome: Outcome::Indeterminate });
    }
    #[test]
    fn success_requires_all_steps_in_order_once() {
        let mut r = ready();
        assert!(!r.record(Step::Recycle, Outcome::Done));
        for s in ORDER { assert!(r.record(s, Outcome::Done)); }
        assert_eq!(r.state, Record::Complete);
        assert!(r.retired() && r.recycled());
        assert!(!r.record(Step::Recycle, Outcome::Done));
        assert_eq!(r.done, ORDER);
    }

    #[test]
    fn removal_before_confirmation_cannot_be_cleared_by_success() {
        for lost in [receipt(point(u64::MAX)),
            Receipt { device_ok: false, ..receipt(point(17)) }] {
            let mut r = Review::new(point(17));
            assert_eq!(r.observe(lost), Evidence::Removed);
            assert_eq!(r.observe(receipt(point(17))), Evidence::Removed);
            assert!(r.removed && !r.gpu && r.done.is_empty());
            assert!(!r.record(Step::Handback, Outcome::Done));
        }
    }

    #[test]
    fn removal_after_gpu_confirmation_preserves_effect_prefix() {
        let mut r = ready();
        assert!(r.record(Step::Handback, Outcome::Done));
        assert_eq!(r.observe(receipt(point(u64::MAX))), Evidence::Removed);
        assert_eq!(r.observe(receipt(point(17))), Evidence::Removed);
        assert!(r.gpu && r.removed);
        assert_eq!(r.done, [Step::Handback]);
        assert!(!r.record(Step::Readback, Outcome::Done));
        assert!(!r.retired() && !r.recycled());
    }

    #[test]
    fn removal_after_fault_preserves_uncertain_effect() {
        let mut r = ready();
        assert!(r.record(Step::Handback, Outcome::Indeterminate));
        let before = r.state;
        assert_eq!(r.observe(receipt(point(u64::MAX))), Evidence::Removed);
        assert_eq!(r.state, before);
        assert!(r.removed && r.done.is_empty());
        assert!(!r.record(Step::Handback, Outcome::Done));
    }

    #[test]
    fn foreign_removal_cannot_poison_confirmed_domain() {
        let mut r = ready();
        let mut foreign = point(u64::MAX);
        foreign.domain.epoch += 1;
        assert_eq!(r.observe(receipt(foreign)), Evidence::Unknown);
        assert!(!r.removed && r.gpu);
        assert!(r.record(Step::Handback, Outcome::Done));
    }

    #[test]
    fn higher_query_requires_target_scoped_wait_receipt() {
        let mut r = Review::new(point(17));
        assert_eq!(r.observe(receipt(point(29))), Evidence::Unknown);
        let mut wrong = point(17);
        wrong.domain.fence += 1;
        assert_eq!(r.observe(Receipt { waited_for: wrong, ..receipt(point(29)) }),
            Evidence::Unknown);
        assert_eq!(r.observe(Receipt { waited_for: point(17), ..receipt(point(29)) }),
            Evidence::Confirmed);
        assert!(r.gpu);
    }

    #[test]
    fn reservations_reject_invalid_duplicate_decreasing_and_foreign_targets() {
        let mut book = Reservations::new(point(17).domain);
        assert!(book.reserve(point(0)).is_none());
        let first = book.reserve(point(17)).unwrap();
        assert_eq!(first.target, point(17));
        for value in [0, 16, 17, u64::MAX] {
            assert!(book.reserve(point(value)).is_none());
            assert_eq!(book.last, Some(point(17)));
        }
        let mut foreign = point(29);
        foreign.domain.queue += 1;
        assert!(book.reserve(foreign).is_none());
        let second = book.reserve(point(29)).unwrap();
        assert_eq!(second.target, point(29));
        assert_eq!(book.last, Some(point(29)));
        assert!(!first.gpu && !second.gpu);
    }
}
