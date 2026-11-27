// SPDX-License-Identifier: GPL-3.0-or-later
//! Serial lifecycle model, no GPU objects, I/O, waits or runtime registration.
use std::sync::Arc;

#[derive(Clone)]
pub struct Domain(Arc<()>);
impl Domain { pub fn new() -> Self { Self(Arc::new(())) } }

#[derive(Clone)]
pub struct Lease { index: usize, identity: Arc<()> }

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Outcome { Done, NoEffect, Uncertain }
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Phase { Reserved, InFlight, Complete, Copied, Published, Signaled, Quarantined }
#[derive(Debug, PartialEq, Eq)]
pub enum Error { Budget, Invalid, Full, Stale, WrongPhase, NotComplete, Failed, Quarantined }

struct Active<T> {
    identity: Arc<()>,
    domain: Domain,
    fence: u64,
    phase: Phase,
    pin: Arc<T>,
}
struct Slot<T> { capacity: u64, active: Option<Active<T>> }
pub struct Pool<T> { slots: Vec<Slot<T>> }

impl<T> Pool<T> {
    /// Capacities are logical fixed allocation reservations, not real VRAM.
    /// Never allocate more slots at pressure or evict in-flight work.
    pub fn new(capacities: &[u64], budget: u64) -> Result<Self, Error> {
        if capacities.is_empty() || capacities.len() > 64 { return Err(Error::Budget); }
        let mut total = 0u64;
        for &capacity in capacities {
            if capacity == 0 { return Err(Error::Invalid); }
            total = total.checked_add(capacity).ok_or(Error::Budget)?;
        }
        if total > budget { return Err(Error::Budget); }
        Ok(Self { slots: capacities.iter().map(|&capacity| Slot { capacity, active: None }).collect() })
    }
    pub fn reserve(&mut self, bytes: u64, domain: Domain, fence: u64, pin: Arc<T>) -> Result<Lease, Error> {
        if bytes == 0 || fence == 0 || fence == u64::MAX { return Err(Error::Invalid); }
        let (index, slot) = self.slots.iter_mut().enumerate().filter(|(_,s)| s.active.is_none() && s.capacity >= bytes)
            .min_by_key(|(_,s)| s.capacity).ok_or(Error::Full)?;
        let identity = Arc::new(());
        slot.active = Some(Active { identity: identity.clone(), domain, fence, phase: Phase::Reserved, pin });
        Ok(Lease { index, identity })
    }
    fn active(&mut self, lease: &Lease) -> Result<&mut Active<T>, Error> {
        let active = self.slots.get_mut(lease.index).and_then(|s| s.active.as_mut()).ok_or(Error::Stale)?;
        if !Arc::ptr_eq(&active.identity, &lease.identity) { return Err(Error::Stale); }
        Ok(active)
    }
    /// Pre-mark uncertainty before calling an externally owned effect.
    fn effect(&mut self, lease: &Lease, expected: Phase, next: Phase, run: impl FnOnce() -> Outcome) -> Result<(), Error> {
        let a = self.active(lease)?;
        if a.phase == Phase::Quarantined { return Err(Error::Quarantined); }
        if a.phase != expected { return Err(Error::WrongPhase); }
        a.phase = Phase::Quarantined;
        match run() {
            Outcome::Done => { a.phase = next; Ok(()) }
            Outcome::NoEffect => { a.phase = expected; Err(Error::Failed) }
            Outcome::Uncertain => Err(Error::Quarantined),
        }
    }
    pub fn submit(&mut self, lease: &Lease, run: impl FnOnce() -> Outcome) -> Result<(), Error> {
        self.effect(lease, Phase::Reserved, Phase::InFlight, run)
    }
    pub fn complete(&mut self, lease: &Lease, domain: &Domain, value: u64) -> Result<(), Error> {
        let a = self.active(lease)?;
        if a.phase == Phase::Quarantined { return Err(Error::Quarantined); }
        if a.phase != Phase::InFlight { return Err(Error::WrongPhase); }
        if !Arc::ptr_eq(&a.domain.0, &domain.0) || value < a.fence { return Err(Error::NotComplete); }
        if value == u64::MAX { a.phase = Phase::Quarantined; return Err(Error::Quarantined); }
        a.phase = Phase::Complete;
        Ok(())
    }
    pub fn copy(&mut self, lease: &Lease, run: impl FnOnce() -> Outcome) -> Result<(), Error> {
        self.effect(lease, Phase::Complete, Phase::Copied, run)
    }
    pub fn publish(&mut self, lease: &Lease, run: impl FnOnce() -> Outcome) -> Result<(), Error> {
        self.effect(lease, Phase::Copied, Phase::Published, run)
    }
    pub fn signal(&mut self, lease: &Lease, run: impl FnOnce() -> Outcome) -> Result<(), Error> {
        self.effect(lease, Phase::Published, Phase::Signaled, run)
    }
    /// Cancel only before any submitted effect (including proven no-effect).
    /// All post-submit paths require the full completion protocol.
    pub fn cancel(&mut self, lease: &Lease) -> Result<Arc<T>, Error> {
        self.release(lease, Phase::Reserved)
    }
    pub fn retire(&mut self, lease: &Lease) -> Result<Arc<T>, Error> {
        self.release(lease, Phase::Signaled)
    }
    fn release(&mut self, lease: &Lease, expected: Phase) -> Result<Arc<T>, Error> {
        let a = self.active(lease)?;
        if a.phase == Phase::Quarantined { return Err(Error::Quarantined); }
        if a.phase != expected { return Err(Error::WrongPhase); }
        Ok(self.slots[lease.index].active.take().unwrap().pin)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn done() -> Outcome { Outcome::Done }
    fn setup() -> (Pool<u32>, Domain, Lease) {
        let mut p = Pool::new(&[64],64).unwrap();
        let d = Domain::new();
        let l = p.reserve(32,d.clone(),7,Arc::new(1)).unwrap();
        (p,d,l)
    }
    #[test]
    fn budget_and_best_fit_no_eviction() {
        assert!(matches!(Pool::<()>::new(&[u64::MAX,1],u64::MAX),Err(Error::Budget)));
        assert!(matches!(Pool::<()>::new(&[64,128],191),Err(Error::Budget)));
        let mut p = Pool::new(&[128,64],192).unwrap();
        let d = Domain::new();
        let a = p.reserve(60,d.clone(),1,Arc::new(())).unwrap();
        assert_eq!(a.index,1);
        let b = p.reserve(100,d.clone(),2,Arc::new(())).unwrap();
        assert_eq!(b.index,0);
        assert!(matches!(p.reserve(1,d,3,Arc::new(())),Err(Error::Full)));
    }
    #[test]
    fn complete_then_copy_publish_signal_before_reuse() {
        let (mut p,d,l) = setup();
        assert_eq!(p.copy(&l,|| panic!("premature copy")),Err(Error::WrongPhase));
        p.submit(&l,done).unwrap();
        assert_eq!(p.cancel(&l),Err(Error::WrongPhase));
        assert_eq!(p.retire(&l),Err(Error::WrongPhase));
        p.complete(&l,&d,7).unwrap();
        assert_eq!(p.signal(&l,|| panic!("premature signal")),Err(Error::WrongPhase));
        p.copy(&l,done).unwrap();
        p.publish(&l,done).unwrap();
        assert_eq!(p.retire(&l),Err(Error::WrongPhase));
        p.signal(&l,done).unwrap();
        assert_eq!(*p.retire(&l).unwrap(),1);
        let fresh = p.reserve(32,d,8,Arc::new(2)).unwrap();
        assert_eq!(fresh.index,l.index);
        assert_eq!(p.submit(&l,|| panic!("stale lease")),Err(Error::Stale));
    }
    #[test]
    fn wrong_domain_and_device_loss_never_release() {
        let (mut p,d,l) = setup();
        p.submit(&l,done).unwrap();
        assert_eq!(p.complete(&l,&Domain::new(),1000),Err(Error::NotComplete));
        assert_eq!(p.complete(&l,&d,6),Err(Error::NotComplete));
        assert_eq!(p.complete(&l,&d,u64::MAX),Err(Error::Quarantined));
        assert_eq!(p.complete(&l,&d,7),Err(Error::Quarantined));
        assert_eq!(p.retire(&l),Err(Error::Quarantined));
        assert!(matches!(p.reserve(1,d,8,Arc::new(2)),Err(Error::Full)));
    }
    #[test]
    fn definite_submission_failure_can_cancel_and_retry() {
        let (mut p,d,l) = setup();
        assert_eq!(p.submit(&l,|| Outcome::NoEffect),Err(Error::Failed));
        assert_eq!(*p.cancel(&l).unwrap(),1);
        let l = p.reserve(1,d.clone(),7,Arc::new(3)).unwrap();
        assert_eq!(p.submit(&l,|| Outcome::NoEffect),Err(Error::Failed));
        p.submit(&l,done).unwrap();
        p.complete(&l,&d,7).unwrap();
        assert_eq!(p.copy(&l,|| Outcome::NoEffect),Err(Error::Failed));
        p.copy(&l,done).unwrap();
        assert_eq!(p.copy(&l,|| panic!("repeated copy")),Err(Error::WrongPhase));
    }
    #[test]
    fn uncertainty_at_any_effect_retains_pin_and_slot() {
        for failing in 0..4 {
            let mut p = Pool::new(&[64],64).unwrap();
            let d = Domain::new();
            let pin = Arc::new(1);
            let weak = Arc::downgrade(&pin);
            let l = p.reserve(32,d.clone(),7,pin).unwrap();
            let outcome = |i| if i == failing { Outcome::Uncertain } else { Outcome::Done };
            let _ = p.submit(&l,|| outcome(0));
            let _ = p.complete(&l,&d,7);
            let _ = p.copy(&l,|| outcome(1));
            let _ = p.publish(&l,|| outcome(2));
            let _ = p.signal(&l,|| outcome(3));
            assert_eq!(p.retire(&l),Err(Error::Quarantined));
            assert_eq!(p.cancel(&l),Err(Error::Quarantined));
            assert!(weak.upgrade().is_some());
            assert!(matches!(p.reserve(1,d,8,Arc::new(2)),Err(Error::Full)));
        }
    }
    #[test]
    fn unwind_quarantines_and_foreign_pool_lease_is_stale() {
        let (mut p,_,l) = setup();
        let (mut other,_,_) = setup();
        assert_eq!(other.submit(&l,|| panic!("foreign lease")),Err(Error::Stale));
        assert!(std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            let _ = p.submit(&l,|| panic!("uncertain submission"));
        })).is_err());
        assert_eq!(p.submit(&l,done),Err(Error::Quarantined));
        assert_eq!(p.cancel(&l),Err(Error::Quarantined));
    }
}
