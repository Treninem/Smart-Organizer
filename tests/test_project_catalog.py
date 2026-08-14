import unittest
from pathlib import Path

from core.knowledge import load_initial_knowledge


class ProjectCatalogTests(unittest.TestCase):
    def setUp(self):
        self.payload = load_initial_knowledge(Path("config/initial_knowledge.json"))
        self.projects = {item["name"]: item for item in self.payload["projects"]}

    def test_known_user_projects_are_separate_entries(self):
        expected = {
            "VoxLyra",
            "BookVoxLyra",
            "Boostora",
            "ImPuls-Minecraft",
            "ImPuls",
            "ProControl",
            "Smart-Organizer",
            "Zveroboy",
            "LoveMi",
            "Pubgbot",
            "Open-World-Survival-Game",
            "Extrusion-Calibrator",
            "Treninem-Game",
            "Documentation-Translation",
            "Personal-Website",
        }
        self.assertTrue(expected.issubset(self.projects))
        self.assertEqual(len(self.projects), len(self.payload["projects"]))

    def test_known_repositories_are_not_mixed(self):
        expected = {
            "VoxLyra": "Treninem/Voxlyra",
            "BookVoxLyra": "Treninem/bookvoxlyra",
            "Boostora": "Treninem/Boostora",
            "ImPuls-Minecraft": "Treninem/ImPuls-Minecraft",
            "ImPuls": "Treninem/Impuls",
            "ProControl": "Treninem/Proizvodstvo",
            "Smart-Organizer": "Treninem/Smart-Organizer",
            "Zveroboy": "Treninem/Zveroboy",
            "LoveMi": "Treninem/LoveMi",
            "Pubgbot": "Treninem/Pubgbot",
            "Treninem-Game": "Treninem/game",
        }
        for project, repository in expected.items():
            self.assertEqual(repository, self.projects[project]["repository"], project)
        self.assertEqual(len(expected.values()), len(set(expected.values())))

    def test_bookvoxlyra_is_separate_from_voxlyra_runtime(self):
        self.assertNotEqual(self.projects["BookVoxLyra"]["repository"], self.projects["VoxLyra"]["repository"])
        self.assertIn("import", self.projects["BookVoxLyra"]["type"].casefold())

    def test_template_catalog_is_broad(self):
        names = {item["name"] for item in self.payload["templates"]}
        for name in (
            "Telegram / VK Mini App",
            "Minecraft Server",
            "Minecraft Datapack",
            "Game Project",
            "Website",
            "Production System",
            "Library / Reader Platform",
            "Drawings / CAD",
            "Comics Import Package",
            "Windows Runtime Release",
            "VoxLyra Source Import Repository",
            "Single-player RPG / Survival Game",
            "Technical PDF Translation",
            "Comic / Manga Localization Package",
        ):
            self.assertIn(name, names)
        self.assertGreaterEqual(len(names), 23)


if __name__ == "__main__":
    unittest.main()
