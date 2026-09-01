import tempfile
import unittest
from pathlib import Path

from host.eegstream.session import SessionReader, write_synthetic
from inference.pipeline import analyze_session


class ReplayTests(unittest.TestCase):
    def test_deterministic_replay(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "s.eeg"
            write_synthetic(path, n_samples=250, sample_rate=250.0)
            a = analyze_session(SessionReader(path)).as_dict()
            b = analyze_session(SessionReader(path)).as_dict()
            self.assertEqual(a["features"], b["features"])
            self.assertIn("alpha_power", a["features"])
            self.assertIn("artifact_probability", a["features"])

    def test_baseline_relative_delta(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "s.eeg"
            write_synthetic(path, n_samples=250, sample_rate=250.0)
            first = analyze_session(SessionReader(path))
            second = analyze_session(SessionReader(path), baseline=first.features)
            self.assertTrue(second.baseline_delta)
            self.assertAlmostEqual(second.baseline_delta["alpha_power"], 0.0, places=9)


if __name__ == "__main__":
    unittest.main()
