import unittest

from core.final_safety_runtime import finalize_executable_plan


class FinalSafetyRuntimeTests(unittest.TestCase):
    def test_medium_confidence_is_review_only(self):
        plan = {"items": [{"source": r"D:\A\x.txt", "target_dir": r"D:\B", "target_path": r"D:\B\x.txt", "mode": "existing", "confidence": "medium", "requires_confirmation": False, "score": 30}], "summary": {}}
        result = finalize_executable_plan(plan)
        self.assertEqual("review", result["items"][0]["mode"])
        self.assertTrue(result["items"][0]["requires_confirmation"])

    def test_file_move_is_ordered_before_folder_move(self):
        plan = {"items": [
            {"kind": "folder", "source": r"D:\Desk\Project", "target_dir": r"D:\Desk\Bots", "target_path": r"D:\Desk\Bots\Project", "mode": "existing", "confidence": "high", "score": 180},
            {"kind": "file", "source": r"D:\Desk\release.zip", "target_dir": r"D:\Desk\Project", "target_path": r"D:\Desk\Project\release.zip", "mode": "existing", "confidence": "high", "score": 170},
        ], "summary": {}}
        result = finalize_executable_plan(plan)
        self.assertEqual("file", result["items"][0]["kind"])
        self.assertEqual("folder", result["items"][1]["kind"])


if __name__ == "__main__":
    unittest.main()
