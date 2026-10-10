from __future__ import annotations

import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from core.background_engine import normalized_power_settings
from main import _install_settings_and_close_fixes


class ShutdownTests(unittest.TestCase):
    def _app_class(self):
        class FakeApp:
            def __init__(self):
                self.registered_protocol = {}
                self.registered_keys = {}
                self.cancelled = []
                self.monitor_stop = threading.Event()
                self.db = SimpleNamespace(close=Mock())
                self._background_after_id = "background-id"
                self._auto_update_after_id = "update-id"
                self._update_after_id = "legacy-id"
                self._game_poll_after_id = None
                self._restart_pending = True
                self.quit = Mock()
                self.destroy = Mock()

            def show_settings(self):
                return "full settings"

            def protocol(self, name, callback):
                self.registered_protocol[name] = callback

            def bind_all(self, name, callback):
                self.registered_keys[name] = callback

            def after_cancel(self, callback_id):
                self.cancelled.append(callback_id)

        window = SimpleNamespace(SmartOrganizerApp=FakeApp)
        _install_settings_and_close_fixes(window)
        return window.SmartOrganizerApp

    def test_cross_closes_and_restores_true_settings_view(self):
        cls = self._app_class()
        app = cls()
        self.assertEqual(app.show_settings(), "full settings")
        self.assertIn("WM_DELETE_WINDOW", app.registered_protocol)
        app.registered_protocol["WM_DELETE_WINDOW"]()
        self.assertTrue(app._closing)
        self.assertTrue(app._force_real_exit)
        self.assertFalse(app._restart_pending)
        self.assertTrue(app.monitor_stop.is_set())
        self.assertCountEqual(app.cancelled, ["background-id", "update-id", "legacy-id"])
        app.db.close.assert_called_once_with()
        app.quit.assert_called_once_with()
        app.destroy.assert_called_once_with()
        # Double-clicking the close button is safe.
        app.registered_protocol["WM_DELETE_WINDOW"]()
        app.db.close.assert_called_once_with()
        app.destroy.assert_called_once_with()

    def test_ctrl_q_and_explicit_close(self):
        cls = self._app_class()
        app = cls()
        app.registered_keys["<Control-q>"](None)
        app.destroy.assert_called_once_with()
        app2 = cls()
        app2.on_close()
        app2.destroy.assert_called_once_with()

    def test_errors_cannot_prevent_destroy(self):
        cls = self._app_class()
        app = cls()
        app.db.close.side_effect = RuntimeError("busy db")
        app.quit.side_effect = RuntimeError("Tk exiting")
        app.on_close()
        app.destroy.assert_called_once_with()

    def test_existing_close_to_background_setting_is_disabled(self):
        self.assertFalse(normalized_power_settings(None)["close_to_background"])
        self.assertFalse(normalized_power_settings(
            {"background_enabled": True, "close_to_background": True}
        )["close_to_background"])
        self.assertFalse(normalized_power_settings(None)["start_with_windows"])
        self.assertTrue(normalized_power_settings(
            {"start_with_windows": True}
        )["start_with_windows"])


if __name__ == "__main__":
    unittest.main()
