import tempfile
import unittest
from pathlib import Path

from core.database import Database
from core.placement_learning import (
    SETTINGS_KEY,
    apply_confirmed_learning,
    forget_undone_moves,
    learning_summary,
    remember_confirmed_items,
)


class PlacementLearningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = Database(self.root / "knowledge.db")
        self.inbox = self.root / "Inbox"
        self.archives = self.root / "Archives"
        self.other = self.root / "OtherArchives"
        self.inbox.mkdir()
        self.archives.mkdir()
        self.other.mkdir()
        self.folders = [
            {"path": str(self.root), "parent": str(self.root.parent), "name": self.root.name, "depth": 0},
            {"path": str(self.inbox), "parent": str(self.root), "name": "Inbox", "depth": 1},
            {"path": str(self.archives), "parent": str(self.root), "name": "Archives", "depth": 1},
            {"path": str(self.other), "parent": str(self.root), "name": "OtherArchives", "depth": 1},
        ]

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def _item(self, name: str, target_dir: Path, project: str = "") -> dict:
        source = self.inbox / name
        return {
            "kind": "file",
            "source": str(source),
            "target_dir": str(target_dir),
            "target_path": str(target_dir / name),
            "category": "Архивы",
            "extension": ".zip",
            "project_hint": project,
        }

    def _record(self, name: str, project: str = "") -> dict:
        source = self.inbox / name
        return {
            "path": str(source),
            "parent": str(self.inbox),
            "name": name,
            "category": "Архивы",
            "extension": ".zip",
            "project_hint": project,
        }

    def _plan(self, record: dict) -> dict:
        return {
            "items": [
                {
                    "source": record["path"],
                    "target_dir": str(self.other),
                    "target_path": str(self.other / record["name"]),
                    "mode": "proposed",
                    "score": 0,
                    "confidence": "low",
                    "requires_confirmation": True,
                    "reason": "no_confident_user_layout_match_create_only_after_confirmation",
                    "evidence": [],
                    "category": record["category"],
                    "extension": record["extension"],
                    "project_hint": record["project_hint"],
                }
            ],
            "summary": {"files_considered": 1},
        }

    def test_one_confirmation_is_learning_only_not_automatic(self):
        remember_confirmed_items(self.db, [self._item("one.zip", self.archives)])
        record = self._record("new.zip")
        result = apply_confirmed_learning(
            self._plan(record), [record], self.folders, self.db.get_setting(SETTINGS_KEY, []), str(self.root)
        )
        item = result["items"][0]
        self.assertNotEqual("confirmed_local_learning", item["reason"])
        self.assertNotEqual("high", item["confidence"])
        self.assertEqual(1, result["summary"]["pending_learned_rules"])
        self.assertEqual(1, result["summary"]["learned_moves_pending"])

    def test_two_confirmations_create_mature_high_confidence_route(self):
        remember_confirmed_items(
            self.db,
            [self._item("one.zip", self.archives), self._item("two.zip", self.archives)],
        )
        record = self._record("new.zip")
        result = apply_confirmed_learning(
            self._plan(record), [record], self.folders, self.db.get_setting(SETTINGS_KEY, []), str(self.root)
        )
        item = result["items"][0]
        self.assertEqual("confirmed_local_learning", item["reason"])
        self.assertEqual("existing", item["mode"])
        self.assertEqual("high", item["confidence"])
        self.assertFalse(item["requires_confirmation"])
        self.assertEqual(str(self.archives), item["target_dir"])
        self.assertEqual(1, result["summary"]["learned_moves_boosted"])

    def test_equal_mature_destinations_are_blocked_as_ambiguous(self):
        remember_confirmed_items(
            self.db,
            [
                self._item("a1.zip", self.archives),
                self._item("a2.zip", self.archives),
                self._item("b1.zip", self.other),
                self._item("b2.zip", self.other),
            ],
        )
        record = self._record("new.zip")
        result = apply_confirmed_learning(
            self._plan(record), [record], self.folders, self.db.get_setting(SETTINGS_KEY, []), str(self.root)
        )
        item = result["items"][0]
        self.assertEqual("review", item["mode"])
        self.assertEqual("ambiguous", item["confidence"])
        self.assertEqual("conflicting_confirmed_learning", item["reason"])
        self.assertEqual(1, result["summary"]["learned_moves_ambiguous"])

    def test_current_real_layout_evidence_wins_over_history(self):
        remember_confirmed_items(
            self.db,
            [self._item("one.zip", self.archives), self._item("two.zip", self.archives)],
        )
        record = self._record("new.zip")
        plan = self._plan(record)
        plan["items"][0].update(
            target_dir=str(self.other),
            target_path=str(self.other / "new.zip"),
            mode="existing",
            score=180,
            confidence="high",
            requires_confirmation=False,
            reason="user_layout: новая фактическая раскладка",
            evidence=["текущая раскладка пользователя"],
        )
        result = apply_confirmed_learning(
            plan, [record], self.folders, self.db.get_setting(SETTINGS_KEY, []), str(self.root)
        )
        self.assertEqual(str(self.other), result["items"][0]["target_dir"])
        self.assertTrue(result["items"][0]["reason"].startswith("user_layout:"))

    def test_undo_removes_positive_example_and_demotes_rule(self):
        first = self._item("one.zip", self.archives)
        second = self._item("two.zip", self.archives)
        remember_confirmed_items(self.db, [first, second])
        before = learning_summary(self.db.get_setting(SETTINGS_KEY, []))
        self.assertEqual(1, before["mature"])

        removed = forget_undone_moves(
            self.db,
            [{"op_type": "move", "source": second["source"], "target": second["target_path"]}],
        )
        self.assertEqual(1, removed)
        after = learning_summary(self.db.get_setting(SETTINGS_KEY, []))
        self.assertEqual(0, after["mature"])
        self.assertEqual(1, after["learning"])
        self.assertEqual(1, after["confirmations"])

    def test_project_specific_learning_does_not_cross_projects(self):
        remember_confirmed_items(
            self.db,
            [self._item("one.zip", self.archives, "Project-A"), self._item("two.zip", self.archives, "Project-A")],
        )
        record = self._record("new.zip", "Project-B")
        result = apply_confirmed_learning(
            self._plan(record), [record], self.folders, self.db.get_setting(SETTINGS_KEY, []), str(self.root)
        )
        self.assertNotEqual("confirmed_local_learning", result["items"][0]["reason"])
        self.assertEqual(0, result["summary"]["learned_moves_boosted"])


if __name__ == "__main__":
    unittest.main()
