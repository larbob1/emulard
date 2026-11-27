// Standalone Rust TLS destructor boundary; not Windows loader callbacks.
use std::cell::RefCell;
use std::sync::{Arc, Mutex, mpsc};
use std::thread;
use std::time::Duration;

const LIMIT: Duration = Duration::from_secs(5);
#[derive(Default)]
struct State {
    idle: usize,
    retiring: usize,
    queued: usize,
}
fn needs_worker(s: &State) -> bool { s.queued > s.idle }

struct Cleanup {
    state: Arc<Mutex<State>>,
    entered: mpsc::Sender<()>,
    release: mpsc::Receiver<()>,
    ended: mpsc::Sender<()>,
}
impl Drop for Cleanup {
    fn drop(&mut self) {
        // Test only: prove the scheduler mutex is not held during cleanup.
        let unlocked = self.state.try_lock().is_ok();
        if !unlocked { return; }
        let _ = self.entered.send(());
        if self.release.recv_timeout(LIMIT).is_ok() {
            let _ = self.ended.send(());
        }
    }
}
thread_local! {
    static CLEANUP: RefCell<Option<Cleanup>> = const { RefCell::new(None) };
}

#[test]
fn retirement_precedes_thread_cleanup_and_new_admission() {
    let state = Arc::new(Mutex::new(State { idle: 1, ..State::default() }));
    let (entered_tx, entered_rx) = mpsc::channel();
    let (release_tx, release_rx) = mpsc::channel();
    let (ended_tx, ended_rx) = mpsc::channel();
    let worker_state = state.clone();
    let worker = thread::spawn(move || {
        CLEANUP.with(|slot| *slot.borrow_mut() = Some(Cleanup {
            state: worker_state.clone(), entered: entered_tx,
            release: release_rx, ended: ended_tx,
        }));
        {
            let mut s = worker_state.lock().unwrap();
            s.idle -= 1;
            s.retiring += 1;
        }
        // Return normally; Rust TLS cleanup runs after this body.
    });
    entered_rx.recv_timeout(LIMIT).expect("cleanup must run with scheduler unlocked");
    {
        let mut s = state.lock().unwrap();
        assert_eq!((s.idle, s.retiring), (0, 1));
        s.queued += 1;
        assert!(needs_worker(&s));
        // Counting the exiting worker as available would suppress admission.
        assert!(!(s.queued > s.idle + s.retiring));
    }
    let (done_tx, done_rx) = mpsc::channel();
    let replacement_state = state.clone();
    let replacement = thread::spawn(move || {
        let mut s = replacement_state.lock().unwrap();
        assert_eq!(s.queued, 1);
        s.queued -= 1;
        drop(s);
        done_tx.send(()).unwrap();
    });
    done_rx.recv_timeout(LIMIT).unwrap();
    replacement.join().unwrap();
    assert!(ended_rx.try_recv().is_err());
    release_tx.send(()).unwrap();
    ended_rx.recv_timeout(LIMIT).unwrap();
    worker.join().unwrap();
    // Only this observing harness knows join has completed.
    let mut s = state.lock().unwrap();
    s.retiring -= 1;
    assert_eq!((s.idle, s.retiring, s.queued), (0, 0, 0));
}

#[test]
fn pending_start_is_not_entered_capacity() {
    let (entered_tx, entered_rx) = mpsc::channel();
    let (release_tx, release_rx) = mpsc::channel();
    let worker = thread::spawn(move || {
        release_rx.recv_timeout(LIMIT).unwrap();
        entered_tx.send(()).unwrap();
    });
    // A successful spawn returns a handle, not proof that work has begun.
    assert!(entered_rx.try_recv().is_err());
    release_tx.send(()).unwrap();
    entered_rx.recv_timeout(LIMIT).unwrap();
    worker.join().unwrap();
}

#[test]
fn cleanup_may_require_scheduler_lock() {
    let state = Arc::new(Mutex::new(State::default()));
    let (started_tx, started_rx) = mpsc::channel();
    let (acquired_tx, acquired_rx) = mpsc::channel();
    let guard = state.lock().unwrap();
    let other = state.clone();
    let worker = thread::spawn(move || {
        started_tx.send(()).unwrap();
        let _guard = other.lock().unwrap();
        acquired_tx.send(()).unwrap();
    });
    started_rx.recv_timeout(LIMIT).unwrap();
    assert!(acquired_rx.try_recv().is_err());
    // Never join under the mutex: cleanup can need it. This is a bounded
    // lock-dependency demonstration, not an actual deadlock attempt.
    drop(guard);
    acquired_rx.recv_timeout(LIMIT).unwrap();
    worker.join().unwrap();
}
