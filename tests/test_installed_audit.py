from __future__ import annotations

import unittest
from datetime import date

from core.installed_audit import installation_review, installation_review_text, parse_registry_date


class InstalledAuditTests(unittest.TestCase):
    def test_parse_registry_dates(self):
        self.assertEqual(parse_registry_date("20261010"), date(2026, 10, 10))
        self.assertIsNone(parse_registry_date("20260231"))
        self.assertIsNone(parse_registry_date("2026-10-10"))
        self.assertIsNone(parse_registry_date(""))

    def test_same_day_not_malware_verdict(self):
        apps = [
            {"name": "Browser", "installed": "20261009", "publisher": "Vendor A"},
            {"name": "Helper", "installed": "20261009", "publisher": ""},
            {"name": "Ancient", "installed": "20250101", "publisher": "Vendor"},
            {"name": "Unknown", "installed": "", "publisher": "Vendor"},
            {"name": "Future", "installed": "20270101", "publisher": "Vendor"},
        ]
        result = installation_review(apps, today=date(2026, 10, 10), days=30)
        self.assertEqual(result["unknown_dates"], 1)
        self.assertEqual(len(result["same_day"]), 1)
        self.assertEqual([r["name"] for r in result["same_day"][0]["apps"]],
                         ["Browser", "Helper"])
        report = installation_review_text(result)
        self.assertIn("НЕ доказывает", report)
        self.assertNotIn("Future", report)
        self.assertNotIn("Ancient", report)


if __name__ == "__main__":
    unittest.main()
