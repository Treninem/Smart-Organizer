import json
import unittest
from pathlib import Path


class ReleaseConsistencyTests(unittest.TestCase):
    def test_runtime_manifest_matches_application_version(self):
        app_version = json.loads(Path("version.json").read_text(encoding="utf-8"))["version"]
        runtime_version = json.loads(Path("runtime-manifest.json").read_text(encoding="utf-8"))["version"]
        self.assertEqual(app_version, runtime_version)

    def test_legacy_bridge_matches_application_version_and_is_fail_safe(self):
        app_version = json.loads(Path("version.json").read_text(encoding="utf-8"))["version"]
        bridge = json.loads(Path("update-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(app_version, bridge["version"])
        paths = [item["path"] for item in bridge["files"]]
        self.assertEqual("main.py", paths[0])
        self.assertIn("core/runtime_update.py", paths)
        self.assertIn("core/auto_update_runtime.py", paths)
        self.assertEqual("version.json", paths[-1])
        self.assertNotIn("data/", paths)
        self.assertNotIn("logs/", paths)


if __name__ == "__main__":
    unittest.main()
