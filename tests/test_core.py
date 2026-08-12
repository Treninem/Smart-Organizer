import tempfile
import unittest
from pathlib import Path

from core.classifier import category_for, project_hint
from core.database import Database
from core.scanner import scan_tree
from core.updater import parse_version


class CoreTests(unittest.TestCase):
    def test_versions(self):
        self.assertLess(parse_version("v1.0.3"), parse_version("v3.0"))
        self.assertEqual(parse_version("Version_2.1"), (2, 1))

    def test_classifier(self):
        self.assertEqual(category_for(Path("image.png")), "Изображения")
        self.assertEqual(category_for(Path("app.py")), "Код")

    def test_project_hint(self):
        projects = [{"name": "VoxLyra", "keywords": ["voxlyra", "comic"], "aliases": []}]
        self.assertEqual(project_hint(Path("VoxLyra_comic_import.zip"), projects), "VoxLyra")

    def test_scan_is_read_only_and_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Existing").mkdir()
            f = root / "Existing" / "VoxLyra_v1.0.zip"
            f.write_bytes(b"abc")
            before = f.read_bytes()
            result = scan_tree(root, [{"name": "VoxLyra", "keywords": ["voxlyra"], "aliases": []}])
            self.assertEqual(before, f.read_bytes())
            self.assertEqual(len(result.files), 1)
            db = Database(root / "knowledge.db")
            db.replace_scan(result.folders, result.files)
            self.assertEqual(db.counts()["files"], 1)
            db.close()


if __name__ == "__main__":
    unittest.main()
