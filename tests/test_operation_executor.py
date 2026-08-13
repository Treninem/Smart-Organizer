import tempfile
import unittest
from pathlib import Path

from core.database import Database
from core.operation_executor import OperationExecutionError, execute_batch, undo_batch
from core.operation_journal import OperationJournal, ReversibleOperation


class OperationExecutorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = Database(self.root / "knowledge.db")
        self.journal = OperationJournal(self.db)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_move_batch_can_be_undone(self):
        src_dir = self.root / "src"
        dst_dir = self.root / "dst"
        src_dir.mkdir()
        dst_dir.mkdir()
        source = src_dir / "document.txt"
        target = dst_dir / "document.txt"
        source.write_text("important", encoding="utf-8")

        batch_id = self.journal.plan_batch([
            ReversibleOperation("move", str(source), str(target), "classification")
        ])
        result = execute_batch(self.journal, batch_id)
        self.assertEqual(result["applied"], 1)
        self.assertFalse(source.exists())
        self.assertEqual(target.read_text(encoding="utf-8"), "important")
        self.assertEqual(self.journal.entries(batch_id)[0]["status"], "applied")

        result = undo_batch(self.journal, batch_id)
        self.assertEqual(result["undone"], 1)
        self.assertTrue(source.exists())
        self.assertFalse(target.exists())
        self.assertEqual(self.journal.entries(batch_id)[0]["status"], "undone")

    def test_existing_target_is_never_overwritten(self):
        src_dir = self.root / "src"
        dst_dir = self.root / "dst"
        src_dir.mkdir()
        dst_dir.mkdir()
        source = src_dir / "same.txt"
        target = dst_dir / "same.txt"
        source.write_text("new", encoding="utf-8")
        target.write_text("old", encoding="utf-8")

        batch_id = self.journal.plan_batch([
            ReversibleOperation("move", str(source), str(target), "collision test")
        ])
        with self.assertRaises(OperationExecutionError):
            execute_batch(self.journal, batch_id)

        self.assertEqual(source.read_text(encoding="utf-8"), "new")
        self.assertEqual(target.read_text(encoding="utf-8"), "old")
        self.assertEqual(self.journal.entries(batch_id)[0]["status"], "failed")

    def test_whole_batch_preflight_prevents_partial_move(self):
        src = self.root / "src"
        dst = self.root / "dst"
        src.mkdir()
        dst.mkdir()
        first = src / "first.txt"
        second = src / "second.txt"
        first.write_text("first", encoding="utf-8")
        second.write_text("second", encoding="utf-8")
        first_target = dst / "first.txt"
        second_target = dst / "second.txt"
        second_target.write_text("occupied", encoding="utf-8")

        batch_id = self.journal.plan_batch([
            ReversibleOperation("move", str(first), str(first_target), "first"),
            ReversibleOperation("move", str(second), str(second_target), "second"),
        ])
        with self.assertRaises(OperationExecutionError):
            execute_batch(self.journal, batch_id)

        self.assertTrue(first.exists(), "first operation must not run before second passes preflight")
        self.assertFalse(first_target.exists())
        self.assertEqual(second_target.read_text(encoding="utf-8"), "occupied")
        statuses = [row["status"] for row in self.journal.entries(batch_id)]
        self.assertEqual(statuses, ["planned", "failed"])

        second_target.unlink()
        with self.assertRaises(OperationExecutionError):
            execute_batch(self.journal, batch_id)
        self.assertTrue(first.exists(), "failed batch must require a fresh plan instead of silent resume")

    def test_undo_refuses_non_empty_created_directory(self):
        folder = self.root / "new-folder"
        batch_id = self.journal.plan_batch([
            ReversibleOperation("mkdir", str(folder), None, "user-approved folder")
        ])
        execute_batch(self.journal, batch_id)
        (folder / "later.txt").write_text("do not delete me", encoding="utf-8")

        with self.assertRaises(OperationExecutionError):
            undo_batch(self.journal, batch_id)
        self.assertTrue((folder / "later.txt").exists())
        self.assertEqual(self.journal.entries(batch_id)[0]["status"], "applied")

    def test_missing_parent_is_not_created_implicitly(self):
        source = self.root / "source.txt"
        source.write_text("x", encoding="utf-8")
        target = self.root / "missing" / "source.txt"
        batch_id = self.journal.plan_batch([
            ReversibleOperation("move", str(source), str(target), "no implicit mkdir")
        ])

        with self.assertRaises(OperationExecutionError):
            execute_batch(self.journal, batch_id)
        self.assertTrue(source.exists())
        self.assertFalse(target.parent.exists())

    def test_reviewed_batch_can_create_quarantine_then_move_and_undo(self):
        source = self.root / "duplicate.bin"
        source.write_bytes(b"same-content")
        quarantine = self.root / "quarantine"
        target = quarantine / "duplicate.bin"
        batch_id = self.journal.plan_batch([
            ReversibleOperation("mkdir", str(quarantine), None, "confirmed quarantine folder"),
            ReversibleOperation("delete-to-quarantine", str(source), str(target), "confirmed exact duplicate"),
        ])

        result = execute_batch(self.journal, batch_id)
        self.assertEqual(2, result["applied"])
        self.assertFalse(source.exists())
        self.assertTrue(target.exists())

        result = undo_batch(self.journal, batch_id)
        self.assertEqual(2, result["undone"])
        self.assertTrue(source.exists())
        self.assertFalse(quarantine.exists())


if __name__ == "__main__":
    unittest.main()
