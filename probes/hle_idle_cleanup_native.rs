// Native Windows thread-handle / post-work / Rust TLS cleanup boundary, test-only clone.
// Does not load title images or exercise their forwarded loader callbacks.
#[cfg(test)]
mod hle_idle_cleanup_native_review {
    use super::*;
    use std::sync::{OnceLock, mpsc};
    use std::cell::RefCell;
    use std::time::Instant;
    use std::thread::JoinHandle;
    use std::os::windows::io::AsRawHandle;
    use windows_sys::Win32::Foundation::{WAIT_OBJECT_0, WAIT_TIMEOUT};
    use windows_sys::Win32::System::Threading::{GetCurrentThreadId, WaitForSingleObject};

    // @POOL_CLONE@

    const LIMIT: Duration = Duration::from_secs(5);
    static FIRST: AtomicBool = AtomicBool::new(true);
    static EVENTS: OnceLock<mpsc::Sender<(usize, u32, bool)>> = OnceLock::new();
    static CLEANUP_ENTERED: OnceLock<mpsc::Sender<u32>> = OnceLock::new();
    static RELEASE: OnceLock<Mutex<Option<mpsc::Receiver<()>>>> = OnceLock::new();
    static HANDLES: Mutex<Vec<JoinHandle<()>>> = Mutex::new(Vec::new());

    static TLS_DROPS: AtomicUsize = AtomicUsize::new(0);

    struct Cleanup;
    impl Drop for Cleanup {
        fn drop(&mut self) {
            // May run during platform-managed TLS cleanup. Only a fixed
            // atomic observation: no gate, mutex, allocation, or callback.
            TLS_DROPS.fetch_add(1, Ordering::SeqCst);
        }
    }
    thread_local! {
        static CLEANUP: RefCell<Option<Cleanup>> = const { RefCell::new(None) };
    }

    fn before_body_return(pool: &'static ReviewPool) {
        // This gate is after Pool::work returned, NOT in a TLS destructor.
        if pool.state.try_lock().is_err() { return; }
        let id = unsafe { GetCurrentThreadId() };
        if let Some(tx) = CLEANUP_ENTERED.get() {
            let _ = tx.send(id);
        }
        let rx = RELEASE.get().and_then(|m| m.lock().ok())
            .and_then(|mut slot| slot.take());
        if let Some(rx) = rx {
            let _ = rx.recv_timeout(LIMIT * 3);
        }
    }

    fn start(pool: &'static ReviewPool) {
        let first = FIRST.swap(false, Ordering::SeqCst);
        let handle = std::thread::spawn(move || {
            CLEANUP.with(|slot| *slot.borrow_mut() = Some(Cleanup));
            pool.work();
            if first { before_body_return(pool); }
        });
        lock(&HANDLES).push(handle);
    }

    extern "system" fn report(context: *mut c_void, canceled: bool) {
        if let Some(tx) = EVENTS.get() {
            let _ = tx.send((context as usize, unsafe { GetCurrentThreadId() }, !canceled));
        }
    }

    fn observe_retirement(pool: &ReviewPool, n: usize) {
        let deadline = Instant::now() + LIMIT;
        loop {
            {
                let s = lock(&pool.state);
                if s.0.is_empty() && s.1 == 0
                    && pool.retired.load(Ordering::SeqCst) == n { return; }
            }
            assert!(Instant::now() < deadline, "retirement watchdog");
            std::thread::sleep(Duration::from_millis(1));
        }
    }

    #[test]
    #[ignore = "fresh-process Windows thread cleanup boundary"]
    fn retired_worker_cleanup_does_not_supply_capacity() {
        let (tx, rx) = mpsc::channel();
        let (entered_tx, entered_rx) = mpsc::channel();
        let (release_tx, release_rx) = mpsc::channel();
        assert!(EVENTS.set(tx).is_ok());
        assert!(CLEANUP_ENTERED.set(entered_tx).is_ok());
        assert!(RELEASE.set(Mutex::new(Some(release_rx))).is_ok());
        let pool: &'static ReviewPool = Box::leak(Box::new(ReviewPool {
            state: Mutex::new((VecDeque::new(), 0)),
            ready: Condvar::new(),
            timeout: Some(Duration::from_millis(50)),
            retired: AtomicUsize::new(0),
        }));
        pool.submit(Task::new(1usize as *mut c_void, report));
        let (id, first_thread, ok) = rx.recv_timeout(LIMIT).unwrap();
        assert_eq!((id, ok), (1, true));
        assert_eq!(entered_rx.recv_timeout(LIMIT).unwrap(), first_thread);
        observe_retirement(pool, 1);
        let first_handle = {
            let mut handles = lock(&HANDLES);
            assert_eq!(handles.len(), 1);
            handles.pop().unwrap()
        };
        // SAFETY: borrowed valid OS thread handle owned by JoinHandle.
        assert_eq!(unsafe { WaitForSingleObject(first_handle.as_raw_handle(), 0) }, WAIT_TIMEOUT);
        pool.submit(Task::new(2usize as *mut c_void, report));
        let (id, replacement, ok) = rx.recv_timeout(LIMIT).unwrap();
        assert_eq!((id, ok), (2, true));
        assert_ne!(first_thread, replacement);
        assert_eq!(unsafe { WaitForSingleObject(first_handle.as_raw_handle(), 0) }, WAIT_TIMEOUT);
        observe_retirement(pool, 2);
        let second_handle = {
            let mut handles = lock(&HANDLES);
            assert_eq!(handles.len(), 1);
            handles.pop().unwrap()
        };
        // No scheduler/handle mutex is held while releasing or waiting.
        release_tx.send(()).unwrap();
        for handle in [first_handle, second_handle] {
            // SAFETY: borrowed thread handle, bounded native wait.
            assert_eq!(unsafe { WaitForSingleObject(handle.as_raw_handle(), 5000) }, WAIT_OBJECT_0);
            handle.join().unwrap();
        }
        assert!(rx.try_recv().is_err());
        assert!(lock(&HANDLES).is_empty());
        assert_eq!(TLS_DROPS.load(Ordering::SeqCst), 2);
    }
}
