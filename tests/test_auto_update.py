import unittest

from core.auto_update_runtime import (
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    MIN_UPDATE_INTERVAL_MINUTES,
    normalize_interval_minutes,
)


class AutoUpdateRuntimeTests(unittest.TestCase):
    def test_default_interval(self):
        self.assertEqual(normalize_interval_minutes(None), DEFAULT_UPDATE_INTERVAL_MINUTES)
        self.assertEqual(normalize_interval_minutes("bad"), DEFAULT_UPDATE_INTERVAL_MINUTES)

    def test_custom_interval(self):
        self.assertEqual(normalize_interval_minutes("10"), 10)
        self.assertEqual(normalize_interval_minutes(60), 60)
        self.assertEqual(normalize_interval_minutes(120), 120)

    def test_minimum_interval(self):
        self.assertEqual(normalize_interval_minutes(0), MIN_UPDATE_INTERVAL_MINUTES)
        self.assertEqual(normalize_interval_minutes(-5), MIN_UPDATE_INTERVAL_MINUTES)


if __name__ == "__main__":
    unittest.main()
