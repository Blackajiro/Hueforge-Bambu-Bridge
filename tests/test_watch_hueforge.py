from pathlib import Path
import tempfile
import unittest
from watch_hueforge import SaveTracker, find_stl


class WatchTests(unittest.TestCase):
    def test_wait_for_both_files_and_debounce(self):
        tracker = SaveTracker(('old HFP', 'old STL'))
        self.assertFalse(tracker.ready(('old HFP', 'old STL'), 10))
        self.assertFalse(tracker.ready(('new HFP', 'old STL'), 11))
        self.assertFalse(tracker.ready(('new HFP', 'old STL'), 20))
        self.assertFalse(tracker.ready(('new HFP', 'new STL'), 21))
        self.assertFalse(tracker.ready(('new HFP', 'new STL'), 23))
        self.assertTrue(tracker.ready(('new HFP', 'new STL'), 24))
        tracker.consume(('new HFP', 'new STL'))
        self.assertFalse(tracker.ready(('new HFP', 'new STL'), 30))

    def test_stl_before_hfp_and_write_restarts_timer(self):
        tracker = SaveTracker(('a', 'b'))
        self.assertFalse(tracker.ready(('a', 'c'), 0))
        self.assertFalse(tracker.ready(('d', 'c'), 2))
        self.assertFalse(tracker.ready(('d', 'e'), 4))
        self.assertFalse(tracker.ready(('d', 'e'), 6))
        self.assertTrue(tracker.ready(('d', 'e'), 7))

    def test_missing_stl_then_created(self):
        tracker = SaveTracker(('a', None))
        self.assertFalse(tracker.ready(('b', None), 0))
        self.assertFalse(tracker.ready(('b', None), 5))
        self.assertFalse(tracker.ready(('b', 'c'), 6))
        self.assertTrue(tracker.ready(('b', 'c'), 9))

    def test_exact_project_prefix_and_ambiguous_exports(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            hfp = folder/'my [fox].hfp'
            (folder/'other_Front_50x150.stl').touch()
            self.assertIsNone(find_stl(hfp))
            expected = folder/'my [fox]_Front_50x150.stl'
            expected.touch()
            self.assertEqual(find_stl(hfp), expected)
            (folder/'my [fox]_Front_60x180.stl').touch()
            with self.assertRaises(ValueError): find_stl(hfp)


if __name__ == '__main__':
    unittest.main()
