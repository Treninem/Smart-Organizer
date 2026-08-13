import inspect
import unittest

import core.safe_layout_runtime as safe_runtime
from core.safe_layout_runtime import confirmed_creation_items, safe_executable_items


class SafeLayoutRuntimeTests(unittest.TestCase):
    def test_new_folder_guesses_are_preview_only(self):
        plan = {
            "items": [
                {
                    "source": r"D:\Inbox\a.zip",
                    "target_dir": r"D:\Archives",
                    "target_path": r"D:\Archives\a.zip",
                    "mode": "existing",
                    "requires_confirmation": False,
                    "confidence": "high",
                },
                {
                    "source": r"D:\Inbox\b.bin",
                    "target_dir": r"D:\Smart-Organizer_Unsorted\Прочее",
                    "target_path": r"D:\Smart-Organizer_Unsorted\Прочее\b.bin",
                    "mode": "proposed",
                    "requires_confirmation": True,
                    "confidence": "low",
                },
            ]
        }
        result = safe_executable_items(plan)
        self.assertEqual(1, len(result))
        self.assertEqual(r"D:\Inbox\a.zip", result[0]["source"])

    def test_medium_confidence_existing_move_is_not_executable(self):
        plan = {
            "items": [
                {
                    "source": r"D:\Inbox\a.zip",
                    "target_dir": r"D:\Archives",
                    "target_path": r"D:\Archives\a.zip",
                    "mode": "existing",
                    "requires_confirmation": False,
                    "confidence": "medium",
                }
            ]
        }
        self.assertEqual([], safe_executable_items(plan))

    def test_confirmation_flag_blocks_execution_even_for_existing_mode(self):
        plan = {
            "items": [
                {
                    "source": r"D:\Inbox\a.zip",
                    "target_dir": r"D:\Archives",
                    "target_path": r"D:\Archives\a.zip",
                    "mode": "existing",
                    "requires_confirmation": True,
                    "confidence": "high",
                }
            ]
        }
        self.assertEqual([], safe_executable_items(plan))

    def test_only_explicit_family_rule_can_create_destination(self):
        plan = {
            "items": [
                {
                    "source": r"D:\Desk\Tool_v1.0",
                    "target_dir": r"D:\Desk\Tool",
                    "target_path": r"D:\Desk\Tool\Tool_v1.0",
                    "mode": "family_proposed",
                    "requires_confirmation": True,
                    "confidence": "high",
                    "allow_confirmed_creation": True,
                },
                {
                    "source": r"D:\Desk\unknown.bin",
                    "target_dir": r"D:\Desk\Other",
                    "target_path": r"D:\Desk\Other\unknown.bin",
                    "mode": "proposed",
                    "requires_confirmation": True,
                    "confidence": "high",
                },
            ]
        }
        result = confirmed_creation_items(plan)
        self.assertEqual(1, len(result))
        self.assertTrue(result[0]["source"].endswith("Tool_v1.0"))

    def test_real_organize_action_uses_latest_class_plan(self):
        source = inspect.getsource(safe_runtime.install_safe_layout_runtime)
        self.assertIn("self._current_safe_plan()", source)
        self.assertIn("_with_undo_memory(self, self._current_safe_plan())", source)
        self.assertNotIn("plan = _current_safe_plan(self)\n        self._last_sort_plan", source)


if __name__ == "__main__":
    unittest.main()
