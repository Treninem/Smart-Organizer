import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import updater_main


class RecoveryUpdaterTests(unittest.TestCase):
    def test_double_click_default_installs_full_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / ".update-staging" / "SmartOrganizer-runtime.zip"
            script = root / ".apply-smart-organizer-runtime.ps1"
            release = {
                "assets": [
                    {
                        "name": "SmartOrganizer-runtime.zip",
                        "browser_download_url": "https://example.invalid/runtime.zip",
                    }
                ]
            }
            with (
                patch("sys.argv", ["updater.exe"]),
                patch.object(updater_main, "app_root", return_value=root),
                patch.object(updater_main, "fetch_runtime_manifest", return_value={"version": "0.2.7"}),
                patch.object(updater_main, "fetch_runtime_release", return_value=release),
                patch.object(updater_main, "find_runtime_asset", return_value=release["assets"][0]),
                patch.object(updater_main, "download_runtime_bundle", return_value=bundle) as download,
                patch.object(updater_main, "create_apply_script", return_value=script) as create_script,
                patch.object(updater_main, "launch_apply_script") as launch,
            ):
                self.assertEqual(updater_main.main(), 0)
            download.assert_called_once_with(root, release["assets"][0])
            self.assertEqual(create_script.call_count, 1)
            args = create_script.call_args.args
            self.assertEqual(args[0], root)
            self.assertEqual(args[1], bundle)
            self.assertIsInstance(args[2], int)
            launch.assert_called_once_with(script)

    def test_check_mode_does_not_modify_runtime(self):
        release = {"assets": [{"name": "SmartOrganizer-runtime.zip"}]}
        with (
            patch("sys.argv", ["updater.exe", "--check"]),
            patch.object(updater_main, "fetch_runtime_manifest", return_value={"version": "0.2.7"}),
            patch.object(updater_main, "fetch_runtime_release", return_value=release),
            patch.object(updater_main, "find_runtime_asset", return_value=release["assets"][0]),
            patch.object(updater_main, "download_runtime_bundle") as download,
            patch.object(updater_main, "launch_apply_script") as launch,
        ):
            self.assertEqual(updater_main.main(), 0)
        download.assert_not_called()
        launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
