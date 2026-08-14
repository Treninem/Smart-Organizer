import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from core.background_engine import (
    POWER_SETTINGS_KEY,
    apply_corrections,
    choose_configured_target,
    normalized_power_settings,
)
from core.database import Database
from core.operation_executor import execute_batch
from core.operation_journal import OperationJournal, ReversibleOperation


class BackgroundEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = Database(self.root / "knowledge.db")
        self.projects = json.loads(Path("config/initial_knowledge.json").read_text(encoding="utf-8"))["projects"]

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_project_route_wins_over_general_archive_route(self):
        project_dir = self.root / "VoxLyra"
        archive_dir = self.root / "Archives"
        project_dir.mkdir()
        archive_dir.mkdir()
        source = self.root / "VoxLyra_v1.16.2.zip"
        source.write_bytes(b"x")
        settings = normalized_power_settings({
            "project_routes": {"VoxLyra": str(project_dir)},
            "routes": {"Архивы": str(archive_dir)},
        })
        decision = choose_configured_target(source, settings, [], self.projects)
        self.assertIsNotNone(decision)
        self.assertEqual(str(project_dir), decision["target_dir"])
        self.assertEqual("explicit-project-route:VoxLyra", decision["reason"])

    def test_chatgpt_route_separates_explicitly_named_file(self):
        ai_dir = self.root / "ChatGPT"
        image_dir = self.root / "Images"
        ai_dir.mkdir()
        image_dir.mkdir()
        source = self.root / "ChatGPT Image 2026.png"
        source.write_bytes(b"png")
        settings = normalized_power_settings({
            "chatgpt_target": str(ai_dir),
            "routes": {"Изображения": str(image_dir)},
            "separate_chatgpt": True,
        })
        decision = choose_configured_target(source, settings, [], self.projects)
        self.assertEqual(str(ai_dir), decision["target_dir"])
        self.assertEqual("explicit-chatgpt-route", decision["reason"])

    def test_existing_target_collision_blocks_background_move(self):
        target = self.root / "Docs"
        target.mkdir()
        source = self.root / "notes.txt"
        source.write_text("new", encoding="utf-8")
        (target / "notes.txt").write_text("old", encoding="utf-8")
        settings = normalized_power_settings({"routes": {"Документы": str(target)}})
        self.assertIsNone(choose_configured_target(source, settings, [], self.projects))
        self.assertEqual("old", (target / "notes.txt").read_text(encoding="utf-8"))

    def test_self_correction_moves_only_previous_applied_journal_target(self):
        downloads = self.root / "Downloads"
        wrong = self.root / "Wrong"
        right = self.root / "Right"
        downloads.mkdir()
        wrong.mkdir()
        right.mkdir()
        source = downloads / "notes.txt"
        source.write_text("important", encoding="utf-8")
        wrong_target = wrong / source.name

        journal = OperationJournal(self.db)
        batch = journal.plan_batch([ReversibleOperation("move", str(source), str(wrong_target), "old wrong decision")])
        execute_batch(journal, batch)
        self.assertTrue(wrong_target.exists())

        self.db.set_setting(
            POWER_SETTINGS_KEY,
            normalized_power_settings({
                "routes": {"Документы": str(right)},
                "auto_correct_own_moves": True,
            }),
        )
        result = apply_corrections(self.db, self.projects)
        corrected = right / "notes.txt"
        self.assertEqual(1, result["corrected"])
        self.assertTrue(corrected.exists())
        self.assertFalse(wrong_target.exists())
        self.assertEqual("important", corrected.read_text(encoding="utf-8"))

    def test_self_correction_does_not_sweep_arbitrary_file(self):
        wrong = self.root / "Wrong"
        right = self.root / "Right"
        wrong.mkdir()
        right.mkdir()
        arbitrary = wrong / "notes.txt"
        arbitrary.write_text("user file", encoding="utf-8")
        self.db.set_setting(
            POWER_SETTINGS_KEY,
            normalized_power_settings({
                "routes": {"Документы": str(right)},
                "auto_correct_own_moves": True,
            }),
        )
        result = apply_corrections(self.db, self.projects)
        self.assertEqual(0, result["corrected"])
        self.assertTrue(arbitrary.exists())
        self.assertFalse((right / "notes.txt").exists())


if __name__ == "__main__":
    unittest.main()
