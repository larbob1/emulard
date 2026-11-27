// SPDX-License-Identifier: GPL-3.0-or-later
//! Serial CPU model, NOT a GPU instrumentation or synchronization implementation.
//! External callers must establish coverage, real fence completion and publication.
use std::sync::Arc;

const PAGE: u64 = 4096;
const MAX_PAGES: u64 = 4096;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Span { start: u64, end: u64 }
impl Span {
    pub fn new(start: u64, len: u64) -> Option<Self> {
        let end = start.checked_add(len)?;
        (end > start).then_some(Self { start, end })
    }
    fn pages(self) -> u64 { (self.end - 1) / PAGE - self.start / PAGE + 1 }
}

#[derive(Clone)]
pub struct Ticket(Arc<()>);
impl Ticket {
    fn matches(&self, other: &Self) -> bool { Arc::ptr_eq(&self.0, &other.0) }
}

/// A model fence identity, independent of the numeric fence value.
#[derive(Clone)]
pub struct FenceDomain(Arc<()>);
impl FenceDomain {
    pub fn new() -> Self { Self(Arc::new(())) }
    fn matches(&self, other: &Self) -> bool { Arc::ptr_eq(&self.0, &other.0) }
}

/// Ordered publication stages. This is a serial protocol model, not a
/// lock or an implementation of the effects themselves.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Stage { Handback, GenerationsAndAliases, ReadbackVisible, TitleSignals }

impl Stage {
    fn next(self) -> Option<Self> {
        match self {
            Self::Handback => Some(Self::GenerationsAndAliases),
            Self::GenerationsAndAliases => Some(Self::ReadbackVisible),
            Self::ReadbackVisible => Some(Self::TitleSignals),
            Self::TitleSignals => None,
        }
    }
}

/// Only an externally proven no-effect failure may be retried directly.
/// Unknown or partially applied effects require external reconciliation.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Outcome { Done, NoEffect, Uncertain }

// These are assertions in the model, not evidence from actual shader analysis.
// Every category is necessary; none can be inferred from a zero bitmap.
#[derive(Clone, Copy, Default)]
pub struct Coverage {
    pub stores: bool,
    pub atomics: bool,
    pub non_shader_writes: bool,
    pub descriptors: bool,
    pub backing_identity: bool,
    pub alias_footprint: bool,
    pub fault_free: bool,
}

impl Coverage {
    fn complete(self) -> bool {
        self.stores && self.atomics && self.non_shader_writes && self.descriptors
            && self.backing_identity && self.alias_footprint && self.fault_free
    }
}

pub struct Report {
    pub ticket: Ticket,
    pub fence: u64,
    pub coverage: Coverage,
    pub words: Vec<u64>,
}

#[derive(Debug, PartialEq, Eq)]
pub enum Plan {
    // Use the existing authoritative path, including its complete footprint.
    // Never interpret unknown coverage as merely all pages of this region.
    Authoritative,
    // Candidate compare/readback ranges, NOT permission to overwrite bytes.
    Sparse(Vec<Span>),
}

#[derive(Debug, PartialEq, Eq)]
pub enum Error { NotCompleted, NotPlanned, AlreadyPlanned, AlreadyPublished, NotPublished, InvalidFence, PublicationFailed, WrongStage, Quarantined }

pub struct Flight<T> {
    ticket: Ticket,
    fence: u64,
    domain: FenceDomain,
    region: Span,
    // Model-only stand-in for an aggregate of real retained backing and descriptor leases.
    pin: Option<Arc<T>>,
    plan: Option<Plan>,
    next_stage: Option<Stage>,
    quarantined: bool,
}

impl<T> Flight<T> {
    pub fn new(domain: FenceDomain, fence: u64, region: Span, pin: Arc<T>) -> Result<Self, Error> {
        if fence == 0 || fence == u64::MAX { return Err(Error::InvalidFence); }
        Ok(Self { ticket: Ticket(Arc::new(())), fence, domain, region, pin: Some(pin), plan: None, next_stage: Some(Stage::Handback), quarantined: false })
    }

    pub fn ticket(&self) -> Ticket { self.ticket.clone() }

    // completed_fence must come from the same real queue/fence domain.
    // A device-loss sentinel or failed fence query must be rejected upstream.
    // Missing/wrong/malformed report cannot produce sparse work.
    pub fn plan(&mut self, domain: &FenceDomain, completed_fence: u64, report: Option<&Report>) -> Result<&Plan, Error> {
        if self.plan.is_some() { return Err(Error::AlreadyPlanned); }
        if !self.domain.matches(domain) || completed_fence == u64::MAX || completed_fence < self.fence {
            return Err(Error::NotCompleted);
        }
        self.plan = Some(report.and_then(|r| self.sparse(r)).unwrap_or(Plan::Authoritative));
        Ok(self.plan.as_ref().unwrap())
    }

    fn sparse(&self, report: &Report) -> Option<Plan> {
        if !self.ticket.matches(&report.ticket) || self.fence != report.fence || !report.coverage.complete() {
            return None;
        }
        let pages = self.region.pages();
        if pages > MAX_PAGES || report.words.len() != pages.div_ceil(64) as usize {
            return None;
        }
        let tail = pages % 64;
        if tail != 0 && report.words.last().copied()? >> tail != 0 {
            return None;
        }
        let first_page = self.region.start / PAGE;
        let mut spans: Vec<Span> = Vec::new();
        for i in 0..pages {
            if report.words[(i / 64) as usize] & (1u64 << (i % 64)) == 0 { continue; }
            let base = (first_page + i).checked_mul(PAGE)?;
            let start = base.max(self.region.start);
            // Last page may end past u64::MAX; clip to representable region.
            let end = base.saturating_add(PAGE).min(self.region.end);
            if let Some(last) = spans.last_mut() {
                if last.end == start { last.end = end; continue; }
            }
            spans.push(Span { start, end });
        }
        Some(Plan::Sparse(spans))
    }

    // Invoke a stage only after all previous stages completed. Mark the
    // flight uncertain before executing any effect: even a panic/unwind
    // must not permit automatic replay. The closure's result is a modeled
    // assertion; the real caller needs an audited effect/recovery contract.
    pub fn step(&mut self, stage: Stage, effect: impl FnOnce() -> Outcome) -> Result<(), Error> {
        if self.plan.is_none() { return Err(Error::NotPlanned); }
        if self.quarantined { return Err(Error::Quarantined); }
        let expected = self.next_stage.ok_or(Error::AlreadyPublished)?;
        if stage != expected { return Err(Error::WrongStage); }
        self.quarantined = true;
        match effect() {
            Outcome::Done => {
                self.next_stage = stage.next();
                self.quarantined = false;
                Ok(())
            }
            Outcome::NoEffect => {
                self.quarantined = false;
                Err(Error::PublicationFailed)
            }
            Outcome::Uncertain => Err(Error::Quarantined),
        }
    }

    // Explicit successful release only. Dropping this model itself is NOT
    // a safe production cancellation path; a real owner must retain failures.
    pub fn retire(&mut self) -> Result<Arc<T>, Error> {
        if self.quarantined { return Err(Error::Quarantined); }
        if self.plan.is_none() || self.next_stage.is_some() { return Err(Error::NotPublished); }
        self.pin.take().ok_or(Error::NotPublished)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn coverage() -> Coverage {
        Coverage { stores: true, atomics: true, non_shader_writes: true, descriptors: true,
            backing_identity: true, alias_footprint: true, fault_free: true }
    }
    fn flight(start: u64, len: u64) -> Flight<()> {
        Flight::new(FenceDomain::new(), 7, Span::new(start, len).unwrap(), Arc::new(())).unwrap()
    }
    const STAGES: [Stage; 4] = [Stage::Handback, Stage::GenerationsAndAliases, Stage::ReadbackVisible, Stage::TitleSignals];
    fn finish<T>(f: &mut Flight<T>) {
        for stage in STAGES { f.step(stage, || Outcome::Done).unwrap(); }
    }
    // Helper uses the owning fence domain, except explicit wrong-domain tests.
    fn plan<'a, T>(f: &'a mut Flight<T>, value: u64, report: Option<&Report>) -> Result<&'a Plan, Error> {
        let domain = f.domain.clone();
        f.plan(&domain, value, report)
    }
    fn report(f: &Flight<()>, words: Vec<u64>) -> Report {
        Report { ticket: f.ticket(), fence: 7, coverage: coverage(), words }
    }
    #[test]
    fn sparse_clips_and_joins_pages() {
        let mut f = flight(17, PAGE * 4 - 34);
        let r = report(&f, vec![0b1011]);
        assert_eq!(plan(&mut f, 7, Some(&r)), Ok(&Plan::Sparse(vec![
            Span::new(17, PAGE * 2 - 17).unwrap(),
            Span::new(PAGE * 3, PAGE - 17).unwrap(),
        ])));
    }
    #[test]
    fn zero_and_full_masks() {
        let mut f = flight(13, PAGE * 2);
        let r = report(&f, vec![0]);
        assert_eq!(plan(&mut f, 7, Some(&r)), Ok(&Plan::Sparse(vec![])));
        let mut f = flight(13, PAGE * 2);
        let r = report(&f, vec![7]);
        assert_eq!(plan(&mut f, 8, Some(&r)), Ok(&Plan::Sparse(vec![Span::new(13, PAGE * 2).unwrap()])));
    }
    #[test]
    fn no_fence_or_device_loss_cannot_plan() {
        let mut f = flight(0, PAGE);
        let r = report(&f, vec![1]);
        for n in [0, 6, u64::MAX] {
            assert_eq!(plan(&mut f, n, Some(&r)), Err(Error::NotCompleted));
        }
        assert!(plan(&mut f, 7, Some(&r)).is_ok());
        assert_eq!(plan(&mut f, 8, Some(&r)), Err(Error::AlreadyPlanned));
    }
    #[test]
    fn wrong_fence_domain_and_reserved_fence_values_are_rejected() {
        let mut f = flight(0, PAGE);
        let r = report(&f, vec![1]);
        let unrelated = FenceDomain::new();
        assert_eq!(f.plan(&unrelated, 1000, Some(&r)), Err(Error::NotCompleted));
        assert!(plan(&mut f, 7, Some(&r)).is_ok());
        for fence in [0, u64::MAX] {
            assert!(matches!(Flight::new(FenceDomain::new(), fence, Span::new(0, PAGE).unwrap(), Arc::new(())), Err(Error::InvalidFence)));
        }
    }

    #[test]
    fn readback_and_title_signal_acknowledgements_required() {
        let mut f = flight(0, PAGE);
        plan(&mut f, 7, None).unwrap();
        f.step(Stage::Handback, || Outcome::Done).unwrap();
        f.step(Stage::GenerationsAndAliases, || Outcome::Done).unwrap();
        assert_eq!(f.step(Stage::ReadbackVisible, || Outcome::NoEffect), Err(Error::PublicationFailed));
        assert_eq!(f.retire(), Err(Error::NotPublished));
        f.step(Stage::ReadbackVisible, || Outcome::Done).unwrap();
        assert_eq!(f.step(Stage::TitleSignals, || Outcome::NoEffect), Err(Error::PublicationFailed));
        assert_eq!(f.retire(), Err(Error::NotPublished));
        f.step(Stage::TitleSignals, || Outcome::Done).unwrap();
        assert!(f.retire().is_ok());
    }

    #[test]
    fn duplicate_or_out_of_order_effect_never_executes() {
        let mut f = flight(0, PAGE);
        assert_eq!(f.step(Stage::Handback, || panic!("before plan")), Err(Error::NotPlanned));
        plan(&mut f, 7, None).unwrap();
        for stage in STAGES {
            for wrong in STAGES {
                if wrong != stage {
                    assert_eq!(f.step(wrong, || panic!("wrong stage executed")), Err(Error::WrongStage));
                }
            }
            f.step(stage, || Outcome::Done).unwrap();
        }
        assert_eq!(f.step(Stage::Handback, || panic!("repeated effect")), Err(Error::AlreadyPublished));
        assert!(f.retire().is_ok());
    }

    #[test]
    fn definite_no_effect_failure_retries_only_current_stage() {
        for failing in 0..STAGES.len() {
            let mut f = flight(0, PAGE);
            plan(&mut f, 7, None).unwrap();
            let mut successes = Vec::new();
            for (i, stage) in STAGES.into_iter().enumerate() {
                if i == failing {
                    for _ in 0..3 {
                        assert_eq!(f.step(stage, || Outcome::NoEffect), Err(Error::PublicationFailed));
                        assert_eq!(f.retire(), Err(Error::NotPublished));
                    }
                    for old in &STAGES[..i] {
                        assert_eq!(f.step(*old, || panic!("replayed prior effect")), Err(Error::WrongStage));
                    }
                }
                f.step(stage, || { successes.push(stage); Outcome::Done }).unwrap();
            }
            assert_eq!(successes, STAGES);
            assert!(f.retire().is_ok());
        }
    }

    #[test]
    fn uncertain_failure_at_every_stage_quarantines_and_retains_lease() {
        for failing in 0..STAGES.len() {
            let pin = Arc::new(42);
            let weak = Arc::downgrade(&pin);
            let mut f = Flight::new(FenceDomain::new(), 7, Span::new(0, PAGE).unwrap(), pin).unwrap();
            plan(&mut f, 7, None).unwrap();
            for stage in &STAGES[..failing] { f.step(*stage, || Outcome::Done).unwrap(); }
            assert_eq!(f.step(STAGES[failing], || Outcome::Uncertain), Err(Error::Quarantined));
            for stage in STAGES {
                assert_eq!(f.step(stage, || panic!("quarantined effect")), Err(Error::Quarantined));
            }
            assert_eq!(f.retire(), Err(Error::Quarantined));
            assert!(weak.upgrade().is_some());
        }
    }

    #[test]
    fn unwinding_effect_quarantines_before_automatic_retry() {
        let mut f = flight(0, PAGE);
        plan(&mut f, 7, None).unwrap();
        let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            let _ = f.step(Stage::Handback, || panic!("uncertain side effects"));
        }));
        assert!(result.is_err());
        assert_eq!(f.step(Stage::Handback, || panic!("replayed effect")), Err(Error::Quarantined));
        assert_eq!(f.retire(), Err(Error::Quarantined));
    }

    #[test]
    fn cross_flight_and_wrong_fence_fall_back() {
        let a = flight(0, PAGE);
        let mut b = flight(0, PAGE);
        let r = report(&a, vec![0]);
        assert_eq!(plan(&mut b, 7, Some(&r)), Ok(&Plan::Authoritative));
        let mut f = flight(0, PAGE);
        let mut r = report(&f, vec![0]);
        r.fence = 8;
        assert_eq!(plan(&mut f, 8, Some(&r)), Ok(&Plan::Authoritative));
    }
    #[test]
    fn every_coverage_category_is_required() {
        for i in 0..7 {
            let mut f = flight(0, PAGE);
            let mut r = report(&f, vec![0]);
            match i {
                0 => r.coverage.stores = false,
                1 => r.coverage.atomics = false,
                2 => r.coverage.non_shader_writes = false,
                3 => r.coverage.descriptors = false,
                4 => r.coverage.backing_identity = false,
                5 => r.coverage.alias_footprint = false,
                _ => r.coverage.fault_free = false,
            }
            assert_eq!(plan(&mut f, 7, Some(&r)), Ok(&Plan::Authoritative));
        }
        let mut f = flight(0, PAGE);
        assert_eq!(plan(&mut f, 7, None), Ok(&Plan::Authoritative));
    }
    #[test]
    fn malformed_bitmaps_and_capacity_fall_back() {
        for words in [vec![], vec![0, 0], vec![4], vec![u64::MAX]] {
            let mut f = flight(0, PAGE * 2);
            let r = report(&f, words);
            assert_eq!(plan(&mut f, 7, Some(&r)), Ok(&Plan::Authoritative));
        }
        let mut f = flight(0, PAGE * (MAX_PAGES + 1));
        let r = report(&f, vec![0; 65]);
        assert_eq!(plan(&mut f, 7, Some(&r)), Ok(&Plan::Authoritative));
        assert!(Span::new(u64::MAX, 1).is_none());
        assert!(Span::new(0, 0).is_none());
        let mut f = flight(u64::MAX - 32, 32);
        let r = report(&f, vec![1]);
        assert_eq!(plan(&mut f, 7, Some(&r)), Ok(&Plan::Sparse(vec![Span::new(u64::MAX - 32, 32).unwrap()])));
    }
    #[test]
    fn backing_retained_through_failed_publication() {
        let pin = Arc::new(42u32);
        let weak = Arc::downgrade(&pin);
        let mut f = Flight::new(FenceDomain::new(), 7, Span::new(0, PAGE).unwrap(), pin).unwrap();
        assert_eq!(f.step(Stage::Handback, || Outcome::Done), Err(Error::NotPlanned));
        assert_eq!(f.retire(), Err(Error::NotPublished));
        assert_eq!(plan(&mut f, 7, None), Ok(&Plan::Authoritative));
        for stage in STAGES {
            assert_eq!(f.step(stage, || Outcome::NoEffect), Err(Error::PublicationFailed));
            assert_eq!(f.retire(), Err(Error::NotPublished));
            assert!(weak.upgrade().is_some());
            f.step(stage, || Outcome::Done).unwrap();
        }
        assert_eq!(f.step(Stage::Handback, || Outcome::Done), Err(Error::AlreadyPublished));
        let retired = f.retire().unwrap();
        assert_eq!(*retired, 42);
        drop(retired);
        assert!(weak.upgrade().is_none());
        assert_eq!(f.retire(), Err(Error::NotPublished));
    }
    #[test]
    fn separate_flights_keep_separate_backing_leases() {
        let pin = Arc::new(7u32);
        let weak = Arc::downgrade(&pin);
        let mut a = Flight::new(FenceDomain::new(), 1, Span::new(0, PAGE).unwrap(), pin.clone()).unwrap();
        let mut b = Flight::new(FenceDomain::new(), 2, Span::new(0, PAGE).unwrap(), pin).unwrap();
        plan(&mut a, 1, None).unwrap();
        finish(&mut a);
        drop(a.retire().unwrap());
        assert!(weak.upgrade().is_some());
        assert_eq!(plan(&mut b, 1, None), Err(Error::NotCompleted));
        plan(&mut b, 2, None).unwrap();
        finish(&mut b);
        drop(b.retire().unwrap());
        assert!(weak.upgrade().is_none());
    }
    #[test]
    fn deterministic_page_oracle_across_word_boundaries() {
        let mut seed = 0x714b_217c_8a93_u64;
        for pages in [1, 2, 63, 64, 65, 127, 128, 129, 4096] {
            for _ in 0..8 {
                let mut f = flight(17, pages * PAGE - 35 + 18);
                // Region covers exactly pages pages, starting partway through page zero.
                let actual = f.region.pages();
                let mut words = vec![0u64; actual.div_ceil(64) as usize];
                for i in 0..actual {
                    seed ^= seed << 13; seed ^= seed >> 7; seed ^= seed << 17;
                    if seed & 3 == 0 { words[(i/64) as usize] |= 1 << (i%64); }
                }
                let region = f.region;
                let r = report(&f, words.clone());
                let Plan::Sparse(spans) = plan(&mut f, 7, Some(&r)).unwrap() else { panic!("unexpected fallback"); };
                assert!(spans.windows(2).all(|w| w[0].end < w[1].start));
                assert!(spans.iter().all(|s| region.start <= s.start && s.start < s.end && s.end <= region.end));
                for i in 0..actual {
                    let at = (i * PAGE).max(region.start);
                    let expected = words[(i/64) as usize] & (1 << (i%64)) != 0;
                    assert_eq!(spans.iter().any(|s| s.start <= at && at < s.end), expected);
                }
            }
        }
    }
}
