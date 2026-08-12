import unittest

from core.sort_planner import build_sort_plan


class SortPlannerTests(unittest.TestCase):
    def test_existing_structure_is_preferred_without_confirmation(self):
        files = [{
            "path": r"D:\Inbox\photo.jpg",
            "parent": r"D:\Inbox",
            "name": "photo.jpg",
            "category": "Изображения",
            "project_hint": None,
        }]
        folders = [
            {"path": r"D:\Inbox", "name": "Inbox", "depth": 1},
            {"path": r"D:\Images", "name": "Images", "depth": 1},
        ]
        result = build_sort_plan(files, folders, [], r"D:\")
        self.assertTrue(result["safe_mode"])
        self.assertEqual(result["summary"]["filesystem_changes_performed"], 0)
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["target_dir"], r"D:\Images")
        self.assertFalse(result["items"][0]["requires_confirmation"])

    def test_new_folder_requires_confirmation(self):
        files = [{
            "path": r"D:\Inbox\unknown.bin",
            "parent": r"D:\Inbox",
            "name": "unknown.bin",
            "category": "Прочее",
            "project_hint": None,
        }]
        folders = [{"path": r"D:\Inbox", "name": "Inbox", "depth": 1}]
        result = build_sort_plan(files, folders, [], r"D:\Work")
        self.assertEqual(len(result["items"]), 1)
        self.assertTrue(result["items"][0]["requires_confirmation"])
        self.assertEqual(result["items"][0]["mode"], "proposed")
        self.assertEqual(result["summary"]["new_folder_targets"], 1)

    def test_already_placed_file_is_not_suggested(self):
        files = [{
            "path": r"D:\Images\photo.jpg",
            "parent": r"D:\Images",
            "name": "photo.jpg",
            "category": "Изображения",
            "project_hint": None,
        }]
        folders = [{"path": r"D:\Images", "name": "Images", "depth": 1}]
        result = build_sort_plan(files, folders, [], r"D:\")
        self.assertEqual(result["items"], [])
        self.assertEqual(result["summary"]["already_placed"], 1)


if __name__ == "__main__":
    unittest.main()
