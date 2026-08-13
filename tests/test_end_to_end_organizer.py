import tempfile
import unittest
from pathlib import Path

from core.database import Database
from core.duplicates import exact_duplicate_groups
from core.operation_executor import execute_batch, undo_batch
from core.operation_journal import OperationJournal
from core.plan_bridge import operations_from_confirmed_sort_plan
from core.scanner import scan_tree
from core.sort_planner import build_sort_plan


class EndToEndOrganizerTests(unittest.TestCase):
    def test_existing_folder_move_really_executes_and_undo_restores(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inbox = root / "Inbox"
            images = root / "Images"
            inbox.mkdir()
            images.mkdir()
            source = inbox / "holiday.jpg"
            source.write_bytes(b"image-data")

            scan = scan_tree(root, [])
            plan = build_sort_plan(scan.files, scan.folders, [], str(root))
            self.assertEqual(1, plan["summary"]["moves_suggested"])
            self.assertEqual(str(images / "holiday.jpg"), plan["items"][0]["target_path"])

            operations = operations_from_confirmed_sort_plan(plan)
            db = Database(root / "knowledge.db")
            journal = OperationJournal(db)
            try:
                batch = journal.plan_batch(operations, label="e2e-existing-folder")
                result = execute_batch(journal, batch)
                self.assertEqual(1, result["applied"])
                self.assertFalse(source.exists())
                self.assertTrue((images / "holiday.jpg").exists())

                undone = undo_batch(journal, batch)
                self.assertEqual(1, undone["undone"])
                self.assertTrue(source.exists())
                self.assertFalse((images / "holiday.jpg").exists())
            finally:
                db.close()

    def test_new_nested_folders_execute_and_undo_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inbox = root / "Inbox"
            inbox.mkdir()
            source = inbox / "manual.pdf"
            source.write_bytes(b"pdf-data")

            scan = scan_tree(root, [])
            plan = build_sort_plan(scan.files, scan.folders, [], str(root))
            self.assertEqual(1, plan["summary"]["new_folder_targets"])
            target = Path(plan["items"][0]["target_path"])
            self.assertFalse(target.parent.exists())

            operations = operations_from_confirmed_sort_plan(plan)
            self.assertGreaterEqual(sum(op.op_type == "mkdir" for op in operations), 2)

            db = Database(root / "knowledge.db")
            journal = OperationJournal(db)
            try:
                batch = journal.plan_batch(operations, label="e2e-new-folders")
                execute_batch(journal, batch)
                self.assertTrue(target.exists())
                self.assertFalse(source.exists())

                undo_batch(journal, batch)
                self.assertTrue(source.exists())
                self.assertFalse(target.exists())
                self.assertFalse(root.joinpath("Smart-Organizer_Unsorted").exists())
            finally:
                db.close()

    def test_two_projects_with_identical_main_py_remain_independent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_a = root / "Project-A"
            project_b = root / "Project-B"
            project_a.mkdir()
            project_b.mkdir()
            a = project_a / "main.py"
            b = project_b / "main.py"
            a.write_text("print('same')\n", encoding="utf-8")
            b.write_text("print('same')\n", encoding="utf-8")

            scan = scan_tree(root, [])
            plan = build_sort_plan(scan.files, scan.folders, [], str(root))
            self.assertEqual([], plan["items"])
            self.assertTrue(a.exists())
            self.assertTrue(b.exists())

            groups = exact_duplicate_groups(scan.files, str(root))
            self.assertEqual([], groups)
            self.assertTrue(a.exists())
            self.assertTrue(b.exists())


if __name__ == "__main__":
    unittest.main()
