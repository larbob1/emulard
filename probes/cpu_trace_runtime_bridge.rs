// Review-only runtime bridge. Concatenate after cpu_trace_buffer.rs in a new
// victory-gpu cpu_trace.rs module only after coordinator approval.
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::{Arc, OnceLock};
use std::time::{Duration, Instant};

struct RuntimeCapture {
    controller: Arc<Controller>,
    origin: Instant,
}
static TRACE: OnceLock<Option<RuntimeCapture>> = OnceLock::new();

fn publish_capture(c: &Controller, destination: &Path, deadline: Instant) -> std::io::Result<()> {
    let mut name = destination.as_os_str().to_os_string();
    name.push(".partial");
    let partial = PathBuf::from(name);
    // No truncation of existing files, including existing partial traces.
    let mut file = std::fs::OpenOptions::new().write(true).create_new(true).open(&partial)?;
    loop {
        if Instant::now() >= deadline {
            c.fail(WRITER_FAILED);
            return Err(std::io::ErrorKind::TimedOut.into());
        }
        if c.write_next(&mut file)? { continue; }
        if let Some(end) = c.terminal() {
            if !end.complete {
                return Err(std::io::ErrorKind::InvalidData.into());
            }
            writeln!(file, "{}", end.json())?;
            file.flush()?;
            file.sync_all()?;
            drop(file);
            // Same-directory hard link publishes without replacing an existing
            // destination on either Windows or Unix. Unsupported FS fails closed.
            std::fs::hard_link(&partial, destination)?;
            let _ = std::fs::remove_file(&partial);
            return Ok(());
        }
        if c.stop.load(Ordering::Acquire) == WRITER_FAILED {
            return Err(std::io::ErrorKind::Other.into());
        }
        std::thread::sleep(Duration::from_millis(2));
    }
}

fn runtime() -> Option<&'static RuntimeCapture> {
    TRACE.get_or_init(|| {
        if !std::env::var_os("VICTORY_CPU_TRACE").is_some_and(|v| v == "1") {
            return None;
        }
        let path = PathBuf::from(std::env::var_os("VICTORY_CPU_TRACE_PATH")?);
        if path.as_os_str().is_empty() { return None; }
        let controller = Arc::new(Controller::new(true, 600, 8, 256));
        let worker = Arc::clone(&controller);
        let origin = Instant::now();
        std::thread::Builder::new().name("victory-cpu-trace".into()).spawn(move || {
            if publish_capture(&worker, &path, origin + Duration::from_secs(900)).is_err() {
                worker.fail(WRITER_FAILED);
            }
        }).ok()?;
        Some(RuntimeCapture { controller, origin })
    }).as_ref()
}

pub(crate) enum Hook { Execute, PaceSleep, PresentCall }
pub(crate) struct Observation {
    runtime: &'static RuntimeCapture,
    ticket: Ticket,
}
fn stamp(runtime: &RuntimeCapture) -> Option<u64> {
    u64::try_from(runtime.origin.elapsed().as_nanos()).ok()
}

pub(crate) fn begin(hook: Hook) -> Option<Observation> {
    let runtime = runtime()?;
    if !runtime.controller.observing() { return None; }
    let kind = match hook {
        Hook::Execute => Kind::Execute,
        Hook::PaceSleep => Kind::PaceSleep,
        Hook::PresentCall => Kind::PresentCall,
    };
    // Reserve before measuring: exclude begin's capture bookkeeping from
    // the measured outer call. Failed reservation is never fabricated.
    let mut ticket = runtime.controller.begin(kind, 0)?;
    let Some(start) = stamp(runtime) else {
        runtime.controller.fail(EXHAUSTED);
        return None;
    };
    ticket.start_ns = start;
    Some(Observation { runtime, ticket })
}

pub(crate) fn end(observation: Option<Observation>, ok: bool) {
    let Some(o) = observation else { return; };
    let Some(end_ns) = stamp(o.runtime) else {
        o.runtime.controller.fail(EXHAUSTED);
        return;
    };
    o.runtime.controller.finish(o.ticket, end_ns, ok);
}

#[cfg(test)]
mod bridge_tests {
    use super::*;

    fn completed() -> Controller {
        let c = Controller::new(true, 1, 1, 4);
        for (a,b) in [(1,10),(19,20)] {
            let t = c.begin(Kind::PresentCall, a).unwrap();
            c.finish(t, b, true);
        }
        c
    }
    struct Temp(PathBuf);
    impl Temp {
        fn new() -> Self {
            let p = std::env::temp_dir().join(format!("victory-trace-test-{}-{}", std::process::id(), fresh_id().unwrap()));
            std::fs::create_dir(&p).unwrap();
            Self(p)
        }
    }
    impl Drop for Temp {
        fn drop(&mut self) { let _ = std::fs::remove_dir_all(&self.0); }
    }

    #[test]
    fn writer_publishes_complete_file() {
        let d = Temp::new();
        let p = d.0.join("capture.jsonl");
        publish_capture(&completed(), &p, Instant::now()+Duration::from_secs(2)).unwrap();
        let text = std::fs::read_to_string(&p).unwrap();
        assert_eq!(text.lines().count(), 2);
        assert!(text.lines().last().unwrap().contains("cpu_trace_end_v1"));
        assert!(!d.0.join("capture.jsonl.partial").exists());
    }

    #[test]
    fn writer_never_replaces_existing_files() {
        let d = Temp::new();
        let p = d.0.join("capture.jsonl");
        std::fs::write(&p, b"existing").unwrap();
        assert!(publish_capture(&completed(), &p, Instant::now()+Duration::from_secs(2)).is_err());
        assert_eq!(std::fs::read(&p).unwrap(), b"existing");
        let partial = d.0.join("capture.jsonl.partial");
        let prior = std::fs::read(&partial).unwrap();
        assert!(publish_capture(&completed(), &p, Instant::now()+Duration::from_secs(2)).is_err());
        assert_eq!(std::fs::read(&partial).unwrap(), prior);
    }

    #[test]
    fn timeout_does_not_publish() {
        let d = Temp::new();
        let p = d.0.join("capture.jsonl");
        let c = Controller::new(true, 1, 1, 4);
        assert!(publish_capture(&c, &p, Instant::now()).is_err());
        assert!(!p.exists());
        assert!(!std::fs::read_to_string(d.0.join("capture.jsonl.partial")).unwrap().contains("cpu_trace_end_v1"));
    }
}
