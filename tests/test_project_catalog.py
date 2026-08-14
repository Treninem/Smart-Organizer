import json
import unittest
from pathlib import Path


class ProjectCatalogTests(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads(Path("config/initial_knowledge.json").read_text(encoding="utf-8"))
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
        }
        self.assertTrue(expected.issubset(self.projects))

    def test_known_repositories_are_not_mixed(self):
        self.assertEqual("Treninem/Voxlyra", self.projects["VoxLyra"]["repository"])
        self.assertEqual("Treninem/ImPuls-Minecraft", self.projects["ImPuls-Minecraft"]["repository"])
        self.assertEqual("Treninem/Impuls", self.projects["ImPuls"]["repository"])
        self.assertEqual("Treninem/Proizvodstvo", self.projects["ProControl"]["repository"])
        self.assertEqual("Treninem/Smart-Organizer", self.projects["Smart-Organizer"]["repository"])

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
        ):
            self.assertIn(name, names)
        self.assertGreaterEqual(len(names), 18)


if __name__ == "__main__":
    unittest.main()
