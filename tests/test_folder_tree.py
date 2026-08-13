import unittest

from core.folder_tree import render_folder_tree


class FolderTreeTests(unittest.TestCase):
    def test_tree_is_relative_to_last_scan_root(self):
        folders = [
            {"path": r"D:\Work", "parent": "D:\\", "name": "Work", "depth": 0},
            {"path": r"D:\Work\VoxLyra", "parent": r"D:\Work", "name": "VoxLyra", "depth": 1},
            {"path": r"D:\Work\VoxLyra\Books", "parent": r"D:\Work\VoxLyra", "name": "Books", "depth": 2},
        ]
        text = render_folder_tree(folders, r"D:\Work")
        self.assertIn("D:\\Work", text)
        self.assertIn("└─ VoxLyra", text)
        self.assertIn("   └─ Books", text)


if __name__ == "__main__":
    unittest.main()
