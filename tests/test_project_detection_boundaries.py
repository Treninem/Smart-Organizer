import unittest
from pathlib import Path

from core.classifier import category_for, project_hint


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

    def test_equal_project_scores_are_ambiguous_not_arbitrarily_selected(self):
        projects = [
            {"name": "AlphaBot", "aliases": [], "keywords": ["bot"]},
            {"name": "BetaBot", "aliases": [], "keywords": ["bot"]},
        ]
        self.assertIsNone(project_hint(Path("D:/Desktop/bot/export.zip"), projects))

    def test_extended_local_formats_are_classified(self):
        self.assertEqual("Архивы", category_for(Path("comic.cbz")))
        self.assertEqual("Документы", category_for(Path("book.epub")))
        self.assertEqual("Чертежи", category_for(Path("scene.blend")))
        self.assertEqual("Программы", category_for(Path("client.apk")))


if __name__ == "__main__":
    unittest.main()
