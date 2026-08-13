import unittest

from core.layout_memory import best_user_layout_folder, destination_allowed_by_layout, layout_affinity
from core.sort_planner import build_sort_plan


class LayoutMemoryTests(unittest.TestCase):
    def test_archives_follow_where_user_already_keeps_archives(self):
        files = [
            {
                "path": r"D:\Desk\Inbox\new-release.zip",
                "parent": r"D:\Desk\Inbox",
                "name": "new-release.zip",
                "extension": ".zip",
                "category": "Архивы",
                "project_hint": None,
            },
            {
                "path": r"D:\Desk\My Packages\old-1.zip",
                "parent": r"D:\Desk\My Packages",
                "name": "old-1.zip",
                "extension": ".zip",
                "category": "Архивы",
                "project_hint": None,
            },
            {
                "path": r"D:\Desk\My Packages\old-2.7z",
                "parent": r"D:\Desk\My Packages",
                "name": "old-2.7z",
                "extension": ".7z",
                "category": "Архивы",
                "project_hint": None,
            },
        ]
        folders = [
            {"path": r"D:\Desk", "name": "Desk", "depth": 0},
            {"path": r"D:\Desk\Inbox", "name": "Inbox", "depth": 1},
            {"path": r"D:\Desk\My Packages", "name": "My Packages", "depth": 1},
            {"path": r"D:\Desk\Archives", "name": "Archives", "depth": 1},
        ]

        plan = build_sort_plan(files, folders, [], r"D:\Desk")
        item = next(row for row in plan["items"] if row["source"].endswith("new-release.zip"))
        self.assertEqual(r"D:\Desk\My Packages", item["target_dir"])
        self.assertEqual("existing", item["mode"])
        self.assertEqual("high", item["confidence"])
        self.assertTrue(item["reason"].startswith("user_layout:"))
        self.assertGreaterEqual(plan["summary"]["learned_user_layout_targets"], 1)

    def test_real_contents_outweigh_generic_folder_name(self):
        incoming = {
            "path": r"D:\Desk\Inbox\photo-new.jpg",
            "parent": r"D:\Desk\Inbox",
            "name": "photo-new.jpg",
            "extension": ".jpg",
            "category": "Изображения",
            "project_hint": None,
        }
        files = [
            incoming,
            {
                "path": r"D:\Desk\Family\one.jpg",
                "parent": r"D:\Desk\Family",
                "name": "one.jpg",
                "extension": ".jpg",
                "category": "Изображения",
                "project_hint": None,
            },
            {
                "path": r"D:\Desk\Family\two.png",
                "parent": r"D:\Desk\Family",
                "name": "two.png",
                "extension": ".png",
                "category": "Изображения",
                "project_hint": None,
            },
        ]
        folders = [
            {"path": r"D:\Desk", "name": "Desk", "depth": 0},
            {"path": r"D:\Desk\Inbox", "name": "Inbox", "depth": 1},
            {"path": r"D:\Desk\Family", "name": "Family", "depth": 1},
            {"path": r"D:\Desk\Images", "name": "Images", "depth": 1},
        ]
        learned = best_user_layout_folder(incoming, folders, files, r"D:\Desk")
        self.assertIsNotNone(learned)
        self.assertEqual(r"D:\Desk\Family", learned["path"])

    def test_unrelated_project_layout_is_never_learned_as_destination(self):
        loose = {
            "path": r"D:\Desk\Inbox\asset.zip",
            "parent": r"D:\Desk\Inbox",
            "name": "asset.zip",
            "extension": ".zip",
            "category": "Архивы",
            "project_hint": None,
        }
        files = [
            loose,
            {
                "path": r"D:\Desk\Project-B\main.py",
                "parent": r"D:\Desk\Project-B",
                "name": "main.py",
                "extension": ".py",
                "category": "Код",
                "project_hint": None,
            },
            {
                "path": r"D:\Desk\Project-B\releases\build.zip",
                "parent": r"D:\Desk\Project-B\releases",
                "name": "build.zip",
                "extension": ".zip",
                "category": "Архивы",
                "project_hint": None,
            },
        ]
        self.assertFalse(
            destination_allowed_by_layout(loose, r"D:\Desk\Project-B\releases", files, r"D:\Desk")
        )

    def test_affinity_uses_actual_folder_contents(self):
        record = {
            "name": "backup.zip",
            "extension": ".zip",
            "category": "Архивы",
            "project_hint": "VoxLyra",
        }
        files = [
            {
                "path": r"D:\Backups\old.zip",
                "parent": r"D:\Backups",
                "name": "old.zip",
                "extension": ".zip",
                "category": "Архивы",
                "project_hint": "VoxLyra",
            }
        ]
        score, reasons = layout_affinity(record, r"D:\Backups", files)
        self.assertGreater(score, 50)
        self.assertTrue(any("VoxLyra" in reason for reason in reasons))
        self.assertTrue(any("архив" in reason.lower() for reason in reasons))


if __name__ == "__main__":
    unittest.main()
