from __future__ import annotations

import unittest
from unittest.mock import patch, Mock

from core.msi_uninstall import eligible_msi_items, launch_msi_uninstall


class MsiSafetyTests(unittest.TestCase):
    def test_only_trusted_msi_product_codes_are_eligible(self):
        good = "{01234567-89AB-CDEF-0123-456789ABCDEF}"
        apps = [
            {"name": "Demo Editor", "registry_key": good, "windows_installer": True},
            {"name": "Demo Launcher", "registry_key": good, "windows_installer": True},
            {"name": "Browser", "registry_key": "Uninstall_exe", "windows_installer": False},
            {"name": "Microsoft Visual C++ Redistributable", "registry_key": 
             "{11111111-1111-1111-1111-111111111111}", "windows_installer": True},
            {"name": "Malicious", "registry_key": "bad; & calc.exe", "windows_installer": True},
        ]
        result = eligible_msi_items(apps)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Demo Editor")
        self.assertEqual(result[0]["product_code"], good)

    def test_reject_command_injection_without_subprocess(self):
        with patch("core.msi_uninstall.os.name", "nt"), \
             patch("core.msi_uninstall.subprocess.Popen") as proc:
            with self.assertRaises(ValueError):
                launch_msi_uninstall('"{GUID}" & powershell.exe')
            proc.assert_not_called()

    def test_non_windows_cannot_start_uninstaller(self):
        with patch("core.msi_uninstall.os.name", "posix"), \
             patch("core.msi_uninstall.subprocess.Popen") as proc:
            with self.assertRaises(RuntimeError):
                launch_msi_uninstall("{01234567-89AB-CDEF-0123-456789ABCDEF}")
            proc.assert_not_called()


if __name__ == "__main__":
    unittest.main()
