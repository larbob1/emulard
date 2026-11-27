# SPDX-License-Identifier: GPL-3.0-or-later
"""Check the actual test-only fixture wiring; GPU execution needs WARP."""
import unittest
from apply_pipeline_perf import PATCHES

class HeapRecordingObservationTests(unittest.TestCase):
    def test_fixture_calls_actual_paths_and_never_submits(self):
        src = "\n".join(new for _,new in PATCHES["crates/victory-gpu/src/descriptor.rs"])
        self.assertIn('#[ignore = "requires isolated WARP process;',src)
        self.assertIn('heap_recording_observation_software_adapter()',src)
        self.assertIn('a.observe_heap_buffers_for_test(&first)',src)
        self.assertIn('b.observe_heap_buffers_for_test(&second)',src)
        self.assertIn('assert!(initial.0 > 0',src)
        self.assertIn('assert_eq!(skipped, (0,0,0)',src)
        self.assertIn('assert_eq!(release(h), 0)',src)
        self.assertNotIn('gpu.execute(',src)
        self.assertNotIn('gpu.execute_own(',src)
        self.assertNotIn('crate::shadow::unregister(',src)
        self.assertNotIn('VirtualFree(',src)

    def test_slot_materialization_and_stride_positive_control(self):
        src = "\n".join(new for _,new in PATCHES["crates/victory-gpu/src/descriptor.rs"])
        pre = src.index('assert!(!heap_host.made(0)')
        refresh = src.index('a.observe_heap_buffers_for_test(&first)')
        post = src.index('assert!(heap_host.made(0)')
        self.assertLess(pre, refresh)
        self.assertLess(refresh, post)
        self.assertIn('heap_host.shows(0, &shadow.buffer), None',src)
        self.assertIn('heap_host.shows(0, &shadow.buffer), Some(true)',src)
        self.assertIn('FRAME skip still pins stride table',src)
        self.assertIn('ONCE must not duplicate stride pin',src)
        for name in ("first", "second"):
            pin = f'{name}.observe_recorded_ownership(shadow_id,stride_identity).2'
            self.assertIn(f'assert_eq!({pin}, 1',src)
            self.assertGreaterEqual(src.count(f'assert_eq!({pin}, 0)'),2)

    def test_real_slot_rewrite_is_observed_before_wrapper_release(self):
        src = "\n".join(new for _,new in PATCHES["crates/victory-gpu/src/descriptor.rs"])
        start = src.index("desc[6] = (LEN / 8) as u32")
        finish = src.index("slot rewrite does not repair FRAME skip", start)
        section = src[start:finish]
        self.assertIn("create_placed_srv(std::ptr::null(), &resource, &desc, handle)", section)
        self.assertIn("old slot COM reference removed", section)
        self.assertIn("heap_host.mirror(0, handle, true)", section)
        self.assertIn("slot rewrite preserves first recorded ownership", section)
        self.assertLess(finish, src.index("assert_eq!(release(h), 0)", finish))

    def test_observers_are_test_only_and_nonowning(self):
        draw = "\n".join(new for _,new in PATCHES["crates/victory-gpu/src/draw.rs"])
        host = "\n".join(new for _,new in PATCHES["crates/victory-gpu/src/host.rs"])
        self.assertIn("#[cfg(test)]\n    pub(crate) fn observe_heap_buffers_for_test",draw)
        self.assertIn("self.heap_buffers(list)",draw)
        self.assertIn("#[cfg(test)]\n    pub(crate) fn observe_recorded_ownership",host)
        part = host.split("pub(crate) fn observe_recorded_ownership",1)[1].split("/// Keeps",1)[0]
        self.assertIn("Step::Refresh(s, _, _) if s.id() == shadow_id",part)
        self.assertIn("Step::GpuWrite(s, _, _) if s.id() == shadow_id",part)
        self.assertIn("deferred.kept.iter()",part)
        self.assertNotIn(".clone()",part)
        self.assertNotIn(".cast",part)

    def test_detached_fixture_uses_actual_title_list_lifecycle(self):
        src = "\n".join(new for _, new in PATCHES["crates/victory-gpu/src/list.rs"])
        self.assertIn("fn detached_list_keeps_recording_after_title_reset()", src)
        self.assertIn("old.keep(&fence)", src)
        self.assertIn("drop(fence)", src)
        self.assertIn("detach(&[title, title])", src)
        self.assertIn("assert_eq!(order, [0, 0])", src)
        self.assertIn("saved._uploads.iter()", src)
        self.assertLess(src.index("saved._uploads.iter()"), src.index("from_raw_parts(p, 40)"))
        self.assertLess(src.index("release(title)"), src.index("from_raw_parts(p, 40)"))
        self.assertIn("drop(detached)", src)
        self.assertNotIn("gpu.execute(", src)
        self.assertNotIn(".Signal(", src)
