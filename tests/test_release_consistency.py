import json
import unittest
from pathlib import Path


class ReleaseConsistencyTests(unittest.TestCase):
    def test_runtime_manifest_matches_application_version(self):
        app_version = json.loads(Path("version.json").read_text(encoding="utf-8"))["version"]
        runtime_version = json.loads(Path("runtime-manifest.json").read_text(encoding="utf-8"))["version"]
        self.assertEqual(app_version, runtime_version)


if __name__ == "__main__":
    unittest.main()
