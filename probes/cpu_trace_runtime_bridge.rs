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

struct Output {
    file: std::fs::File,
    partial: PathBuf,
    destination: PathBuf,
}

fn absent(path: &Path) -> std::io::Result<()> {
    match std::fs::symlink_metadata(path) {
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(e) => Err(e),
        Ok(_) => Err(std::io::ErrorKind::AlreadyExists.into()),
    }
}

fn within(path: &Path, root: &Path) -> bool {
    if path.starts_with(root) { return true; }
    // Windows paths are normally case-insensitive. Conservatively reject
    // case variants as well. External read-only isolation is still required.
    #[cfg(windows)]
    {
        let p = path.to_string_lossy().to_lowercase();
        let mut r = root.to_string_lossy().to_lowercase();
        if p == r { return true; }
        if !r.ends_with('\\') { r.push('\\'); }
        return p.starts_with(&r);
    }
    #[cfg(not(windows))]
    false
}

fn prepare_output(destination: &Path, title_root: &Path) -> std::io::Result<Output> {
    if !destination.is_absolute() {
        return Err(std::io::ErrorKind::InvalidInput.into());
    }
    let name = destination.file_name().ok_or(std::io::ErrorKind::InvalidInput)?;
    let parent = destination.parent().ok_or(std::io::ErrorKind::InvalidInput)?.canonicalize()?;
    let title = title_root.canonicalize()?;
    if within(&parent, &title) {
        return Err(std::io::ErrorKind::PermissionDenied.into());
    }
    let destination = parent.join(name);
    absent(&destination)?;
    let mut name = destination.as_os_str().to_os_string();
    name.push(".partial");
    let partial = PathBuf::from(name);
    let file = std::fs::OpenOptions::new().write(true).create_new(true).open(&partial)?;
    Ok(Output { file, partial, destination })
}

fn write_capture(c: &Controller, output: Output, deadline: Instant) -> std::io::Result<()> {
    let Output { mut file, partial, destination } = output;
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
            std::fs::hard_link(&partial, &destination)?;
            let _ = std::fs::remove_file(&partial);
            return Ok(());
        }
        if c.stop.load(Ordering::Acquire) == WRITER_FAILED {
            return Err(std::io::ErrorKind::Other.into());
        }
        std::thread::sleep(Duration::from_millis(2));
    }
}

// Only the application's pre-title startup path invokes this initializer.
// The caller may wait for readiness here, never in execute/present/wait.
fn start_runtime(
    enabled: bool, path: Option<PathBuf>, title_root: &Path,
    launch: impl FnOnce(Box<dyn FnOnce() + Send>) -> std::io::Result<()>,
) -> Option<RuntimeCapture> {
    if !enabled { return None; }
    let output = prepare_output(&path?, title_root).ok()?;
    let partial = output.partial.clone();
    let controller = Arc::new(Controller::new(true, 600, 8, 256));
    let worker = Arc::clone(&controller);
    let (ready_tx, ready_rx) = std::sync::mpsc::sync_channel(0);
    let origin = Instant::now();
    let result = launch(Box::new(move || {
        // The output file already exists and is uniquely owned.
        if ready_tx.send(()).is_err() { return; }
        if write_capture(&worker, output, origin + Duration::from_secs(900)).is_err() {
            worker.fail(WRITER_FAILED);
        }
    }));
    if result.is_err() {
        // The failed spawn dropped the closure and its open file.
        let _ = std::fs::remove_file(partial);
        return None;
    }
    if ready_rx.recv_timeout(Duration::from_secs(2)).is_err() {
        controller.fail(WRITER_FAILED);
        return None;
    }
    Some(RuntimeCapture { controller, origin })
}

pub fn initialize(title_root: &Path) {
    TRACE.get_or_init(|| {
        let enabled = std::env::var_os("VICTORY_CPU_TRACE").is_some_and(|v| v == "1");
        let path = if enabled { std::env::var_os("VICTORY_CPU_TRACE_PATH").map(PathBuf::from) } else { None };
        start_runtime(enabled, path, title_root, |job| {
            std::thread::Builder::new().name("victory-cpu-trace".into()).spawn(job).map(|_| ())
        })
    });
}

fn runtime() -> Option<&'static RuntimeCapture> {
    // get() returns None even if a separate thread is initializing.
    // No environment lookup, allocation, spawn, or wait in a hook.
    TRACE.get().and_then(Option::as_ref)
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

    fn publish_capture(c: &Controller, destination: &Path, deadline: Instant) -> std::io::Result<()> {
        let d = Temp::new();
        write_capture(c, prepare_output(destination, &d.0)?, deadline)
    }

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
        let title = Temp::new();
        let output = prepare_output(&p, &title.0).unwrap();
        std::fs::write(&p, b"existing").unwrap();
        assert!(write_capture(&completed(), output, Instant::now()+Duration::from_secs(2)).is_err());
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

    #[test]
    fn disabled_and_failed_preflight_never_spawn() {
        let title = Temp::new();
        let d = Temp::new();
        let path = d.0.join("capture.jsonl");
        assert!(start_runtime(false, Some(path.clone()), &title.0, |_| panic!("spawn")).is_none());
        assert!(!path.exists());
        assert!(start_runtime(true, Some(title.0.join("forbidden.jsonl")), &title.0,
                              |_| panic!("spawn")).is_none());
        assert!(start_runtime(true, Some(PathBuf::from("relative.jsonl")), &title.0,
                              |_| panic!("spawn")).is_none());
        assert!(start_runtime(true, Some(d.0.join("missing").join("x.jsonl")), &title.0,
                              |_| panic!("spawn")).is_none());
        std::fs::write(&path, b"existing").unwrap();
        assert!(start_runtime(true, Some(path.clone()), &title.0, |_| panic!("spawn")).is_none());
        assert_eq!(std::fs::read(path).unwrap(), b"existing");
    }

    #[test]
    fn failed_spawn_does_not_enable_capture() {
        let title = Temp::new();
        let d = Temp::new();
        let path = d.0.join("capture.jsonl");
        assert!(start_runtime(true, Some(path.clone()), &title.0, |job| {
            drop(job);
            Err(std::io::ErrorKind::Other.into())
        }).is_none());
        assert!(!path.exists());
        assert!(!d.0.join("capture.jsonl.partial").exists());
    }

    #[test]
    fn ready_before_capture_and_incomplete_never_publishes() {
        let title = Temp::new();
        let d = Temp::new();
        let path = d.0.join("capture.jsonl");
        let mut join = None;
        let rt = start_runtime(true, Some(path.clone()), &title.0, |job| {
            join = Some(std::thread::spawn(job));
            Ok(())
        }).unwrap();
        assert!(rt.controller.observing());
        assert!(d.0.join("capture.jsonl.partial").exists());
        rt.controller.fail(WRITER_FAILED);
        join.unwrap().join().unwrap();
        assert!(!path.exists());
    }

    #[test]
    fn nonblocking_read_during_initialization() {
        let slot = OnceLock::<Option<u32>>::new();
        let entered = std::sync::Barrier::new(2);
        let release = std::sync::Barrier::new(2);
        std::thread::scope(|s| {
            s.spawn(|| {
                slot.get_or_init(|| {
                    entered.wait();
                    release.wait();
                    Some(7)
                });
            });
            entered.wait();
            assert!(slot.get().is_none());
            release.wait();
        });
        assert_eq!(slot.get(), Some(&Some(7)));
    }
}
