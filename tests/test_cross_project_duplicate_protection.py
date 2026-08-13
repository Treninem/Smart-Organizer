import tempfile
import unittest
from pathlib import Path

from core.duplicate_insights import duplicate_candidate_groups
from core.duplicates import exact_duplicate_groups


class CrossProjectDuplicateProtectionTests(unittest.TestCase):
    def _record(self, path: Path, project_hint=None) -> dict:
        stat = path.stat()
        return {
            "path": str(path),
            "parent": str(path.parent),
            "name": path.name,
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "project_hint": project_hint,
        }

    def test_identical_main_py_in_two_projects_is_not_a_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_a = root / "Project-A"
            project_b = root / "Project-B"
            project_a.mkdir()
            project_b.mkdir()
            a = project_a / "main.py"
            b = project_b / "main.py"
            a.write_text("print('shared bootstrap')\n", encoding="utf-8")
            b.write_text("print('shared bootstrap')\n", encoding="utf-8")

            records = [self._record(a, "Project-A"), self._record(b, "Project-B")]
            self.assertEqual([], exact_duplicate_groups(records, str(root)))

    def test_identical_arbitrary_files_in_different_project_trees_are_protected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_a = root / "Alpha"
            project_b = root / "Beta"
            project_a.mkdir()
            project_b.mkdir()
            a = project_a / "settings.json"
            b = project_b / "config-copy.json"
            a.write_bytes(b'{"enabled":true}')
            b.write_bytes(b'{"enabled":true}')

            # Even without a recognized project hint, sibling project trees are
            # separate safety scopes under the scanned root.
            records = [self._record(a), self._record(b)]
            self.assertEqual([], exact_duplicate_groups(records, str(root)))

    def test_same_name_and_size_across_projects_are_not_even_duplicate_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_a = root / "One"
            project_b = root / "Two"
            project_a.mkdir()
            project_b.mkdir()
            a = project_a / "main.py"
            b = project_b / "main.py"
            a.write_bytes(b"abc")
            b.write_bytes(b"abc")
            records = [self._record(a), self._record(b)]

            report = duplicate_candidate_groups(records, scan_root=str(root))
            self.assertEqual(0, report["summary"]["same_name_groups"])
            self.assertEqual(0, report["summary"]["same_size_groups"])

    def test_real_copy_inside_one_project_scope_is_still_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "Project-A"
            project.mkdir()
            a = project / "report.txt"
            b = project / "report (1).txt"
            a.write_bytes(b"same")
            b.write_bytes(b"same")
            records = [self._record(a, "Project-A"), self._record(b, "Project-A")]

            groups = exact_duplicate_groups(records, str(root))
            self.assertEqual(1, len(groups))
            self.assertEqual(str(a), groups[0]["canonical"])
            self.assertEqual([str(b)], groups[0]["duplicates"])


if __name__ == "__main__":
    unittest.main()
