import unittest

from core.safe_layout_runtime import safe_executable_items


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

    def test_confirmation_flag_blocks_execution_even_for_existing_mode(self):
        plan = {
            "items": [
                {
                    "source": r"D:\Inbox\a.zip",
                    "target_dir": r"D:\Archives",
                    "target_path": r"D:\Archives\a.zip",
                    "mode": "existing",
                    "requires_confirmation": True,
                }
            ]
        }
        self.assertEqual([], safe_executable_items(plan))


if __name__ == "__main__":
    unittest.main()
