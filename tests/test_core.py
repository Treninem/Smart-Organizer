import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

from core.archive_analyzer import analyze_archive
from core.classifier import category_for, project_hint
from core.database import Database
from core.duplicates import exact_duplicate_groups
from core.project_manager import rank_existing_folders, suggest_destination
from core.scanner import scan_tree
from core.system_monitor import _format_network_speed
from core.updater import parse_version
from core.version_manager import artifact_key, detect_version, version_groups

PROJECTS = [{"name": "VoxLyra", "type": "Telegram/VK bot + Mini App", "aliases": ["Vox Lyra"], "keywords": ["voxlyra", "comic"]}]


class CoreTests(unittest.TestCase):
    def test_versions(self):
        self.assertLess(parse_version("v1.0.3"), parse_version("v3.0"))
        info = detect_version("VoxLyra_v1.15.9.zip")
        self.assertIsNotNone(info)
        self.assertEqual(info.normalized, "v1.15.9")
        self.assertEqual(detect_version("app_v2.0-rc2.zip").channel, "rc")
        self.assertEqual(artifact_key("VoxLyra_v1.15.9.zip"), "voxlyra")

    def test_version_groups(self):
        records = [
            {"path": "a", "name": "VoxLyra_v1.0.zip", "project_hint": "VoxLyra"},
            {"path": "b", "name": "VoxLyra_v1.2.zip", "project_hint": "VoxLyra"},
        ]
        groups = version_groups(records)
        self.assertEqual(groups[0]["newest"], "v1.2")
        self.assertEqual(groups[0]["older"][0]["version"], "v1.0")

    def test_classifier(self):
        self.assertEqual(category_for(Path("image.png")), "Изображения")
        self.assertEqual(category_for(Path("app.py")), "Код")
        self.assertEqual(project_hint(Path("VoxLyra_comic_import.zip"), PROJECTS), "VoxLyra")

    def test_scan_is_read_only_and_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Existing").mkdir()
            f = root / "Existing" / "VoxLyra_v1.0.zip"
            f.write_bytes(b"abc")
            before = f.read_bytes()
            result = scan_tree(root, PROJECTS)
            self.assertEqual(before, f.read_bytes())
            db = Database(root / "knowledge.db")
            db.replace_scan(result.folders, result.files)
            self.assertEqual(db.counts()["files"], 1)
            db.close()

    def test_database_thread_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(Path(tmp) / "knowledge.db")
            errors = []

            def worker():
                try:
                    db.log_action("thread-test", None, "ok")
                    db.set_setting("thread-value", 1)
                except Exception as exc:
                    errors.append(exc)

            t = threading.Thread(target=worker)
            t.start()
            t.join()
            self.assertEqual(errors, [])
            self.assertEqual(db.get_setting("thread-value"), 1)
            db.close()

    def test_exact_duplicate_hashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a, b, c = root / "bot.exe", root / "bot(1).exe", root / "other.exe"
            a.write_bytes(b"same")
            b.write_bytes(b"same")
            c.write_bytes(b"diff")
            records = []
            for path in (a, b, c):
                st = path.stat()
                records.append({"path": str(path), "name": path.name, "size": st.st_size, "modified": st.st_mtime})
            groups = exact_duplicate_groups(records)
            self.assertEqual(len(groups), 1)
            self.assertEqual(groups[0]["canonical"], str(a))
            self.assertIn(str(b), groups[0]["duplicates"])

    def test_existing_tree_wins(self):
        record = {"path": r"D:\Downloads\VoxLyra_v1.2.zip", "parent": r"D:\Downloads", "name": "VoxLyra_v1.2.zip", "category": "Архивы", "project_hint": "VoxLyra"}
        folders = [
            {"path": r"D:\MyStuff\Bots\VoxLyra\Releases", "name": "Releases", "depth": 4},
            {"path": r"D:\Other", "name": "Other", "depth": 1},
        ]
        ranked = rank_existing_folders(record, folders, PROJECTS)
        self.assertTrue(ranked)
        self.assertEqual(ranked[0]["path"], r"D:\MyStuff\Bots\VoxLyra\Releases")
        self.assertEqual(suggest_destination(record, folders, PROJECTS, r"D:\MyStuff")["mode"], "existing")

    def test_zip_archive_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "VoxLyra_v1.2.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("app/main.py", "print('x')")
                zf.writestr("comic/cover.jpg", b"jpg")
            result = analyze_archive(archive, PROJECTS)
            self.assertEqual(result["format"], "ZIP")
            self.assertEqual(result["entries"], 2)
            self.assertEqual(result["project_hint"], "VoxLyra")
            self.assertEqual(result["version"], "v1.2")
            self.assertTrue(result["read_only"])

    def test_network_speed_format(self):
        self.assertEqual(_format_network_speed(0), "0 bit/s")
        self.assertEqual(_format_network_speed(125_000), "1.0 Mbit/s")
        self.assertEqual(_format_network_speed(12_500_000), "100.0 Mbit/s")


if __name__ == "__main__":
    unittest.main()
