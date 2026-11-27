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
