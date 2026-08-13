import tempfile
import unittest
from pathlib import Path

from core.database import Database
from core.undo_feedback import SETTINGS_KEY, apply_undo_feedback, remember_undone_moves


class UndoFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name) / "knowledge.db")

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_undo_remembers_only_exact_source_target_pair(self):
        entries = [
            {
                "op_type": "move",
                "source": r"D:\Desk\release.zip",
                "target": r"D:\Desk\Archives\release.zip",
            }
        ]
        self.assertEqual(1, remember_undone_moves(self.db, entries))
        self.assertEqual(0, remember_undone_moves(self.db, entries))
        rules = self.db.get_setting(SETTINGS_KEY, [])
        self.assertEqual(1, len(rules))

        plan = {
            "items": [
                {
                    "source": r"D:\Desk\release.zip",
                    "target_path": r"D:\Desk\Archives\release.zip",
                    "mode": "existing",
                    "confidence": "high",
                    "requires_confirmation": False,
                    "allow_confirmed_creation": True,
                },
                {
                    "source": r"D:\Desk\other.zip",
                    "target_path": r"D:\Desk\Archives\other.zip",
                    "mode": "existing",
                    "confidence": "high",
                    "requires_confirmation": False,
                },
            ],
            "summary": {},
        }
        filtered = apply_undo_feedback(plan, rules)
        self.assertEqual("review", filtered["items"][0]["mode"])
        self.assertEqual("rejected", filtered["items"][0]["confidence"])
        self.assertNotIn("allow_confirmed_creation", filtered["items"][0])
        self.assertEqual("existing", filtered["items"][1]["mode"])
        self.assertEqual(1, filtered["summary"]["blocked_by_undo_memory"])

    def test_quarantine_undo_does_not_poison_normal_layout(self):
        entries = [
            {
                "op_type": "delete-to-quarantine",
                "source": r"D:\Desk\copy.bin",
                "target": r"D:\Smart-Organizer\data\quarantine\copy.bin",
            }
        ]
        self.assertEqual(0, remember_undone_moves(self.db, entries))
        self.assertEqual([], self.db.get_setting(SETTINGS_KEY, []))


if __name__ == "__main__":
    unittest.main()
