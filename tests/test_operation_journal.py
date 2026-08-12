import tempfile
import unittest
from pathlib import Path

from core.database import Database
from core.operation_journal import (
    OperationJournal,
    ReversibleOperation,
    validate_no_destructive_conflicts,
)


class OperationJournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name) / "knowledge.db")
        self.journal = OperationJournal(self.db)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_planning_is_persistent_and_does_not_touch_filesystem(self):
        source = Path(self.temp.name) / "source.txt"
        target = Path(self.temp.name) / "Existing" / "source.txt"
        source.write_text("keep", encoding="utf-8")

        batch = self.journal.plan_batch(
            [ReversibleOperation("move", str(source), str(target), "better existing folder")],
            label="preview",
        )

        self.assertTrue(source.exists())
        self.assertFalse(target.exists())
        rows = self.journal.entries(batch)
        self.assertEqual(1, len(rows))
        self.assertEqual("planned", rows[0]["status"])
        self.assertEqual(str(source), rows[0]["source"])
        self.assertEqual(str(target), rows[0]["target"])

    def test_applied_move_produces_reverse_undo_plan(self):
        operation = ReversibleOperation("move", r"D:\Inbox\book.pdf", r"D:\Books\book.pdf", "classified")
        batch = self.journal.plan_batch([operation])
        row = self.journal.entries(batch)[0]
        self.journal.mark_applied(row["id"], {"verified": True})

        undo = self.journal.undo_plan(batch)
        self.assertEqual(1, len(undo))
        self.assertEqual("move", undo[0].op_type)
        self.assertEqual(r"D:\Books\book.pdf", undo[0].source)
        self.assertEqual(r"D:\Inbox\book.pdf", undo[0].target)

    def test_conflicts_are_rejected_before_execution(self):
        with self.assertRaises(ValueError):
            validate_no_destructive_conflicts(
                [
                    ReversibleOperation("move", r"D:\A\x.txt", r"D:\B\x.txt"),
                    ReversibleOperation("move", r"D:\C\x.txt", r"D:\B\x.txt"),
                ]
            )

        with self.assertRaises(ValueError):
            validate_no_destructive_conflicts(
                [ReversibleOperation("rename", r"D:\A\x.txt", r"d:/a/x.txt")]
            )

    def test_invalid_status_does_not_modify_entry(self):
        batch = self.journal.plan_batch([ReversibleOperation("mkdir", r"D:\NewFolder")])
        row = self.journal.entries(batch)[0]
        with self.assertRaises(ValueError):
            self.db.set_operation_status(row["id"], "deleted")
        self.assertEqual("planned", self.journal.entries(batch)[0]["status"])


if __name__ == "__main__":
    unittest.main()
