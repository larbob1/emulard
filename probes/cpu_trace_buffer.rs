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
