import unittest
from pathlib import Path

from core.scanner import _filter_dirs


class ScannerFilterTests(unittest.TestCase):
    def test_project_windows_folder_is_kept(self):
        root = Path("project")
        kept = _filter_dirs(root, root, ["Windows", "src"])
        self.assertIn("Windows", kept)
        self.assertIn("src", kept)

    def test_cache_folders_are_excluded(self):
        root = Path("project")
        kept = _filter_dirs(root, root, ["__pycache__", "node_modules", ".git", "src"])
        self.assertEqual(["src"], kept)


if __name__ == "__main__":
    unittest.main()
