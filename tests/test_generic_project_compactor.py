import unittest
from pathlib import Path

from core.generic_project_compactor import build_generic_project_compaction_plan


class GenericProjectCompactorTests(unittest.TestCase):
    def _folder(self, path: str, parent: str, depth: int) -> dict:
        return {"path": path, "parent": parent, "name": Path(path).name, "depth": depth}

    def _marker(self, parent: str, name: str) -> dict:
        return {
            "path": str(Path(parent) / name),
            "parent": parent,
            "name": name,
            "extension": Path(name).suffix,
            "size": 1,
            "modified": 0,
            "category": "Код",
            "project_hint": None,
        }

    def test_loose_python_project_uses_container_with_two_existing_python_projects(self):
        root = r"D:\Desk"
        projects = r"D:\Desk\Мои проекты"
        alpha = projects + r"\Alpha"
        beta = projects + r"\Beta"
        gamma = r"D:\Desk\Gamma"
        folders = [
            self._folder(root, "D:\\", 0),
            self._folder(projects, root, 1),
            self._folder(alpha, projects, 2),
            self._folder(beta, projects, 2),
            self._folder(gamma, root, 1),
        ]
        files = [
            self._marker(alpha, "main.py"),
            self._marker(beta, "requirements.txt"),
            self._marker(gamma, "pyproject.toml"),
        ]
        plan = build_generic_project_compaction_plan(files, folders, root)
        self.assertEqual(1, plan["summary"]["containers"])
        self.assertEqual(1, plan["summary"]["folder_moves"])
        item = plan["items"][0]
        self.assertEqual(gamma, item["source"])
        self.assertEqual(projects, item["target_dir"])
        self.assertEqual("learned_project_container", item["reason"])
        self.assertEqual("high", item["confidence"])

    def test_two_equally_valid_containers_block_the_move(self):
        root = r"D:\Desk"
        one = r"D:\Desk\One"
        two = r"D:\Desk\Two"
        loose = r"D:\Desk\Loose"
        folders = [self._folder(root, "D:\\", 0), self._folder(one, root, 1), self._folder(two, root, 1), self._folder(loose, root, 1)]
        files = [self._marker(loose, "main.py")]
        for container in (one, two):
            for child_name in ("A", "B"):
                child = container + "\\" + child_name
                folders.append(self._folder(child, container, 2))
                files.append(self._marker(child, "main.py"))
        plan = build_generic_project_compaction_plan(files, folders, root)
        self.assertEqual([], plan["items"])
        self.assertEqual(1, plan["summary"]["ambiguous"])

    def test_different_project_family_is_not_forced_into_container(self):
        root = r"D:\Desk"
        games = r"D:\Desk\Games"
        server = r"D:\Desk\Server"
        folders = [self._folder(root, "D:\\", 0), self._folder(games, root, 1), self._folder(server, root, 1)]
        files = [self._marker(server, "server.properties")]
        for child_name in ("GameA", "GameB"):
            child = games + "\\" + child_name
            folders.append(self._folder(child, games, 2))
            files.append(self._marker(child, "project.godot"))
        plan = build_generic_project_compaction_plan(files, folders, root)
        self.assertEqual([], plan["items"])
        self.assertEqual(0, plan["summary"]["folder_moves"])

    def test_one_matching_family_container_wins_even_without_special_folder_name(self):
        root = r"D:\Desk"
        container = r"D:\Desk\Работа"
        loose = r"D:\Desk\NewGame"
        folders = [self._folder(root, "D:\\", 0), self._folder(container, root, 1), self._folder(loose, root, 1)]
        files = [self._marker(loose, "project.godot")]
        for child_name in ("A", "B"):
            child = container + "\\" + child_name
            folders.append(self._folder(child, container, 2))
            files.append(self._marker(child, "project.godot"))
        plan = build_generic_project_compaction_plan(files, folders, root)
        self.assertEqual(1, len(plan["items"]))
        self.assertEqual(container, plan["items"][0]["target_dir"])


if __name__ == "__main__":
    unittest.main()
