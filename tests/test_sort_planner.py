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
        result = build_sort_plan(files, folders, [], "D:\\")
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
        result = build_sort_plan(files, folders, [], "D:\\")
        self.assertEqual(result["items"], [])
        self.assertEqual(result["summary"]["already_placed"], 1)

    def test_generic_src_folder_in_another_project_is_never_selected(self):
        files = [{
            "path": r"D:\Work\Project-A\main.py",
            "parent": r"D:\Work\Project-A",
            "name": "main.py",
            "category": "Код",
            "project_hint": None,
        }]
        folders = [
            {"path": r"D:\Work\Project-A", "name": "Project-A", "depth": 1},
            {"path": r"D:\Work\Project-B\src", "name": "src", "depth": 2},
        ]
        result = build_sort_plan(files, folders, [], r"D:\Work")
        self.assertEqual(result["items"], [])
        self.assertEqual(result["summary"]["already_placed"], 1)

    def test_existing_project_internals_are_not_rearranged(self):
        files = [{
            "path": r"D:\Work\Project-A\main.py",
            "parent": r"D:\Work\Project-A",
            "name": "main.py",
            "category": "Код",
            "project_hint": None,
        }]
        folders = [
            {"path": r"D:\Work\Project-A", "name": "Project-A", "depth": 1},
            {"path": r"D:\Work\Project-A\src", "name": "src", "depth": 2},
        ]
        result = build_sort_plan(files, folders, [], r"D:\Work")
        self.assertEqual(result["items"], [])
        self.assertEqual(result["summary"]["already_placed"], 1)

    def test_selected_project_root_with_main_py_is_frozen(self):
        files = [
            {
                "path": r"D:\Project-A\main.py",
                "parent": r"D:\Project-A",
                "name": "main.py",
                "category": "Код",
                "project_hint": None,
            },
            {
                "path": r"D:\Project-A\logo.png",
                "parent": r"D:\Project-A",
                "name": "logo.png",
                "category": "Изображения",
                "project_hint": None,
            },
        ]
        folders = [
            {"path": r"D:\Project-A", "name": "Project-A", "depth": 0},
            {"path": r"D:\Project-A\src", "name": "src", "depth": 1},
            {"path": r"D:\Project-A\images", "name": "images", "depth": 1},
        ]
        result = build_sort_plan(files, folders, [], r"D:\Project-A")
        self.assertEqual(result["items"], [])
        self.assertEqual(result["summary"]["protected_project_root"], 1)
        self.assertEqual(result["summary"]["already_placed"], 2)


if __name__ == "__main__":
    unittest.main()
