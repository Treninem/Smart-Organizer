import json
import unittest
from pathlib import Path

from core.knowledge import knowledge_items
from core.project_templates import detect_template, summarize_template_matches


class ProjectTemplateTests(unittest.TestCase):
    def setUp(self):
        self.knowledge = json.loads(Path("config/initial_knowledge.json").read_text(encoding="utf-8"))
        self.templates = self.knowledge["templates"]

    def test_templates_are_seeded_into_local_knowledge(self):
        items = knowledge_items(self.knowledge)
        template_items = [item for item in items if item["kind"] == "template"]
        self.assertGreaterEqual(len(template_items), 6)

    def test_minecraft_and_web_templates_are_detected(self):
        minecraft = {"path": r"D:\Servers\ImPuls\world\datapacks\core.zip", "name": "core.zip"}
        website = {"path": r"D:\Sites\portal\src\index.html", "name": "index.html"}
        self.assertEqual("Minecraft Server", detect_template(minecraft, self.templates))
        self.assertEqual("Website", detect_template(website, self.templates))

    def test_template_summary_counts_matches(self):
        records = [
            {"path": r"D:\Game\Assets\Scenes\menu.tscn", "name": "menu.tscn"},
            {"path": r"D:\CAD\Models\part.step", "name": "part.step"},
        ]
        summary = dict(summarize_template_matches(records, self.templates))
        self.assertGreaterEqual(summary.get("Game Project", 0), 1)
        self.assertGreaterEqual(summary.get("Drawings / CAD", 0), 1)


if __name__ == "__main__":
    unittest.main()
