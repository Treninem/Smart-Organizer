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
        self.assertEqual("Treninem/Voxlyra", self.projects["VoxLyra"]["repository"])
        self.assertEqual("Treninem/ImPuls-Minecraft", self.projects["ImPuls-Minecraft"]["repository"])
        self.assertEqual("Treninem/Impuls", self.projects["ImPuls"]["repository"])
        self.assertEqual("Treninem/Proizvodstvo", self.projects["ProControl"]["repository"])
        self.assertEqual("Treninem/Smart-Organizer", self.projects["Smart-Organizer"]["repository"])
        self.assertEqual("Treninem/game", self.projects["Treninem-Game"]["repository"])

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
            "Single-player RPG / Survival Game",
            "Technical PDF Translation",
            "Comic / Manga Localization Package",
        ):
            self.assertIn(name, names)
        self.assertGreaterEqual(len(names), 22)


if __name__ == "__main__":
    unittest.main()
