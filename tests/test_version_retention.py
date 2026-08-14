import tempfile
import unittest
from pathlib import Path

from core.version_retention import build_version_retention_plan, quarantine_operations


class VersionRetentionTests(unittest.TestCase):
    def _file(self, path: Path, category="Архивы") -> dict:
        return {
            "path": str(path),
            "parent": str(path.parent),
            "name": path.name,
            "extension": path.suffix.lower(),
            "size": 1,
            "modified": 0,
            "category": category,
            "project_hint": None,
        }

    def _folder(self, path: Path, parent: Path, depth=1) -> dict:
        return {"path": str(path), "parent": str(parent), "name": path.name, "depth": depth}

    def test_six_archive_versions_keep_latest_five(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = [self._file(root / f"VoxLyra_v{i}.0.zip") for i in range(1, 7)]
            plan = build_version_retention_plan(files, [], keep_latest=5)
            self.assertEqual(1, plan["summary"]["candidates"])
            self.assertEqual(1, plan["summary"]["archive_candidates"])
            self.assertTrue(plan["items"][0]["source"].endswith("VoxLyra_v1.0.zip"))
            self.assertEqual(0, plan["summary"]["permanent_deletes"])

    def test_code_folders_require_project_marker_and_move_whole(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folders = []
            files = []
            for i in range(1, 7):
                folder = root / f"SmartOrganizer_v{i}.0"
                folders.append(self._folder(folder, root))
                files.append(self._file(folder / "main.py", category="Код"))
            plan = build_version_retention_plan(files, folders, keep_latest=5)
            self.assertEqual(1, plan["summary"]["folder_candidates"])
            self.assertEqual("folder", plan["items"][0]["kind"])
            self.assertTrue(plan["items"][0]["source"].endswith("SmartOrganizer_v1.0"))

    def test_numbered_non_project_folders_are_never_retention_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folders = [self._folder(root / f"Фото v{i}.0", root) for i in range(1, 8)]
            plan = build_version_retention_plan([], folders, keep_latest=5)
            self.assertEqual([], plan["items"])

    def test_generic_release_family_is_rejected_to_avoid_cross_project_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = [self._file(root / f"release_v{i}.0.zip") for i in range(1, 8)]
            plan = build_version_retention_plan(files, [], keep_latest=5)
            self.assertEqual([], plan["items"])
            self.assertGreater(plan["summary"]["generic_families_rejected"], 0)

    def test_quarantine_plan_is_reversible_operations_not_permanent_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = [self._file(root / f"MyTool_v{i}.0.zip") for i in range(1, 7)]
            plan = build_version_retention_plan(files, [], keep_latest=5)
            quarantine = root / "data" / "quarantine" / "versions"
            operations = quarantine_operations(plan, quarantine)
            self.assertTrue(any(op.op_type == "delete-to-quarantine" for op in operations))
            self.assertFalse(any(op.op_type == "delete" for op in operations))


if __name__ == "__main__":
    unittest.main()
