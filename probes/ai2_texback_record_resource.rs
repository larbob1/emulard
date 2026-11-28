// SPDX-License-Identifier: GPL-3.0-or-later
// Append only to a disposable pinned prepared resource.rs.
#[cfg(all(test, windows, feature = "diagnostics"))]
pub(crate) mod ai2_record_resource {
    use super::*;

    pub(crate) fn create(at: usize) -> This {
        assert_ne!(at, 0);
        assert_eq!(at % 256, 0);
        assert!(!TARGETS_AT.lock().unwrap().contains_key(&(at as u64)));
        assert!(!PLACED_TEXTURES.lock().unwrap().keys().any(|(a, _)| *a == at as u64));
        let desc = ResourceDesc {
            dimension: 3, alignment: 0, width: 7, height: 3,
            depth_or_array_size: 2, mip_levels: 2, format: 61,
            sample_count: 1, sample_quality: 0, layout: 1, flags: 4,
        };
        let mut out = std::ptr::null();
        assert_eq!(create_at_address(std::ptr::null(), at as u64, &desc, 0,
            std::ptr::null(), &RESOURCE_IIDS[0], &mut out), S_OK);
        assert!(!out.is_null());
        assert!(textures().contains(&(out as usize)));
        assert_eq!(TARGETS_AT.lock().unwrap().get(&(at as u64)), Some(&(out as usize)));
        assert!(!resource(out).host.placed.load(std::sync::atomic::Ordering::Relaxed));
        assert!(!title_fills(out));
        assert!(!PLACED_TEXTURES.lock().unwrap().keys().any(|(a, _)| *a == at as u64));
        out
    }

    pub(crate) fn release(this: This, at: usize) {
        assert!(!this.is_null());
        assert_eq!(resource(this).data() as usize, at);
        assert!(textures().contains(&(this as usize)));
        assert_eq!(resource_release(this), 0);
        // Check numeric registry keys only after release, never dereference this.
        assert!(!textures().contains(&(this as usize)));
        assert!(!TARGETS_AT.lock().unwrap().contains_key(&(at as u64)));
        assert!(!PLACED_TEXTURES.lock().unwrap().keys().any(|(a, _)| *a == at as u64));
    }
}
