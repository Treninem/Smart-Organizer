import unittest

from core.local_ai import analyze_local_snapshot


class LocalAiTests(unittest.TestCase):
    def test_overview_marks_old_versions_and_never_deletes_without_sha256(self):
        records = [
            {
                "name": "VoxLyra_v1.0.zip",
                "path": r"D:\Work\VoxLyra_v1.0.zip",
                "size": 100,
                "category": "archive",
                "project_hint": "VoxLyra",
            },
            {
                "name": "VoxLyra_v2.0.zip",
                "path": r"D:\Work\VoxLyra_v2.0.zip",
                "size": 120,
                "category": "archive",
                "project_hint": "VoxLyra",
            },
            {
                "name": "notes.txt",
                "path": r"D:\Work\notes.txt",
                "size": 10,
                "category": "document",
                "project_hint": None,
            },
        ]
        report = analyze_local_snapshot(records)
        summary = report["summary"]
        self.assertEqual(3, summary["files"])
        self.assertEqual(1, summary["old_version_candidates"])
        self.assertEqual(1, summary["newest_versions"])
        self.assertEqual(0, summary["delete_without_sha256"])


if __name__ == "__main__":
    unittest.main()
