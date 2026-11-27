// SPDX-License-Identifier: GPL-3.0-or-later
//! Portable CPU trace state prototype. Not linked into the runtime.
//! All times are injected monotonic nanoseconds; no OS thread IDs are exported.

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Kind { Execute, PaceSleep, PresentCall }

impl Kind {
    fn name(self) -> &'static str {
        match self {
            Self::Execute => "execute",
            Self::PaceSleep => "pace_sleep",
            Self::PresentCall => "present_call",
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct Span { start_ns: u64, end_ns: u64, kind: Kind }

#[derive(Debug)]
struct Capture {
    sequence: u64,
    start_ns: u64,
    end_ns: u64,
    spans: Vec<Span>,
    dropped: u64,
    invalid: u64,
    thread_changed: bool,
    present_ok: bool,
    cpu_window_complete: bool,
}

impl Capture {
    // Fixed allowlisted labels and numeric fields only. Deliberately not
    // the GPU dependency schema; no fabricated terminal dependency.
    fn json(&self) -> String {
        let spans = self.spans.iter().map(|s| format!(
            r#"{{"kind":"{}","start_ns":{},"end_ns":{}}}"#,
            s.kind.name(), s.start_ns, s.end_ns
        )).collect::<Vec<_>>().join(",");
        format!(
            concat!(r#"{{"schema":"cpu_trace_v1","boundary":"present_call_return","#,
                    r#""sequence":{},"start_ns":{},"end_ns":{},"dropped":{},"invalid":{},"#,
                    r#""thread_changed":{},"present_ok":{},"cpu_window_complete":{},"spans":[{}]}}"#),
            self.sequence, self.start_ns, self.end_ns, self.dropped, self.invalid,
            self.thread_changed, self.present_ok, self.cpu_window_complete, spans
        )
    }
}

struct Buffer {
    capacity: usize,
    owner: Option<u64>,
    boundary: u64,
    sequence: u64,
    spans: Vec<Span>,
    dropped: u64,
    invalid: u64,
}

impl Buffer {
    fn new(capacity: usize) -> Self {
        Self { capacity: capacity.min(256), owner: None, boundary: 0, sequence: 0,
               spans: Vec::new(), dropped: 0, invalid: 0 }
    }

    // The owner is a local, opaque thread-generation token, never serialized.
    // Non-owner events are outside this first prototype's scope.
    fn record(&mut self, owner: u64, span: Span) {
        if self.owner != Some(owner) { return; }
        if span.start_ns < self.boundary || span.start_ns >= span.end_ns {
            self.invalid = self.invalid.saturating_add(1);
        } else if self.spans.len() >= self.capacity {
            self.dropped = self.dropped.saturating_add(1);
        } else {
            self.spans.push(span);
        }
    }

    // The caller records the outer present call, then passes its exact end
    // timestamp here BEFORE the existing framelog/diagnostic pacing.
    // The first boundary arms capture; it cannot emit a complete window.
    fn finish(&mut self, owner: u64, end_ns: u64, present_ok: bool) -> Option<Capture> {
        let previous_owner = self.owner.replace(owner);
        let start_ns = std::mem::replace(&mut self.boundary, end_ns);
        let mut spans = std::mem::take(&mut self.spans);
        let dropped = std::mem::take(&mut self.dropped);
        let mut invalid = std::mem::take(&mut self.invalid);
        let previous_owner = previous_owner?;
        let Some(sequence) = self.sequence.checked_add(1) else {
            // Exhaustion is terminal; do not reuse sequence numbers.
            self.owner = None;
            self.sequence = u64::MAX;
            return None;
        };
        self.sequence = sequence;
        let thread_changed = previous_owner != owner;
        spans.sort_unstable_by_key(|s| (s.start_ns, s.end_ns));
        let mut prior_end = start_ns;
        let mut presents = 0;
        for span in &spans {
            if span.start_ns < prior_end || span.end_ns > end_ns {
                invalid = invalid.saturating_add(1);
            }
            prior_end = prior_end.max(span.end_ns);
            if span.kind == Kind::PresentCall {
                presents += 1;
                if span.end_ns != end_ns { invalid = invalid.saturating_add(1); }
            }
        }
        let complete = !thread_changed && present_ok && end_ns > start_ns
            && presents == 1 && dropped == 0 && invalid == 0;
        Some(Capture { sequence, start_ns, end_ns, spans, dropped, invalid,
                       thread_changed, present_ok, cpu_window_complete: complete })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn span(a: u64, b: u64, kind: Kind) -> Span {
        Span { start_ns: a, end_ns: b, kind }
    }
    fn armed(cap: usize) -> Buffer {
        let mut b = Buffer::new(cap);
        assert!(b.finish(90001, 100, true).is_none());
        b
    }

    #[test]
    fn complete_outer_calls_and_numeric_schema() {
        let mut b = armed(3);
        b.record(90001, span(110, 120, Kind::Execute));
        b.record(90001, span(130, 140, Kind::PaceSleep));
        b.record(90001, span(150, 200, Kind::PresentCall));
        let c = b.finish(90001, 200, true).unwrap();
        assert!(c.cpu_window_complete);
        assert_eq!(c.sequence, 1);
        assert_eq!(c.spans.len(), 3);
        let json = c.json();
        assert!(json.contains(r#""schema":"cpu_trace_v1""#));
        assert!(json.contains(r#""boundary":"present_call_return""#));
        assert!(!json.contains("90001"));
        assert!(!json.contains("depends_on"));
    }

    #[test]
    fn cap_and_loss_are_visible() {
        let mut b = armed(2);
        b.record(90001, span(110, 120, Kind::Execute));
        b.record(90001, span(130, 140, Kind::PaceSleep));
        b.record(90001, span(150, 200, Kind::PresentCall));
        let c = b.finish(90001, 200, true).unwrap();
        assert_eq!(c.dropped, 1);
        assert_eq!(c.spans.len(), 2);
        assert!(!c.cpu_window_complete);
        assert_eq!(Buffer::new(usize::MAX).capacity, 256);
    }

    #[test]
    fn overlapping_or_outside_windows_are_incomplete() {
        let mut b = armed(8);
        b.record(90001, span(90, 120, Kind::Execute));
        b.record(90001, span(130, 170, Kind::Execute));
        b.record(90001, span(160, 200, Kind::PresentCall));
        let c = b.finish(90001, 200, true).unwrap();
        assert_eq!(c.invalid, 2);
        assert!(!c.cpu_window_complete);
        b.record(90001, span(205, 310, Kind::Execute));
        b.record(90001, span(280, 300, Kind::PresentCall));
        assert!(!b.finish(90001, 300, true).unwrap().cpu_window_complete);
    }

    #[test]
    fn nonowner_excluded_and_switch_invalidates() {
        let mut b = armed(4);
        b.record(77777, span(100, 120, Kind::Execute));
        b.record(77777, span(150, 200, Kind::PresentCall));
        let c = b.finish(77777, 200, true).unwrap();
        assert!(c.thread_changed);
        assert!(c.spans.is_empty());
        assert!(!c.cpu_window_complete);
        b.record(77777, span(250, 300, Kind::PresentCall));
        let c = b.finish(77777, 300, true).unwrap();
        assert!(c.cpu_window_complete);
        assert_eq!(c.sequence, 2);
        assert_eq!(c.start_ns, 200);
    }

    #[test]
    fn failed_and_missing_present() {
        let mut b = armed(4);
        b.record(90001, span(150, 200, Kind::PresentCall));
        assert!(!b.finish(90001, 200, false).unwrap().cpu_window_complete);
        assert!(!b.finish(90001, 300, true).unwrap().cpu_window_complete);
        b.record(90001, span(350, 399, Kind::PresentCall));
        assert!(!b.finish(90001, 400, true).unwrap().cpu_window_complete);
    }

    #[test]
    fn zero_duration_and_reversed_boundary() {
        let mut b = armed(4);
        b.record(90001, span(110, 110, Kind::Execute));
        assert!(!b.finish(90001, 90, true).unwrap().cpu_window_complete);
    }

    #[test]
    fn exhaustion_does_not_reuse_sequence() {
        let mut b = armed(4);
        b.sequence = u64::MAX;
        assert!(b.finish(90001, 200, true).is_none());
        assert!(b.finish(90001, 300, true).is_none());
        assert!(b.finish(90001, 400, true).is_none());
    }
}

// Process-wide capture model: one controller per runtime, bounded pending
// records; only scalar identity/epoch in TLS. No production hooks or I/O.
use std::cell::Cell;
use std::collections::VecDeque;
use std::marker::PhantomData;
use std::rc::Rc;
use std::sync::{Mutex, MutexGuard};
use std::sync::atomic::{AtomicU64, AtomicU8, Ordering};

const RUNNING: u8 = 0;
const CAP_REACHED: u8 = 1;
const QUEUE_FULL: u8 = 2;
const CONCURRENT_PRESENT: u8 = 3;
const STALE_TICKET: u8 = 4;
const CONTENDED: u8 = 5;
const EXHAUSTED: u8 = 6;
const WRITER_FAILED: u8 = 7;
const CLOSED: u64 = 1 << 63;

struct Admission<'a>(&'a AtomicU64);
impl Drop for Admission<'_> {
    fn drop(&mut self) { self.0.fetch_sub(1, Ordering::AcqRel); }
}

static NEXT_ID: AtomicU64 = AtomicU64::new(1);

fn fresh_id() -> Option<u64> {
    NEXT_ID.fetch_update(Ordering::Relaxed, Ordering::Relaxed,
                         |n| n.checked_add(1)).ok()
}

#[derive(Clone, Copy)]
struct Local { session: u64, thread: u64, epoch: u64 }
thread_local! {
    static LOCAL: Cell<Local> = const {
        Cell::new(Local { session: 0, thread: 0, epoch: 0 })
    };
}

struct Ticket {
    session: u64,
    thread: u64,
    epoch: u64,
    start_ns: u64,
    kind: Kind,
    // Cannot transfer an outstanding caller-thread observation to another
    // thread. A ticket deliberately cannot be cloned either.
    _local: PhantomData<Rc<()>>,
}

struct SharedCapture {
    buffer: Buffer,
    epoch: u64,
    present: Option<(u64, u64)>,
    pending: VecDeque<Capture>,
    attempted: u64,
    drained: u64,
    written: u64,
    writer_inflight: Option<u64>,
    outstanding: u64,
    invalid_windows: u64,
    dropped_windows: u64,
}

struct Controller {
    enabled: bool,
    session: u64,
    cap: u64,
    queue_cap: usize,
    stop: AtomicU8,
    admission: AtomicU64,
    pending_hint: AtomicU64,
    state: Mutex<SharedCapture>,
}

#[derive(Debug)]
struct Terminal {
    code: u8,
    expected: u64,
    attempted: u64,
    drained: u64,
    written: u64,
    invalid_windows: u64,
    dropped_windows: u64,
    complete: bool,
}

impl Terminal {
    fn json(&self) -> String {
        format!(concat!(r#"{{"schema":"cpu_trace_end_v1","code":{},"expected":{},"attempted":{},"#,
                        r#""drained":{},"written":{},"invalid_windows":{},"dropped_windows":{},"complete":{}}}"#),
                self.code, self.expected, self.attempted, self.drained, self.written,
                self.invalid_windows, self.dropped_windows, self.complete)
    }
}

impl Controller {
    fn new(enabled: bool, cap: u64, queue_cap: usize, span_cap: usize) -> Self {
        let session = if enabled { fresh_id().unwrap_or(0) } else { 0 };
        Self {
            enabled: enabled && session != 0,
            session,
            cap: cap.clamp(1, 600),
            queue_cap: queue_cap.clamp(1, 8),
            stop: AtomicU8::new(if enabled && session == 0 { EXHAUSTED } else { RUNNING }),
            admission: AtomicU64::new(if enabled && session == 0 { CLOSED } else { 0 }),
            pending_hint: AtomicU64::new(0),
            state: Mutex::new(SharedCapture {
                buffer: Buffer::new(span_cap), epoch: 1, present: None,
                pending: VecDeque::new(), attempted: 0, drained: 0,
                written: 0, writer_inflight: None, outstanding: 0,
                invalid_windows: 0, dropped_windows: 0,
            }),
        }
    }

    fn observing(&self) -> bool {
        self.enabled && self.stop.load(Ordering::Acquire) == RUNNING
    }

    fn fail(&self, code: u8) {
        // A late, racing loss report must not be hidden by a cap-reached
        // status. Fault status is sticky; exact loss count may be unknown.
        self.stop.fetch_max(code, Ordering::AcqRel);
        self.admission.fetch_or(CLOSED, Ordering::AcqRel);
    }

    fn admit(&self) -> Option<Admission<'_>> {
        if !self.observing() { return None; }
        self.admission.fetch_update(Ordering::AcqRel, Ordering::Acquire, |n| {
            if n >= CLOSED - 1 { None } else { Some(n + 1) }
        }).ok()?;
        Some(Admission(&self.admission))
    }

    fn producer_state(&self) -> Option<MutexGuard<'_, SharedCapture>> {
        if !self.observing() { return None; }
        let guard = match self.state.try_lock() {
            Ok(g) => g,
            Err(_) => { self.fail(CONTENDED); return None; }
        };
        if self.observing() { Some(guard) } else { None }
    }

    fn begin(&self, kind: Kind, start_ns: u64) -> Option<Ticket> {
        // Disabled/stopped calls do not touch TLS or lock capture state.
        let _admitted = self.admit()?;
        let mut state = self.producer_state()?;
        let local = LOCAL.with(|cell| {
            let mut l = cell.get();
            if l.session != self.session {
                l = Local { session: self.session, thread: fresh_id()?, epoch: 0 };
            }
            l.epoch = state.epoch;
            cell.set(l);
            Some(l)
        });
        let Some(local) = local else { self.fail(EXHAUSTED); return None; };
        if kind == Kind::PresentCall {
            if state.present.is_some() {
                self.fail(CONCURRENT_PRESENT);
                return None;
            }
            state.present = Some((local.thread, local.epoch));
        } else if state.buffer.owner != Some(local.thread) {
            return None; // Not the presenting thread; no span retained.
        }
        if kind != Kind::PresentCall {
            if state.outstanding >= 256 { self.fail(EXHAUSTED); return None; }
            state.outstanding += 1;
        }
        Some(Ticket { session: self.session, thread: local.thread,
                      epoch: local.epoch, start_ns, kind, _local: PhantomData })
    }

    fn finish(&self, ticket: Ticket, end_ns: u64, present_ok: bool) {
        let Some(_admitted) = self.admit() else { return; };
        let Some(mut state) = self.producer_state() else { return; };
        let local_ok = LOCAL.with(|cell| {
            let l = cell.get();
            l.session == ticket.session && l.thread == ticket.thread
                && l.epoch == ticket.epoch
        });
        if !local_ok || ticket.session != self.session || ticket.epoch != state.epoch {
            self.fail(STALE_TICKET);
            return;
        }
        let is_present = ticket.kind == Kind::PresentCall;
        if is_present {
            if state.present != Some((ticket.thread, ticket.epoch)) {
                self.fail(STALE_TICKET);
                return;
            }
            state.present = None;
            if state.buffer.owner.is_none() && (!present_ok || end_ns <= ticket.start_ns) {
                self.fail(STALE_TICKET);
                return;
            }
        }
        state.buffer.record(ticket.thread, Span {
            kind: ticket.kind, start_ns: ticket.start_ns, end_ns,
        });
        if !is_present {
            if state.outstanding == 0 { self.fail(STALE_TICKET); return; }
            state.outstanding -= 1;
            return;
        }
        if state.outstanding != 0 { self.fail(STALE_TICKET); return; }
        let row = state.buffer.finish(ticket.thread, end_ns, present_ok);
        let Some(next_epoch) = state.epoch.checked_add(1) else {
            self.fail(EXHAUSTED);
            return;
        };
        state.epoch = next_epoch;
        if let Some(row) = row {
            state.attempted += 1; // bounded by capture cap
            if !row.cpu_window_complete { state.invalid_windows += 1; }
            if state.pending.len() >= self.queue_cap {
                state.dropped_windows += 1;
                self.fail(QUEUE_FULL);
                return;
            }
            state.pending.push_back(row);
            self.pending_hint.store(state.pending.len() as u64, Ordering::Release);
            if state.attempted >= self.cap {
                self.fail(CAP_REACHED);
            }
        }
    }

    // Single writer lease; no further pop before write/flush acknowledgement.
    fn pop(&self) -> Option<Capture> {
        // Empty polling must not contend with active producers. This is
        // only a hint; all queue decisions still occur under the mutex.
        if self.pending_hint.load(Ordering::Acquire) == 0 { return None; }
        let mut state = self.state.try_lock().ok()?;
        if state.writer_inflight.is_some() || self.stop.load(Ordering::Acquire) == WRITER_FAILED {
            return None;
        }
        let row = state.pending.pop_front()?;
        self.pending_hint.store(state.pending.len() as u64, Ordering::Release);
        state.drained += 1;
        state.writer_inflight = Some(row.sequence);
        Some(row)
    }

    fn acknowledge(&self, sequence: u64, success: bool) {
        // Writer thread only: never called by a runtime producer.
        let mut state = self.state.lock().unwrap_or_else(|e| e.into_inner());
        if state.writer_inflight != Some(sequence) || !success {
            self.fail(WRITER_FAILED);
            return;
        }
        state.writer_inflight = None;
        state.written += 1;
    }

    fn write_next(&self, output: &mut impl std::io::Write) -> std::io::Result<bool> {
        let Some(row) = self.pop() else { return Ok(false); };
        let result = writeln!(output, "{}", row.json()).and_then(|_| output.flush());
        self.acknowledge(row.sequence, result.is_ok());
        result.map(|_| true)
    }

    fn terminal(&self) -> Option<Terminal> {
        // No need to inspect terminal state before producer quiescence.
        if self.admission.load(Ordering::Acquire) != CLOSED { return None; }
        let state = self.state.try_lock().ok()?;
        // Closed admission plus zero active operations ensures a producer
        // that observed RUNNING earlier cannot publish a later fault.
        if self.admission.load(Ordering::Acquire) != CLOSED { return None; }
        let code = self.stop.load(Ordering::Acquire);
        if code == RUNNING || !state.pending.is_empty() || state.writer_inflight.is_some() {
            return None;
        }
        Some(Terminal {
            code, expected: self.cap, attempted: state.attempted, drained: state.drained,
            written: state.written,
            invalid_windows: state.invalid_windows, dropped_windows: state.dropped_windows,
            complete: code == CAP_REACHED && state.attempted == self.cap
                && state.written == self.cap && state.drained == self.cap
                && state.outstanding == 0 && state.present.is_none()
                && state.invalid_windows == 0 && state.dropped_windows == 0,
        })
    }
}

#[cfg(test)]
mod controller_tests {
    use super::*;
    use std::sync::Barrier;

    fn drain(c: &Controller) -> Option<Capture> {
        let row = c.pop()?;
        c.acknowledge(row.sequence, true);
        Some(row)
    }

    fn present(c: &Controller, start: u64, end: u64) {
        let t = c.begin(Kind::PresentCall, start).unwrap();
        c.finish(t, end, true);
    }

    #[test]
    fn disabled_never_touches_locked_state_or_tls() {
        let c = Controller::new(false, 2, 2, 8);
        let before = LOCAL.with(|l| l.get().session);
        let _hold = c.state.lock().unwrap();
        assert!(c.begin(Kind::PresentCall, 1).is_none());
        assert_eq!(c.stop.load(Ordering::Relaxed), RUNNING);
        assert_eq!(LOCAL.with(|l| l.get().session), before);
    }

    #[test]
    fn bounded_capture_and_drain() {
        let c = Controller::new(true, 2, 2, 8);
        present(&c, 1, 10);
        let t = c.begin(Kind::Execute, 11).unwrap();
        c.finish(t, 12, true);
        present(&c, 19, 20);
        present(&c, 29, 30);
        assert!(c.begin(Kind::PresentCall, 31).is_none());
        assert!(c.terminal().is_none());
        let first = drain(&c).unwrap();
        assert!(first.cpu_window_complete);
        assert_eq!(first.spans.len(), 2);
        assert_eq!(drain(&c).unwrap().sequence, 2);
        let end = c.terminal().unwrap();
        assert!(end.complete);
        assert_eq!(end.code, CAP_REACHED);
        assert_eq!(end.attempted, 2);
        assert_eq!(end.drained, 2);
    }

    #[test]
    fn queue_full_stops_instead_of_overwriting() {
        let c = Controller::new(true, 600, 1, 8);
        present(&c, 1, 10);
        present(&c, 11, 20);
        present(&c, 21, 30);
        assert_eq!(drain(&c).unwrap().sequence, 1);
        assert!(drain(&c).is_none());
        let end = c.terminal().unwrap();
        assert_eq!(end.code, QUEUE_FULL);
        assert_eq!(end.dropped_windows, 1);
        assert_eq!(end.attempted, 2);
        assert!(!end.complete);
    }

    #[test]
    fn stale_epoch_fails_closed() {
        let c = Controller::new(true, 4, 4, 8);
        present(&c, 1, 10);
        let old = c.begin(Kind::Execute, 11).unwrap();
        present(&c, 19, 20);
        c.finish(old, 21, true);
        assert!(drain(&c).is_none());
        assert_eq!(c.terminal().unwrap().code, STALE_TICKET);
        assert!(!c.terminal().unwrap().complete);
    }

    #[test]
    fn concurrent_present_rejected_on_distinct_threads() {
        let c = Controller::new(true, 4, 4, 8);
        present(&c, 1, 10);
        let held = Barrier::new(2);
        let checked = Barrier::new(2);
        std::thread::scope(|s| {
            s.spawn(|| {
                let t = c.begin(Kind::PresentCall, 11).unwrap();
                held.wait();
                checked.wait();
                c.finish(t, 20, true);
            });
            held.wait();
            assert!(c.begin(Kind::PresentCall, 12).is_none());
            checked.wait();
        });
        assert!(drain(&c).is_none());
        assert_eq!(c.terminal().unwrap().code, CONCURRENT_PRESENT);
    }

    #[test]
    fn thread_change_does_not_reuse_old_window() {
        let c = Controller::new(true, 2, 2, 8);
        present(&c, 1, 10);
        std::thread::scope(|s| {
            s.spawn(|| {
                assert!(c.begin(Kind::Execute, 11).is_none());
                present(&c, 19, 20);
                present(&c, 29, 30);
            }).join().unwrap();
        });
        let first = drain(&c).unwrap();
        assert!(first.thread_changed);
        assert!(!first.cpu_window_complete);
        assert!(drain(&c).unwrap().cpu_window_complete);
        let end = c.terminal().unwrap();
        assert_eq!(end.invalid_windows, 1);
        assert!(!end.complete);
    }

    #[test]
    fn contention_does_not_wait_and_marks_loss() {
        let c = Controller::new(true, 3, 3, 8);
        let held = c.state.lock().unwrap();
        std::thread::scope(|s| {
            s.spawn(|| assert!(c.begin(Kind::PresentCall, 1).is_none()))
                .join().unwrap();
        });
        drop(held);
        assert_eq!(c.terminal().unwrap().code, CONTENDED);
        assert!(!c.terminal().unwrap().complete);
    }

    #[test]
    fn wrong_session_ticket_rejected() {
        let a = Controller::new(true, 2, 2, 8);
        let b = Controller::new(true, 2, 2, 8);
        let t = a.begin(Kind::PresentCall, 1).unwrap();
        b.finish(t, 10, true);
        assert_eq!(b.terminal().unwrap().code, STALE_TICKET);
    }

    #[test]
    fn process_wide_bounds_clamped() {
        let c = Controller::new(true, u64::MAX, usize::MAX, usize::MAX);
        assert_eq!(c.cap, 600);
        assert_eq!(c.queue_cap, 8);
        assert_eq!(c.state.lock().unwrap().buffer.capacity, 256);
    }

    #[test]
    fn terminal_waits_for_admitted_producer() {
        let c = Controller::new(true, 1, 1, 8);
        present(&c, 1, 10);
        let active = c.admit().unwrap();
        present(&c, 19, 20);
        drain(&c).unwrap();
        assert!(c.terminal().is_none());
        c.fail(CONTENDED);
        drop(active);
        assert_eq!(c.terminal().unwrap().code, CONTENDED);
        assert!(!c.terminal().unwrap().complete);
    }

    #[test]
    fn terminal_waits_for_writer_ack_and_refuses_second_lease() {
        let c = Controller::new(true, 2, 2, 8);
        present(&c, 1, 10);
        present(&c, 19, 20);
        present(&c, 29, 30);
        let a = c.pop().unwrap();
        assert!(c.pop().is_none());
        assert!(c.terminal().is_none());
        c.acknowledge(a.sequence, true);
        let b = c.pop().unwrap();
        assert!(c.terminal().is_none());
        c.acknowledge(b.sequence, true);
        let end = c.terminal().unwrap();
        assert!(end.complete);
        assert_eq!(end.written, 2);
        assert!(end.json().contains(r#""schema":"cpu_trace_end_v1""#));
    }

    #[test]
    fn actual_writer_and_flush_failure() {
        struct Broken(bool);
        impl std::io::Write for Broken {
            fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
                if self.0 { Ok(bytes.len()) } else { Err(std::io::ErrorKind::Other.into()) }
            }
            fn flush(&mut self) -> std::io::Result<()> {
                Err(std::io::ErrorKind::Other.into())
            }
        }
        for fail_at_flush in [false, true] {
            let c = Controller::new(true, 1, 1, 8);
            present(&c, 1, 10);
            present(&c, 19, 20);
            assert!(c.write_next(&mut Broken(fail_at_flush)).is_err());
            assert!(c.terminal().is_none());
            assert_eq!(c.stop.load(Ordering::Acquire), WRITER_FAILED);
            assert!(c.pop().is_none());
        }
        let c = Controller::new(true, 1, 1, 8);
        present(&c, 1, 10);
        present(&c, 19, 20);
        let mut bytes = Vec::new();
        assert!(c.write_next(&mut bytes).unwrap());
        assert!(String::from_utf8(bytes).unwrap().contains("cpu_trace_v1"));
        assert!(c.terminal().unwrap().complete);
    }

    #[test]
    fn abandoned_ticket_refuses_clean_cap() {
        let c = Controller::new(true, 1, 1, 8);
        present(&c, 1, 10);
        drop(c.begin(Kind::Execute, 11).unwrap());
        present(&c, 19, 20);
        assert!(!c.terminal().unwrap().complete);
        assert_eq!(c.terminal().unwrap().code, STALE_TICKET);
    }

    #[test]
    fn full_600_window_capture() {
        let c = Controller::new(true, 600, 1, 8);
        present(&c, 1, 10);
        for i in 1..=600 {
            present(&c, i*10+1, i*10+10);
            assert_eq!(drain(&c).unwrap().sequence, i);
        }
        assert!(c.terminal().unwrap().complete);
        assert_eq!(c.terminal().unwrap().written, 600);
    }

    #[test]
    fn pending_hint_tracks_authoritative_queue() {
        let c = Controller::new(true, 3, 2, 8);
        assert_eq!(c.pending_hint.load(Ordering::Acquire), 0);
        present(&c, 1, 10);
        assert_eq!(c.pending_hint.load(Ordering::Acquire), 0);
        present(&c, 19, 20);
        present(&c, 29, 30);
        assert_eq!(c.pending_hint.load(Ordering::Acquire), 2);
        let row = c.pop().unwrap();
        assert_eq!(c.pending_hint.load(Ordering::Acquire), 1);
        assert!(c.pop().is_none());
        assert_eq!(c.pending_hint.load(Ordering::Acquire), 1);
        c.acknowledge(row.sequence, true);
        drain(&c).unwrap();
        assert_eq!(c.pending_hint.load(Ordering::Acquire), 0);
        present(&c, 39, 40);
        assert_eq!(c.pending_hint.load(Ordering::Acquire), 1);
        assert!(c.terminal().is_none());
        drain(&c).unwrap();
        assert_eq!(c.pending_hint.load(Ordering::Acquire), 0);
        assert!(c.terminal().unwrap().complete);
    }

    #[test]
    fn empty_writer_poll_with_locked_state_is_harmless() {
        let c = Controller::new(true, 2, 2, 8);
        present(&c, 1, 10);
        let guard = c.state.lock().unwrap();
        std::thread::scope(|s| {
            s.spawn(|| {
                for _ in 0..1000 {
                    assert!(c.pop().is_none());
                    assert!(c.terminal().is_none());
                }
            }).join().unwrap();
        });
        drop(guard);
        assert!(c.observing());
        present(&c, 19, 20);
        present(&c, 29, 30);
        drain(&c).unwrap();
        drain(&c).unwrap();
        assert!(c.terminal().unwrap().complete);
    }
}
