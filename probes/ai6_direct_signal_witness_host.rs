// SPDX-License-Identifier: GPL-3.0-or-later
// Scratch-only host.rs append; called only by the isolated direct signal fixture.
#[cfg(all(test, feature = "diagnostics"))]
pub(crate) fn ai6_direct_signal_witness_preflight(h: &Host) {
    use windows::core::Interface;
    use windows::Win32::Graphics::Dxgi::{IDXGIAdapter1, DXGI_ADAPTER_FLAG_SOFTWARE};
    for key in ["VICTORY_CARD_BUFFERS", "VICTORY_RELAY", "VICTORY_WIDE_BACK"] {
        assert_eq!(std::env::var(key).as_deref(), Ok("0"));
    }
    assert!(!late() && !relay() && !timing());
    assert!(!crate::shadow::cards() && !crate::shadow::relay() && !crate::shadow::wide_back());
    let warp = warp_adapter().expect("strict WARP adapter");
    let desc = unsafe { warp.cast::<IDXGIAdapter1>().unwrap().GetDesc1().unwrap() };
    assert_ne!(desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE.0 as u32,0);
    let actual = unsafe { h.device.GetAdapterLuid() };
    let expected = desc.AdapterLuid;
    assert_eq!((actual.HighPart,actual.LowPart),(expected.HighPart,expected.LowPart));
    assert!(RETIRED.lock().unwrap().is_empty());
    assert_eq!(STARTED.load(Ordering::Acquire),0);
    assert_eq!(FINISHED.load(Ordering::Acquire),0);
    assert_eq!(*h.submitted.lock().unwrap(),0);
    assert_eq!(unsafe { h.fence.GetCompletedValue() },0);
    assert!(unsafe { h.device.GetDeviceRemovedReason() }.is_ok());
    eprintln!("direct_signal_adapter actual_high={} actual_low={} warp_high={} warp_low={} software=1",
        actual.HighPart,actual.LowPart,expected.HighPart,expected.LowPart);
}

#[cfg(all(test, feature = "diagnostics"))]
fn ai6_direct_signal_witness_wait_result(ok: bool) {
    if crate::queue::ai6_direct_signal_witness::active() && !ok {
        std::process::abort();
    }
}

// Called before FINISHED/bury, while the actual submit owns its fence domain.
// Do not take submitted or other mutexes here; caller provides its target.
#[cfg(all(test, feature = "diagnostics"))]
fn ai6_direct_signal_witness_before_retire(h: &Host, target: u64) {
    if !crate::queue::ai6_direct_signal_witness::active() { return; }
    let completed = unsafe { h.fence.GetCompletedValue() };
    if completed != target || completed == u64::MAX ||
        unsafe { h.device.GetDeviceRemovedReason() }.is_err() {
        std::process::abort();
    }
    crate::queue::ai6_direct_signal_witness::healthy(target,completed);
}

#[cfg(all(test, feature = "diagnostics"))]
pub(crate) fn ai6_direct_signal_witness_finish(h: &Host, expected: u64) {
    // Execution guards have returned. Registry empty is not global ownership proof.
    if *h.submitted.lock().unwrap_or_else(|_| std::process::abort()) != expected ||
        STARTED.load(Ordering::Acquire) != expected || FINISHED.load(Ordering::Acquire) != expected ||
        unsafe { h.fence.GetCompletedValue() } != expected ||
        unsafe { h.device.GetDeviceRemovedReason() }.is_err() {
        std::process::abort();
    }
    if !RETIRED.lock().unwrap_or_else(|_| std::process::abort()).is_empty() { std::process::abort(); }
}

// Check one owned buffer obligation and absence of deferred marker/texture work.
#[cfg(all(test, feature = "diagnostics"))]
fn ai6_direct_signal_witness_check_deferred(deferred: &Deferred) {
    if deferred.backs.len() != 1 || !deferred.writes.is_empty() ||
        !deferred.texture_backs.is_empty() || !deferred.back_wanted.is_empty() {
        std::process::abort();
    }
}

#[cfg(all(test, feature = "diagnostics"))]
pub(crate) fn ai6_direct_signal_witness_check_list(list: &HostList) {
    ai6_direct_signal_witness_check_deferred(&list.deferred());
}

#[cfg(all(test, feature = "diagnostics"))]
fn ai6_direct_signal_witness_readback(list: &HostList, deferred: &Deferred) {
    if !crate::queue::ai6_direct_signal_witness::active() { return; }
    ai6_direct_signal_witness_check_deferred(deferred);
    crate::queue::ai6_direct_signal_witness::readback(std::ptr::from_ref(list) as usize);
}
