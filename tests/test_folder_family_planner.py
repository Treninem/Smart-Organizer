import unittest

from core.folder_family_planner import build_folder_family_plan


class FolderFamilyPlannerTests(unittest.TestCase):
    def test_three_version_folders_form_confirmed_family(self):
        folders = [
            {"path": r"D:\Desk", "parent": "", "name": "Desk", "depth": 0},
            {"path": r"D:\Desk\Tool_v1.0", "parent": r"D:\Desk", "name": "Tool_v1.0", "depth": 1},
            {"path": r"D:\Desk\Tool_v1.1", "parent": r"D:\Desk", "name": "Tool_v1.1", "depth": 1},
            {"path": r"D:\Desk\Tool_v2.0", "parent": r"D:\Desk", "name": "Tool_v2.0", "depth": 1},
        ]
        result = build_folder_family_plan(folders, r"D:\Desk")
        self.assertEqual(1, result["summary"]["families"])
        self.assertEqual(3, result["summary"]["folder_moves"])
        self.assertEqual(1, result["summary"]["new_containers"])
        self.assertTrue(all(item["allow_confirmed_creation"] for item in result["items"]))
        self.assertTrue(all(item["mode"] == "family_proposed" for item in result["items"]))

    def test_two_versions_are_not_enough_to_restructure(self):
        folders = [
            {"path": r"D:\Desk", "parent": "", "name": "Desk", "depth": 0},
            {"path": r"D:\Desk\Tool_v1.0", "parent": r"D:\Desk", "name": "Tool_v1.0", "depth": 1},
            {"path": r"D:\Desk\Tool_v2.0", "parent": r"D:\Desk", "name": "Tool_v2.0", "depth": 1},
        ]
        result = build_folder_family_plan(folders, r"D:\Desk")
        self.assertEqual([], result["items"])

    def test_project_root_disables_family_grouping(self):
        folders = [
            {"path": r"D:\Project", "parent": "", "name": "Project", "depth": 0},
            {"path": r"D:\Project\Asset_v1.0", "parent": r"D:\Project", "name": "Asset_v1.0", "depth": 1},
            {"path": r"D:\Project\Asset_v1.1", "parent": r"D:\Project", "name": "Asset_v1.1", "depth": 1},
            {"path": r"D:\Project\Asset_v1.2", "parent": r"D:\Project", "name": "Asset_v1.2", "depth": 1},
        ]
        result = build_folder_family_plan(folders, r"D:\Project", protected_project_root=True)
        self.assertEqual([], result["items"])


if __name__ == "__main__":
    unittest.main()
