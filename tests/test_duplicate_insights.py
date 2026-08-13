import unittest

from core.duplicate_insights import duplicate_candidate_groups, normalized_duplicate_name


class DuplicateInsightTests(unittest.TestCase):
    def test_copy_suffixes_normalize_without_claiming_exact_match(self):
        self.assertEqual("photo.jpg", normalized_duplicate_name("Photo (1).JPG"))
        self.assertEqual("report.pdf", normalized_duplicate_name("report - copy.pdf"))

    def test_name_and_size_candidates_are_reported_inside_one_scope(self):
        records = [
            {"name": "photo.jpg", "path": r"D:\Project\photo.jpg", "size": 10},
            {"name": "photo (1).jpg", "path": r"D:\Project\photo (1).jpg", "size": 11},
            {"name": "other.bin", "path": r"D:\Project\other.bin", "size": 10},
        ]
        report = duplicate_candidate_groups(records)
        self.assertEqual(1, report["summary"]["same_name_groups"])
        self.assertEqual(1, report["summary"]["same_size_groups"])
        self.assertEqual(2, report["name_groups"][0]["count"])
        self.assertEqual(10, report["size_groups"][0]["size"])

    def test_same_name_in_different_scopes_is_not_a_candidate(self):
        records = [
            {"name": "main.py", "path": r"D:\Project-A\main.py", "size": 10},
            {"name": "main.py", "path": r"D:\Project-B\main.py", "size": 10},
        ]
        report = duplicate_candidate_groups(records)
        self.assertEqual(0, report["summary"]["same_name_groups"])
        self.assertEqual(0, report["summary"]["same_size_groups"])


if __name__ == "__main__":
    unittest.main()
