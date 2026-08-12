import tempfile
import unittest
from pathlib import Path

from core.runtime_update import create_apply_script, runtime_update_needed


class RuntimeUpdateTests(unittest.TestCase):
    def test_older_version_requires_runtime_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "runtime-build.txt").write_text("old-build", encoding="ascii")
            manifest = {"version": "0.2.7"}
            release = {"target_commitish": "new-build"}
            self.assertTrue(runtime_update_needed(root, "0.2.6", manifest, release))

    def test_same_version_same_build_is_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "runtime-build.txt").write_text("same-build", encoding="ascii")
            manifest = {"version": "0.2.7"}
            release = {"target_commitish": "same-build"}
            self.assertFalse(runtime_update_needed(root, "0.2.7", manifest, release))

    def test_same_version_missing_build_marker_requires_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = {"version": "0.2.7"}
            release = {"target_commitish": "published-build"}
            self.assertTrue(runtime_update_needed(root, "0.2.7", manifest, release))

    def test_apply_script_resets_pyinstaller_environment_and_preserves_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / ".update-staging" / "SmartOrganizer-runtime.zip"
            bundle.parent.mkdir(parents=True)
            bundle.write_bytes(b"zip-placeholder")
            script = create_apply_script(root, bundle, 12345)
            text = script.read_text(encoding="ascii")
            self.assertIn("PYINSTALLER_RESET_ENVIRONMENT", text)
            self.assertIn("_PYI_APPLICATION_HOME_DIR", text)
            self.assertNotIn("Join-Path $root 'data'", text)
            self.assertNotIn("Join-Path $root 'logs'", text)
            self.assertIn(".runtime-backup", text)

    def test_apply_script_backs_up_complete_replaceable_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / ".update-staging" / "SmartOrganizer-runtime.zip"
            bundle.parent.mkdir(parents=True)
            bundle.write_bytes(b"zip-placeholder")
            script = create_apply_script(root, bundle, 12345)
            text = script.read_text(encoding="ascii")
            for item in (
                "SmartOrganizer.exe",
                "updater.exe",
                "_runtime",
                "main.py",
                "app",
                "core",
                "modules",
                "config",
                "version.json",
                "runtime-manifest.json",
                "runtime-build.txt",
            ):
                self.assertIn(f"'{item}'", text)
            self.assertIn("foreach ($name in $runtimeItems)", text)
            self.assertIn("Move-Item -LiteralPath $saved", text)


if __name__ == "__main__":
    unittest.main()
