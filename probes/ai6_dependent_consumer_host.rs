// SPDX-License-Identifier: GPL-3.0-or-later
// Scratch-only host.rs append; called only by the isolated queue fixture.
#[cfg(all(test, feature = "diagnostics"))]
pub(crate) fn ai6_dependent_consumer_preflight(h: &Host) {
    use windows::core::Interface;
    use windows::Win32::Graphics::Dxgi::{IDXGIAdapter1, DXGI_ADAPTER_FLAG_SOFTWARE};
    assert!(!late() && !relay() && !timing() && !crate::shadow::cards());
    let warp = warp_adapter().expect("strict WARP adapter");
    let desc = unsafe { warp.cast::<IDXGIAdapter1>().unwrap().GetDesc1().unwrap() };
    assert_ne!(desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE.0 as u32,0);
    let actual = unsafe { h.device.GetAdapterLuid() };
    let expected = desc.AdapterLuid;
    assert_eq!((actual.HighPart,actual.LowPart),(expected.HighPart,expected.LowPart));
    assert_eq!(STARTED.load(Ordering::Acquire),0);
    assert_eq!(FINISHED.load(Ordering::Acquire),0);
    assert_eq!(*h.submitted.lock().unwrap(),0);
    assert_eq!(unsafe { h.fence.GetCompletedValue() },0);
    assert!(unsafe { h.device.GetDeviceRemovedReason() }.is_ok());
    eprintln!("dependent_adapter actual_high={} actual_low={} warp_high={} warp_low={} software=1",
        actual.HighPart,actual.LowPart,expected.HighPart,expected.LowPart);
}

#[cfg(all(test, feature = "diagnostics"))]
fn ai6_dependent_consumer_wait_result(ok: bool) {
    if crate::queue::ai6_dependent_consumer::active() && !ok {
        std::process::abort();
    }
}

// Called before FINISHED/bury, while the actual submit owns its fence domain.
// Do not take submitted or other mutexes here; caller provides its target.
#[cfg(all(test, feature = "diagnostics"))]
fn ai6_dependent_consumer_before_retire(h: &Host, target: u64) {
    if !crate::queue::ai6_dependent_consumer::active() { return; }
    let completed = unsafe { h.fence.GetCompletedValue() };
    if completed != target || completed == u64::MAX ||
        unsafe { h.device.GetDeviceRemovedReason() }.is_err() {
        std::process::abort();
    }
    crate::queue::ai6_dependent_consumer::healthy(target,completed);
}

#[cfg(all(test, feature = "diagnostics"))]
pub(crate) fn ai6_dependent_consumer_finish(h: &Host) {
    // Called only after both synchronous calls return and the queues drain.
    if *h.submitted.lock().unwrap_or_else(|_| std::process::abort()) != 2 ||
        STARTED.load(Ordering::Acquire) != 2 || FINISHED.load(Ordering::Acquire) != 2 ||
        unsafe { h.fence.GetCompletedValue() } != 2 ||
        unsafe { h.device.GetDeviceRemovedReason() }.is_err() {
        std::process::abort();
    }
}
