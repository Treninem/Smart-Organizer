import ast
import unittest
from pathlib import Path


class FrozenCompatibilityTests(unittest.TestCase):
    def test_windows_paths_has_no_top_level_ctypes_dependency(self):
        tree = ast.parse(Path("core/windows_paths.py").read_text(encoding="utf-8"))
        top_level_imports = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                top_level_imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                top_level_imports.add(node.module)
        self.assertNotIn("ctypes", top_level_imports)
        self.assertNotIn("ctypes.wintypes", top_level_imports)

    def test_atomic_runtime_update_replaces_old_launcher_logic(self):
        source = Path("core/auto_update_runtime.py").read_text(encoding="utf-8")
        self.assertIn("download_runtime_bundle", source)
        self.assertIn("create_apply_script", source)
        self.assertIn("PYINSTALLER_RESET_ENVIRONMENT", source)
        self.assertNotIn("SmartOrganizer.new.exe", source)

    def test_workflow_builds_onedir_not_onefile_for_main_app(self):
        source = Path(".github/workflows/build-windows.yml").read_text(encoding="utf-8")
        self.assertIn("--onedir --windowed", source)
        self.assertIn("--contents-directory _runtime", source)
        self.assertIn("SmartOrganizer-runtime.zip", source)

    def test_bootstrap_has_frozen_self_test_and_external_stdlib_dependencies(self):
        source = Path("bootstrap.py").read_text(encoding="utf-8")
        self.assertIn("--self-test", source)
        self.assertIn("import ctypes as _ctypes_test", source)
        self.assertIn("import uuid as _uuid_test", source)
        self.assertIn("import zipfile as _zipfile_test", source)
        self.assertIn("import zipfile", source)

    def test_recovery_updater_installs_verified_full_runtime(self):
        source = Path("updater_main.py").read_text(encoding="utf-8")
        self.assertIn("fetch_runtime_manifest", source)
        self.assertIn("fetch_runtime_release", source)
        self.assertIn("find_runtime_asset", source)
        self.assertIn("download_runtime_bundle", source)
        self.assertIn("create_apply_script", source)
        self.assertIn("launch_apply_script", source)
        self.assertNotIn("apply_source_update", source)


if __name__ == "__main__":
    unittest.main()
