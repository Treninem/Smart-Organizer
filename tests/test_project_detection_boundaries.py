import unittest
from pathlib import Path

from core.classifier import project_hint


PROJECTS = [
    {"name": "Reader", "aliases": ["Reader App"], "keywords": ["read", "reader"]},
    {"name": "GameProject", "aliases": ["Game Project"], "keywords": ["game", "config file"]},
]


class ProjectDetectionBoundaryTests(unittest.TestCase):
    def test_short_keyword_does_not_match_inside_another_word(self):
        self.assertIsNone(project_hint(Path("D:/Projects/threading/notes.txt"), PROJECTS))

    def test_real_keyword_still_matches(self):
        self.assertEqual("Reader", project_hint(Path("D:/Projects/Reader/notes.txt"), PROJECTS))

    def test_multiword_keyword_matches_normalized_path(self):
        self.assertEqual("GameProject", project_hint(Path("D:/Game/config-file.txt"), PROJECTS))


if __name__ == "__main__":
    unittest.main()
