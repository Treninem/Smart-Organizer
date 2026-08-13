import unittest

from core.duplicate_insights import duplicate_candidate_groups, normalized_duplicate_name


class DuplicateInsightTests(unittest.TestCase):
    def test_copy_suffixes_normalize_without_claiming_exact_match(self):
        self.assertEqual("photo.jpg", normalized_duplicate_name("Photo (1).JPG"))
        self.assertEqual("report.pdf", normalized_duplicate_name("report - copy.pdf"))

    def test_name_and_size_candidates_are_reported_separately(self):
        records = [
            {"name": "photo.jpg", "path": r"D:\A\photo.jpg", "size": 10},
            {"name": "photo (1).jpg", "path": r"D:\B\photo (1).jpg", "size": 11},
            {"name": "other.bin", "path": r"D:\C\other.bin", "size": 10},
        ]
        report = duplicate_candidate_groups(records)
        self.assertEqual(1, report["summary"]["same_name_groups"])
        self.assertEqual(1, report["summary"]["same_size_groups"])
        self.assertEqual(2, report["name_groups"][0]["count"])
        self.assertEqual(10, report["size_groups"][0]["size"])


if __name__ == "__main__":
    unittest.main()
