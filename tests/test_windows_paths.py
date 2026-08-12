import unittest
from pathlib import Path
from unittest import mock

from core.windows_paths import desktop_path, downloads_path


class WindowsPathTests(unittest.TestCase):
    def test_redirected_desktop_is_respected(self):
        with mock.patch("core.windows_paths._from_registry", return_value=Path(r"D:\\Рабочий стол")):
            self.assertEqual(desktop_path(), Path(r"D:\\Рабочий стол"))

    def test_redirected_downloads_are_respected(self):
        with mock.patch("core.windows_paths._from_registry", return_value=Path(r"D:\\Загрузки")):
            self.assertEqual(downloads_path(), Path(r"D:\\Загрузки"))

    def test_fallback_resolver_does_not_require_ctypes(self):
        with mock.patch("core.windows_paths._from_registry", return_value=None), mock.patch(
            "core.windows_paths._from_powershell", return_value=Path(r"D:\\Desktop")
        ):
            self.assertEqual(desktop_path(), Path(r"D:\\Desktop"))


if __name__ == "__main__":
    unittest.main()
