import unittest

from core.version_manager import artifact_key, detect_version


class VersionFalsePositiveTests(unittest.TestCase):
    def test_year_is_not_a_version(self):
        self.assertIsNone(detect_version("Отчёт 2026.xlsx"))
        self.assertIsNone(detect_version("Фото 2024.jpg"))

    def test_counter_is_not_a_version(self):
        self.assertIsNone(detect_version("chapter 12.txt"))
        self.assertIsNone(detect_version("invoice_153.pdf"))

    def test_explicit_single_component_version_is_supported(self):
        info = detect_version("SmartOrganizer v3.zip")
        self.assertIsNotNone(info)
        self.assertEqual("v3", info.normalized)

    def test_dotted_and_qualified_versions_are_supported(self):
        self.assertEqual("v1.15.9", detect_version("VoxLyra 1.15.9.zip").normalized)
        self.assertEqual("v12-beta2", detect_version("build 12-beta2.zip").normalized)

    def test_artifact_key_keeps_year_but_removes_real_version(self):
        self.assertEqual("report 2026", artifact_key("report 2026.pdf"))
        self.assertEqual("smart organizer", artifact_key("Smart Organizer v0.2.8.zip"))


if __name__ == "__main__":
    unittest.main()
