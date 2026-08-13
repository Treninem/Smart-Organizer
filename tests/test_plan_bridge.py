import unittest

from core.plan_bridge import operations_from_sort_plan


class PlanBridgeTests(unittest.TestCase):
    def test_only_existing_targets_become_operations_by_default(self):
        plan = {
            "items": [
                {
                    "source": r"D:\Inbox\report.pdf",
                    "target_path": r"D:\Docs\report.pdf",
                    "mode": "existing",
                    "requires_confirmation": False,
                    "reason": "existing documents folder",
                },
                {
                    "source": r"D:\Inbox\photo.jpg",
                    "target_path": r"D:\Photos\New\photo.jpg",
                    "mode": "proposed",
                    "requires_confirmation": True,
                    "reason": "new folder proposal",
                },
            ]
        }
        operations = operations_from_sort_plan(plan)
        self.assertEqual(len(operations), 1)
        self.assertEqual(operations[0].source, r"D:\Inbox\report.pdf")
        self.assertEqual(operations[0].target, r"D:\Docs\report.pdf")

    def test_duplicate_targets_are_rejected(self):
        plan = {
            "items": [
                {
                    "source": r"D:\A\one.txt",
                    "target_path": r"D:\Target\same.txt",
                    "mode": "existing",
                    "requires_confirmation": False,
                },
                {
                    "source": r"D:\B\two.txt",
                    "target_path": r"D:\Target\same.txt",
                    "mode": "existing",
                    "requires_confirmation": False,
                },
            ]
        }
        with self.assertRaises(ValueError):
            operations_from_sort_plan(plan)

    def test_conversion_is_read_only_data_only(self):
        plan = {"items": []}
        self.assertEqual(operations_from_sort_plan(plan), [])


if __name__ == "__main__":
    unittest.main()
