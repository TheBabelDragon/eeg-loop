import unittest

from inference.features.extract import artifact_probability, feature_vector


class FeatureTests(unittest.TestCase):
    def test_flatline_low_variance(self):
        xs = [1.0] * 128
        feats = feature_vector(xs, 250.0)
        self.assertEqual(feats["variance"], 0.0)

    def test_spike_raises_artifact(self):
        xs = [0.0] * 100
        xs[50] = 100.0
        self.assertGreater(artifact_probability(xs), 0.3)


if __name__ == "__main__":
    unittest.main()
