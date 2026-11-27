// SPDX-License-Identifier: GPL-3.0-or-later
//! Standalone prototype. Not connected to title memory or the runtime.
use std::sync::{Condvar, Mutex};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Span { start: usize, end: usize }
impl Span {
    pub fn new(start: usize, len: usize) -> Option<Self> {
        let end = start.checked_add(len)?;
        (end > start).then_some(Self { start, end })
    }
    fn overlaps(self, other: Self) -> bool {
        self.start < other.end && other.start < self.end
    }
    // Include whole host views intersecting the requested range. The
    // mapper can unmap/rebuild their neighbors even for a one-page change.
    // Assumes the supplied view table is stable and non-overlapping.
    pub fn expand(self, views: &[Span]) -> Self {
        views.iter().filter(|v| self.overlaps(**v)).fold(self, |s, v| Self {
            start: s.start.min(v.start), end: s.end.max(v.end),
        })
    }
}

#[derive(Clone, Copy)]
struct Entry { id: u64, span: Span, write: bool }
#[derive(Default)]
struct State { next: u64, active: Vec<Entry>, pending: Vec<Entry> }
#[derive(Default)]
pub struct Gate { state: Mutex<State>, changed: Condvar }
pub struct Guard<'a> { gate: &'a Gate, id: u64 }

impl Gate {
    fn entry(state: &mut State, span: Span, write: bool) -> Entry {
        let id = state.next;
        state.next = state.next.checked_add(1).expect("range gate id exhausted");
        Entry { id, span, write }
    }
    pub fn try_read(&self, span: Span) -> Option<Guard<'_>> {
        let mut state = self.state.lock().unwrap();
        if state.active.iter().any(|e| e.write && e.span.overlaps(span))
            || state.pending.iter().any(|e| e.span.overlaps(span))
        { return None; }
        let e = Self::entry(&mut state, span, false);
        state.active.push(e);
        Some(Guard { gate: self, id: e.id })
    }
    pub fn write(&self, span: Span) -> Guard<'_> {
        let mut state = self.state.lock().unwrap();
        let e = Self::entry(&mut state, span, true);
        state.pending.push(e);
        loop {
            let busy = state.active.iter().any(|a| a.span.overlaps(span));
            let earlier = state.pending.iter().take_while(|p| p.id != e.id)
                .any(|p| p.span.overlaps(span));
            if !busy && !earlier {
                state.pending.retain(|p| p.id != e.id);
                state.active.push(e);
                return Guard { gate: self, id: e.id };
            }
            state = self.changed.wait(state).unwrap();
        }
    }
}
impl Drop for Guard<'_> {
    fn drop(&mut self) {
        let mut state = self.gate.state.lock().unwrap();
        state.active.retain(|e| e.id != self.id);
        self.gate.changed.notify_all();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::mpsc;
    use std::time::Duration;
    fn s(start: usize, len: usize) -> Span { Span::new(start, len).unwrap() }

    #[test]
    fn bounds_and_full_view_expansion() {
        assert!(Span::new(0, 0).is_none());
        assert!(Span::new(usize::MAX, 2).is_none());
        assert_eq!(s(64, 64).expand(&[s(0, 192), s(192, 64)]), s(0, 192));
        assert_eq!(s(64, 128).expand(&[s(0, 128), s(128, 128)]), s(0, 256));
    }
    #[test]
    fn disjoint_readers_continue() {
        let gate = Gate::default();
        let writer = gate.write(s(0, 128));
        assert!(gate.try_read(s(64, 64)).is_none());
        assert!(gate.try_read(s(128, 64)).is_some());
        drop(writer);
        assert!(gate.try_read(s(64, 64)).is_some());
    }
    #[test]
    fn readers_share_and_disjoint_writer_runs() {
        let gate = Gate::default();
        let r1 = gate.try_read(s(0, 64)).unwrap();
        let r2 = gate.try_read(s(32, 64)).unwrap();
        let w = gate.write(s(96, 64));
        assert!(gate.try_read(s(80, 32)).is_none());
        drop((r1, r2, w));
        assert!(gate.try_read(s(80, 32)).is_some());
    }
    #[test]
    fn queued_writer_blocks_new_overlapping_readers() {
        let gate = Gate::default();
        let reader = gate.try_read(s(0, 64)).unwrap();
        std::thread::scope(|scope| {
            let (tx, rx) = mpsc::channel();
            let g = &gate;
            scope.spawn(move || {
                let _w = g.write(s(0, 64));
                tx.send(()).unwrap();
            });
            // Wait for the writer to enqueue, without sleeping on timing.
            // If the writer is still pending after two seconds, fail
            // without leaving the scoped thread blocked by our read guard.
            let deadline = std::time::Instant::now() + Duration::from_secs(2);
            let mut queued = false;
            while std::time::Instant::now() < deadline {
                if !gate.state.lock().unwrap().pending.is_empty() {
                    queued = true;
                    break;
                }
                std::thread::yield_now();
            }
            let blocked = gate.try_read(s(0, 64)).is_none();
            let disjoint = gate.try_read(s(64, 64)).is_some();
            drop(reader);
            assert!(queued && blocked && disjoint);
            rx.recv_timeout(Duration::from_secs(2)).unwrap();
        });
    }
}
