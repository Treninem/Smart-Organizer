from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from core.game_priority import (
    BELOW_NORMAL_PRIORITY, NORMAL_PRIORITY, GameModeController, parse_names,
)
from core.pc_health import installed_applications, running_processes, startup_entries


class GameModeTests(unittest.TestCase):
    def test_executable_names_are_explicit_and_safe(self):
        self.assertEqual(
            parse_names("game.exe, Chrome.exe; C:\\Windows\\cmd.exe, explorer.exe, *.exe"),
            ["game.exe", "chrome.exe"],
        )

    def test_opt_in_priority_change_and_restore_after_game_exits(self):
        controller = GameModeController()
        levels = {101: NORMAL_PRIORITY, 202: NORMAL_PRIORITY}
        rows = [{"name": "game.exe", "pid": 101}, {"name": "browser.exe", "pid": 202}]
        writes = []

        def read(pid):
            return levels.get(pid)

        def write(pid, priority):
            writes.append((pid, priority))
            levels[pid] = priority
            return True

        before = controller.tick(rows, ["game.exe"], ["browser.exe"],
                                 read_priority=read, write_priority=write)
        self.assertTrue(before["game_active"])
        self.assertEqual(before["limited_now"], 1)
        self.assertEqual(writes, [(202, BELOW_NORMAL_PRIORITY)])

        again = controller.tick(rows, ["game.exe"], ["browser.exe"],
                                read_priority=read, write_priority=write)
        self.assertEqual(again["newly_limited"], 0)
        self.assertEqual(len(writes), 1)

        after = controller.tick([rows[1]], ["game.exe"], ["browser.exe"],
                                read_priority=read, write_priority=write)
        self.assertFalse(after["game_active"])
        self.assertEqual(after["restored"], 1)
        self.assertEqual(levels[202], NORMAL_PRIORITY)

    def test_no_background_changes_if_not_opted_in(self):
        controller = GameModeController()
        write = Mock()
        controller.tick(
            [{"name": "game.exe", "pid": 101}, {"name": "browser.exe", "pid": 202}],
            ["game.exe"], ["browser.exe"], enabled=False,
            read_priority=lambda pid: NORMAL_PRIORITY, write_priority=write,
        )
        write.assert_not_called()

    def test_does_not_touch_protected_system_processes(self):
        controller = GameModeController()
        write = Mock()
        controller.tick(
            [{"name": "game.exe", "pid": 101}, {"name": "svchost.exe", "pid": 202}],
            ["game.exe"], ["svchost.exe"], enabled=True,
            read_priority=lambda pid: NORMAL_PRIORITY, write_priority=write,
        )
        write.assert_not_called()

    def test_pid_reuse_does_not_restore_wrong_process(self):
        controller = GameModeController()
        state = {202: NORMAL_PRIORITY}
        controller.tick(
            [{"name": "game.exe", "pid": 101}, {"name": "browser.exe", "pid": 202}],
            ["game.exe"], ["browser.exe"], read_priority=lambda pid: state[pid],
            write_priority=lambda pid, pr: state.__setitem__(pid, pr) or True,
        )
        state[202] = BELOW_NORMAL_PRIORITY
        write = Mock()
        controller.tick(
            [{"name": "different.exe", "pid": 202}], ["game.exe"], ["browser.exe"],
            read_priority=lambda pid: state[pid], write_priority=write,
        )
        write.assert_not_called()

    def test_never_promotes_game_to_realtime(self):
        controller = GameModeController()
        writes = []
        controller.tick(
            [{"name": "game.exe", "pid": 101}, {"name": "browser.exe", "pid": 202}],
            ["game.exe"], ["browser.exe"],
            read_priority=lambda pid: 0x80 if pid == 202 else NORMAL_PRIORITY,
            write_priority=lambda pid, priority: writes.append((pid, priority)) or True,
        )
        self.assertEqual(writes, [])


class InventoryTests(unittest.TestCase):
    def test_non_windows_inventory_is_inert(self):
        with patch("core.pc_health.os.name", "posix"):
            self.assertEqual(installed_applications(), [])
            self.assertEqual(startup_entries(), [])
            self.assertEqual(running_processes(), [])

    def test_tasklist_csv_handles_spaces_and_numeric_pids(self):
        sample = '"browser.exe","4312","Console","1","123 456 K"\n' \
                 '"game.exe","11","Console","1","88,912 K"\n'
        run = Mock(returncode=0, stdout=sample, stderr="")
        with patch("core.pc_health.os.name", "nt"), \
             patch("core.pc_health.subprocess.run", return_value=run):
            result = running_processes()
        self.assertEqual([item["pid"] for item in result], [4312, 11])
        self.assertEqual(result[0]["memory_kib"], 123456)


if __name__ == "__main__":
    unittest.main()
