import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import updater_main


class RecoveryUpdaterTests(unittest.TestCase):
    def test_double_click_default_installs_full_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "SmartOrganizer.exe").write_bytes(b"old-launcher")
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
                patch.object(updater_main, "ensure_runtime_release_ready") as ready,
                patch.object(updater_main, "find_runtime_asset", return_value=release["assets"][0]),
                patch.object(updater_main, "download_runtime_bundle", return_value=bundle) as download,
                patch.object(updater_main, "create_apply_script", return_value=script) as create_script,
                patch.object(updater_main, "launch_apply_script") as launch,
            ):
                self.assertEqual(updater_main.main(), 0)
            ready.assert_called_once()
            self.assertEqual(download.call_count, 1)
            called_root, called_asset = download.call_args.args
            self.assertTrue(Path(called_root).samefile(root))
            self.assertEqual(called_asset, release["assets"][0])
            self.assertEqual(create_script.call_count, 1)
            args = create_script.call_args.args
            self.assertTrue(Path(args[0]).samefile(root))
            self.assertEqual(args[1], bundle)
            self.assertIsInstance(args[2], int)
            launch.assert_called_once_with(script)

    def test_explicit_install_dir_works_when_updater_is_downloaded_elsewhere(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as download_tmp:
            root = Path(tmp)
            download_dir = Path(download_tmp)
            release = {"assets": [{"name": "SmartOrganizer-runtime.zip"}]}
            bundle = root / ".update-staging" / "SmartOrganizer-runtime.zip"
            script = root / ".apply-smart-organizer-runtime.ps1"
            with (
                patch("sys.argv", ["updater.exe", "--install-dir", str(root)]),
                patch.object(updater_main, "app_root", return_value=download_dir),
                patch.object(updater_main, "fetch_runtime_manifest", return_value={"version": "0.2.7"}),
                patch.object(updater_main, "fetch_runtime_release", return_value=release),
                patch.object(updater_main, "ensure_runtime_release_ready"),
                patch.object(updater_main, "find_runtime_asset", return_value=release["assets"][0]),
                patch.object(updater_main, "download_runtime_bundle", return_value=bundle) as download,
                patch.object(updater_main, "create_apply_script", return_value=script),
                patch.object(updater_main, "launch_apply_script"),
            ):
                self.assertEqual(updater_main.main(), 0)
            self.assertEqual(download.call_count, 1)
            called_root, called_asset = download.call_args.args
            self.assertTrue(Path(called_root).samefile(root))
            self.assertEqual(called_asset, release["assets"][0])

    def test_check_mode_does_not_modify_runtime(self):
        release = {"assets": [{"name": "SmartOrganizer-runtime.zip"}]}
        with (
            patch("sys.argv", ["updater.exe", "--check"]),
            patch.object(updater_main, "fetch_runtime_manifest", return_value={"version": "0.2.7"}),
            patch.object(updater_main, "fetch_runtime_release", return_value=release),
            patch.object(updater_main, "ensure_runtime_release_ready"),
            patch.object(updater_main, "find_runtime_asset", return_value=release["assets"][0]),
            patch.object(updater_main, "download_runtime_bundle") as download,
            patch.object(updater_main, "launch_apply_script") as launch,
        ):
            self.assertEqual(updater_main.main(), 0)
        download.assert_not_called()
        launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
