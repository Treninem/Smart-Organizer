import ast
import unittest
from pathlib import Path


class StartupPerformanceTests(unittest.TestCase):
    def test_main_has_no_blocking_network_before_gui(self):
        source = Path("main.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertNotIn("urllib.request", imported)
        self.assertNotIn("core.updater", imported)
        self.assertNotIn("_prelaunch_update", source)
        self.assertNotIn("_fetch_release_asset", source)


if __name__ == "__main__":
    unittest.main()
