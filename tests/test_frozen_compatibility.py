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

    def test_launcher_binary_update_runs_after_ui_start(self):
        source = Path("core/auto_update_runtime.py").read_text(encoding="utf-8")
        self.assertIn("start_launcher_update_check", source)
        self.assertIn("self.after(1500", source)
        self.assertIn("SmartOrganizer.new.exe", source)

    def test_bootstrap_has_frozen_self_test(self):
        source = Path("bootstrap.py").read_text(encoding="utf-8")
        self.assertIn("--self-test", source)
        self.assertIn("import ctypes as _ctypes_test", source)


if __name__ == "__main__":
    unittest.main()
