import json
import unittest
from pathlib import Path

from core.updater import update_available


class LegacyUpdateBridgeTests(unittest.TestCase):
    def setUp(self):
        self.legacy = json.loads(Path("update-manifest.json").read_text(encoding="utf-8"))
        self.runtime = json.loads(Path("runtime-manifest.json").read_text(encoding="utf-8"))
        self.paths = [item["path"] for item in self.legacy.get("files", [])]

    def test_v025_is_not_falsely_reported_as_current(self):
        self.assertTrue(update_available("0.2.5", self.legacy))

    def test_bridge_version_matches_runtime_version(self):
        self.assertEqual(self.legacy["version"], self.runtime["version"])

    def test_runtime_dependency_is_staged_before_auto_update_module(self):
        self.assertIn("core/runtime_update.py", self.paths)
        self.assertIn("core/auto_update_runtime.py", self.paths)
        self.assertLess(
            self.paths.index("core/runtime_update.py"),
            self.paths.index("core/auto_update_runtime.py"),
        )

    def test_version_marker_is_written_last(self):
        self.assertEqual(self.paths[-1], "version.json")

    def test_bridge_never_touches_user_data(self):
        for path in self.paths:
            normalized = path.replace("\\", "/").lstrip("/")
            self.assertFalse(normalized == "data" or normalized.startswith("data/"))
            self.assertFalse(normalized == "logs" or normalized.startswith("logs/"))

    def test_current_runtime_does_not_loop_through_legacy_source_updates(self):
        self.assertFalse(update_available(self.runtime["version"], self.legacy))


if __name__ == "__main__":
    unittest.main()
