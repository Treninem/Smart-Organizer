from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core.database import Database
from core.defender_report import parse_defender_json, report_text
from core.desktop_shortcuts import parse_shortcut_rules, plan_shortcut_sort, FOLDER
from core.operation_executor import execute_batch, undo_batch
from core.operation_journal import OperationJournal


class DefenderReportTests(unittest.TestCase):
    def test_empty_results_normalized(self):
        report = parse_defender_json('{"status":{"AntivirusEnabled":true},"threats":null}')
        self.assertEqual(report["status"]["AntivirusEnabled"], True)
        self.assertEqual(report["threats"], [])
        self.assertIn("Microsoft Defender", report_text(report))

    def test_single_detection_remains_one_report(self):
        report = parse_defender_json(json.dumps({
            "status": {"AntivirusEnabled": True, "RealTimeProtectionEnabled": False},
            "threats": {"ThreatID": 1234, "ThreatName": "PUA:Test", "ActionSuccess": True,
                        "Resources": ["file:_C:\\Temp\\unwanted.exe"]},
        }))
        self.assertEqual(len(report["threats"]), 1)
        self.assertIn("PUA:Test", report_text(report))
        self.assertIn("НЕТ", report_text(report))

    def test_invalid_report_does_not_invent_detections(self):
        with self.assertRaises(ValueError):
            parse_defender_json("[]")


class ShortcutRulesTests(unittest.TestCase):
    def test_rules_restrict_destinations(self):
        self.assertEqual(parse_shortcut_rules(
            "Steam=Игры; Chrome=Программы; Steam=Игры"
        ), [("steam", "Игры"), ("chrome", "Программы")])
        for value in ("foo=Folder", "foo=../../outside", "foo", "=Игры",
                      "C:\\Windows=Программы"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_shortcut_rules(value)

    def test_shortcuts_only_and_ambiguous_are_not_moved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in (
                "Steam.lnk", "Chrome.url", "both Steam Chrome.url", "photo.jpg",
                "game.exe", "desktop.ini", "Unknown.lnk",
            ):
                (root / name).write_text("source", encoding="utf-8")
            (root / "Steam.url").mkdir()
            plan = plan_shortcut_sort(root, parse_shortcut_rules(
                "Steam=Игры; Chrome=Программы"
            ))
            self.assertEqual(
                {item["name"] for item in plan["matches"]}, {"Steam.lnk", "Chrome.url"}
            )
            self.assertEqual(plan["ambiguous"], ["both Steam Chrome.url"])
            self.assertEqual(plan["untouched"], 1)
            self.assertTrue(all(
                item["target"].startswith(str(root / FOLDER))
                for item in plan["matches"]
            ))
            self.assertTrue((root / "game.exe").exists())
            self.assertEqual(len(list(root.iterdir())), 8)

    def test_move_and_undo_through_existing_app_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "Desktop"
            root.mkdir()
            original = root / "Steam.url"
            original.write_text("[InternetShortcut]\nURL=https://example.com\n", encoding="utf-8")
            plan = plan_shortcut_sort(root, parse_shortcut_rules("Steam=Игры"))
            db = Database(Path(tmp) / "knowledge.db")
            try:
                journal = OperationJournal(db)
                bid = journal.plan_batch(plan["operations"], label="desktop-shortcuts")
                changed = execute_batch(journal, bid)
                self.assertEqual(changed["applied"], 3)
                moved = root / FOLDER / "Игры" / "Steam.url"
                self.assertTrue(moved.exists())
                self.assertFalse(original.exists())
                restored = undo_batch(journal, bid)
                self.assertEqual(restored["undone"], 3)
                self.assertTrue(original.exists())
                self.assertFalse((root / FOLDER).exists())
            finally:
                db.close()

    def test_target_collision_blocks_without_overwriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "Steam.lnk"
            original.write_text("original", encoding="utf-8")
            dest = root / FOLDER / "Игры"
            dest.mkdir(parents=True)
            (dest / "Steam.lnk").write_text("keep", encoding="utf-8")
            plan = plan_shortcut_sort(root, parse_shortcut_rules("Steam=Игры"))
            self.assertEqual(plan["matches"], [])
            self.assertEqual(len(plan["ambiguous"]), 1)
            self.assertEqual(original.read_text(), "original")
            self.assertEqual((dest / "Steam.lnk").read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
