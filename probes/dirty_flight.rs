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

/// Stable backing identity in the model. Actual resolution belongs to
/// the mapping/lease owner; this is not a virtual address or slot number.
#[derive(Clone)]
pub struct Backing(Arc<()>);
impl Backing {
    pub fn new() -> Self { Self(Arc::new(())) }
}

#[derive(Debug, PartialEq, Eq)]
pub enum MarkError { UnknownFootprint, WrongBacking, OutsideRegion, InvalidSpan, Invalidated, Capacity }

/// Serial reference marker for one already-resolved backing byte region.
/// No real alias projection, GPU atomic instructions or GPU synchronization.
pub struct Marker {
    ticket: Ticket,
    fence: u64,
    backing: Backing,
    region: Span,
    words: Vec<u64>,
    invalid: bool,
}

fn page_bounds(region: Span, start: u64, len: u64) -> Result<(u64, u64), MarkError> {
    let span = Span::new(start, len).ok_or(MarkError::InvalidSpan)?;
    if span.start < region.start || span.end > region.end {
        return Err(MarkError::OutsideRegion);
    }
    let origin = region.start / PAGE;
    Ok((span.start / PAGE - origin, (span.end - 1) / PAGE - origin))
}

fn mark_bits(words: &mut [u64], first: u64, last: u64) {
    // Inclusive page indices. Never shift by 64; final word is clipped by
    // the previously validated byte span. Overlapping writes only OR bits.
    let a = (first / 64) as usize;
    let b = (last / 64) as usize;
    let low = u64::MAX << (first % 64);
    let high = u64::MAX >> (63 - last % 64);
    if a == b {
        words[a] |= low & high;
    } else {
        words[a] |= low;
        for word in &mut words[a+1..b] { *word = u64::MAX; }
        words[b] |= high;
    }
}

#[derive(Debug, PartialEq, Eq)]
pub struct Observation {
    pub candidate_pages: u64,
    pub changed_pages: u64,
    pub missed_pages: u64,
    pub extra_pages: u64,
}

/// Independent exact completed-scan spans, NOT a second rendering path.
/// None means missing/ineligible evidence, not zero changed bytes.
impl Marker {
    pub fn new<T>(flight: &Flight<T>, backing: Backing) -> Result<Self, MarkError> {
        let pages = flight.region.pages();
        if pages > MAX_PAGES { return Err(MarkError::Capacity); }
        Ok(Self {
            ticket: flight.ticket(), fence: flight.fence, backing,
            region: flight.region, words: vec![0; pages.div_ceil(64) as usize], invalid: false,
        })
    }

    pub fn unknown(&mut self) -> MarkError {
        self.invalid = true;
        MarkError::UnknownFootprint
    }

    pub fn mark(&mut self, backing: &Backing, start: u64, len: u64) -> Result<(), MarkError> {
        if self.invalid { return Err(MarkError::Invalidated); }
        let result = if !Arc::ptr_eq(&self.backing.0, &backing.0) {
            Err(MarkError::WrongBacking)
        } else {
            page_bounds(self.region, start, len)
        };
        match result {
            Ok((first, last)) => { mark_bits(&mut self.words, first, last); Ok(()) }
            Err(e) => { self.invalid = true; Err(e) }
        }
    }

    /// Consume the marker. No way to reset a fault into an empty valid mask.
    /// Coverage assertions are supplied independently, not inferred here.
    pub fn finish(self, coverage: Coverage) -> Option<Report> {
        if self.invalid || !coverage.complete() { return None; }
        Some(Report { ticket: self.ticket, fence: self.fence, coverage, words: self.words })
    }

    /// Observation only. Requires a verified same-domain completed fence,
    /// same flight, full independently completed authoritative scan of
    /// this exact backing region, and complete coverage assertions.
    pub fn observe<T>(
        &self, flight: &Flight<T>, domain: &FenceDomain, completed: u64,
        backing: &Backing, coverage: Coverage, actual: Option<&[Span]>,
    ) -> Option<Observation> {
        if self.invalid || !coverage.complete() || !self.ticket.matches(&flight.ticket)
            || self.fence != flight.fence || !flight.domain.matches(domain)
            || completed < self.fence || completed == u64::MAX
            || !Arc::ptr_eq(&self.backing.0, &backing.0)
        { return None; }
        let mut changed = vec![0u64; self.words.len()];
        for span in actual? {
            let (a, b) = page_bounds(self.region, span.start, span.end.checked_sub(span.start)?).ok()?;
            mark_bits(&mut changed, a, b);
        }
        let mut out = Observation { candidate_pages: 0, changed_pages: 0, missed_pages: 0, extra_pages: 0 };
        for (&candidate, &actual) in self.words.iter().zip(&changed) {
            out.candidate_pages += candidate.count_ones() as u64;
            out.changed_pages += actual.count_ones() as u64;
            out.missed_pages += (actual & !candidate).count_ones() as u64;
            out.extra_pages += (candidate & !actual).count_ones() as u64;
        }
        Some(out)
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
    fn marker_crosses_page_and_word_boundaries() {
        let mut f = flight(17, PAGE * 130 - 34);
        let backing = Backing::new();
        let mut m = Marker::new(&f, backing.clone()).unwrap();
        m.mark(&backing, PAGE * 64 - 1, 2).unwrap();
        m.mark(&backing, PAGE * 64, PAGE + 1).unwrap();
        m.mark(&backing, PAGE * 64, 1).unwrap();
        m.mark(&backing, 17, 1).unwrap();
        m.mark(&backing, PAGE * 130 - 18, 1).unwrap();
        let r = m.finish(coverage()).unwrap();
        assert_eq!(r.words, vec![1 | (1 << 63), 3, 2]);
        assert_eq!(plan(&mut f, 7, Some(&r)), Ok(&Plan::Sparse(vec![
            Span::new(17, PAGE - 17).unwrap(),
            Span::new(PAGE * 63, PAGE * 3).unwrap(),
            Span::new(PAGE * 129, PAGE - 17).unwrap(),
        ])));
    }

    #[test]
    fn marker_unknown_or_invalid_span_is_sticky() {
        let f = flight(17, PAGE * 2);
        let backing = Backing::new();
        for (start, len, error) in [
            (16, 1, MarkError::OutsideRegion),
            (PAGE * 2 + 16, 2, MarkError::OutsideRegion),
            (17, 0, MarkError::InvalidSpan),
            (u64::MAX, 1, MarkError::InvalidSpan),
        ] {
            let mut m = Marker::new(&f, backing.clone()).unwrap();
            m.mark(&backing, 17, 1).unwrap();
            assert_eq!(m.mark(&backing, start, len), Err(error));
            assert_eq!(m.mark(&backing, 17, 1), Err(MarkError::Invalidated));
            assert!(m.finish(coverage()).is_none());
        }
        let mut m = Marker::new(&f, backing.clone()).unwrap();
        assert_eq!(m.unknown(), MarkError::UnknownFootprint);
        assert!(m.finish(coverage()).is_none());
    }

    #[test]
    fn marker_wrong_identity_and_unproven_coverage_fail_closed() {
        let mut f = flight(0, PAGE);
        let backing = Backing::new();
        let mut m = Marker::new(&f, backing.clone()).unwrap();
        assert_eq!(m.mark(&Backing::new(), 0, 1), Err(MarkError::WrongBacking));
        let r = m.finish(coverage());
        assert_eq!(plan(&mut f, 7, r.as_ref()), Ok(&Plan::Authoritative));
        let f = flight(0, PAGE);
        let m = Marker::new(&f, backing.clone()).unwrap();
        let mut c = coverage();
        c.alias_footprint = false;
        assert!(m.finish(c).is_none());
        assert!(matches!(Marker::new(&flight(0, (MAX_PAGES+1)*PAGE), backing), Err(MarkError::Capacity)));
    }

    #[test]
    fn marker_near_maximum_address_without_overflow() {
        let mut f = flight(u64::MAX - PAGE, PAGE);
        let backing = Backing::new();
        let mut m = Marker::new(&f, backing.clone()).unwrap();
        m.mark(&backing, u64::MAX - PAGE, PAGE).unwrap();
        let r = m.finish(coverage()).unwrap();
        assert_eq!(plan(&mut f, 7, Some(&r)), Ok(&Plan::Sparse(vec![Span::new(u64::MAX-PAGE, PAGE).unwrap()])));
    }

    #[test]
    fn observation_distinguishes_misses_and_false_positives() {
        let f = flight(0, PAGE * 5);
        let backing = Backing::new();
        let mut m = Marker::new(&f, backing.clone()).unwrap();
        m.mark(&backing, 0, PAGE * 2).unwrap();
        m.mark(&backing, PAGE * 4, 1).unwrap();
        let actual = [Span::new(PAGE - 1, 2).unwrap(), Span::new(PAGE * 2, 1).unwrap()];
        assert_eq!(m.observe(&f, &f.domain, 7, &backing, coverage(), Some(&actual)),
            Some(Observation { candidate_pages: 3, changed_pages: 3, missed_pages: 1, extra_pages: 1 }));
        assert_eq!(m.observe(&f, &f.domain, 7, &backing, coverage(), Some(&[])),
            Some(Observation { candidate_pages: 3, changed_pages: 0, missed_pages: 0, extra_pages: 3 }));
    }

    #[test]
    fn observation_rejects_missing_evidence_and_unrelated_completion() {
        let f = flight(0, PAGE);
        let other = flight(0, PAGE);
        let backing = Backing::new();
        let mut m = Marker::new(&f, backing.clone()).unwrap();
        for value in [6, u64::MAX] {
            assert!(m.observe(&f, &f.domain, value, &backing, coverage(), Some(&[])).is_none());
        }
        assert!(m.observe(&f, &f.domain, 7, &backing, coverage(), None).is_none());
        assert!(m.observe(&f, &other.domain, 7, &backing, coverage(), Some(&[])).is_none());
        assert!(m.observe(&other, &other.domain, 7, &backing, coverage(), Some(&[])).is_none());
        assert!(m.observe(&f, &f.domain, 7, &Backing::new(), coverage(), Some(&[])).is_none());
        assert!(m.observe(&f, &f.domain, 7, &backing, coverage(), Some(&[Span::new(PAGE, 1).unwrap()])).is_none());
        m.unknown();
        assert!(m.observe(&f, &f.domain, 7, &backing, coverage(), Some(&[])).is_none());
    }

    #[test]
    fn marker_random_byte_oracle_matches_all_pages() {
        let mut seed = 0x8123_4465_9876_u64;
        let mut next = || { seed ^= seed << 13; seed ^= seed >> 7; seed ^= seed << 17; seed };
        for pages in [1, 2, 63, 64, 65, 129, 4096] {
            let f = flight(17, pages * PAGE - 34);
            let backing = Backing::new();
            let mut m = Marker::new(&f, backing.clone()).unwrap();
            let mut expected = vec![false; pages as usize];
            for _ in 0..100 {
                let start = 17 + next() % (f.region.end - 17);
                let len = (1 + next() % (PAGE * 5)).min(f.region.end - start);
                m.mark(&backing, start, len).unwrap();
                // Independent per-page intersection oracle, not mark_bits.
                for (i, bit) in expected.iter_mut().enumerate() {
                    let lo = i as u64 * PAGE;
                    *bit |= lo < start + len && start < lo + PAGE;
                }
            }
            let r = m.finish(coverage()).unwrap();
            for (i, want) in expected.into_iter().enumerate() {
                assert_eq!((r.words[i/64] >> (i%64)) & 1 != 0, want);
            }
        }
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
