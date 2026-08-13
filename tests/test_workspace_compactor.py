import unittest

from core.workspace_compactor import build_workspace_compaction_plan


PROJECTS = [
    {
        "name": "VoxLyra",
        "type": "Telegram/VK bot + Mini App",
        "aliases": ["Vox Lyra"],
        "keywords": ["voxlyra"],
    }
]


class WorkspaceCompactorTests(unittest.TestCase):
    def test_project_folder_moves_whole_into_existing_container(self):
        folders = [
            {"path": r"D:\Desk", "parent": "", "name": "Desk", "depth": 0},
            {"path": r"D:\Desk\Боты", "parent": r"D:\Desk", "name": "Боты", "depth": 1},
            {"path": r"D:\Desk\VoxLyra_v1.2", "parent": r"D:\Desk", "name": "VoxLyra_v1.2", "depth": 1},
            {"path": r"D:\Desk\VoxLyra_v1.2\app", "parent": r"D:\Desk\VoxLyra_v1.2", "name": "app", "depth": 2},
        ]
        result = build_workspace_compaction_plan([], folders, PROJECTS, r"D:\Desk")
        self.assertEqual(1, result["summary"]["folder_moves"])
        item = result["items"][0]
        self.assertEqual("folder", item["kind"])
        self.assertEqual(r"D:\Desk\VoxLyra_v1.2", item["source"])
        self.assertEqual(r"D:\Desk\Боты\VoxLyra_v1.2", item["target_path"])
        self.assertEqual("high", item["confidence"])

    def test_multiple_possible_containers_block_move(self):
        folders = [
            {"path": r"D:\Desk", "parent": "", "name": "Desk", "depth": 0},
            {"path": r"D:\Desk\Боты", "parent": r"D:\Desk", "name": "Боты", "depth": 1},
            {"path": r"D:\Desk\Telegram", "parent": r"D:\Desk", "name": "Telegram", "depth": 1},
            {"path": r"D:\Desk\VoxLyra_v1.2", "parent": r"D:\Desk", "name": "VoxLyra_v1.2", "depth": 1},
        ]
        result = build_workspace_compaction_plan([], folders, PROJECTS, r"D:\Desk")
        self.assertEqual([], result["items"])
        self.assertGreaterEqual(result["summary"]["ambiguous"], 1)

    def test_loose_project_file_is_not_guessed_between_version_folders(self):
        folders = [
            {"path": r"D:\Desk", "parent": "", "name": "Desk", "depth": 0},
            {"path": r"D:\Desk\VoxLyra_v1.0", "parent": r"D:\Desk", "name": "VoxLyra_v1.0", "depth": 1},
            {"path": r"D:\Desk\VoxLyra_v2.0", "parent": r"D:\Desk", "name": "VoxLyra_v2.0", "depth": 1},
        ]
        files = [
            {
                "path": r"D:\Desk\VoxLyra_release.zip",
                "parent": r"D:\Desk",
                "name": "VoxLyra_release.zip",
                "extension": ".zip",
                "category": "Архивы",
                "project_hint": "VoxLyra",
            }
        ]
        result = build_workspace_compaction_plan(files, folders, PROJECTS, r"D:\Desk")
        self.assertEqual([], [item for item in result["items"] if item["kind"] == "file"])
        self.assertGreaterEqual(result["summary"]["ambiguous"], 1)


if __name__ == "__main__":
    unittest.main()
