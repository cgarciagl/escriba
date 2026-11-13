import os
import subprocess
import sys
import types
from unittest.mock import MagicMock

import pytest

import linux_platform


class TestToPynput:
    def test_default_on_empty_or_invalid(self):
        assert linux_platform._to_pynput(None) == linux_platform.HOTKEY_PYNPUT
        assert linux_platform._to_pynput("") == linux_platform.HOTKEY_PYNPUT
        assert linux_platform._to_pynput("E") == linux_platform.HOTKEY_PYNPUT
        assert linux_platform._to_pynput("Ctrl+UnknownKeyName") == linux_platform.HOTKEY_PYNPUT

    def test_valid_combinations(self):
        assert linux_platform._to_pynput("Ctrl+Alt+E") == "<ctrl>+<alt>+e"
        assert linux_platform._to_pynput("Super+Alt+E") == "<cmd>+<alt>+e"
        assert linux_platform._to_pynput("Ctrl+Alt+Space") == "<ctrl>+<alt>+<space>"
        assert linux_platform._to_pynput("Ctrl+Shift+F5") == "<ctrl>+<shift>+<f5>"


class TestWindowFocus:
    def test_get_foreground_window_returns_id(self, monkeypatch):
        res = subprocess.CompletedProcess(["xdotool", "getactivewindow"], 0, stdout="123456\n", stderr="")
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: res)
        assert linux_platform.get_foreground_window() == "123456"

    def test_get_foreground_window_missing_xdotool_returns_none(self, monkeypatch):
        def raise_fnf(*a, **kw):
            raise FileNotFoundError("xdotool")

        monkeypatch.setattr(subprocess, "run", raise_fnf)
        assert linux_platform.get_foreground_window() is None

    def test_activate_window_calls_xdotool(self, monkeypatch):
        calls = []

        def fake_run(cmd, **kw):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        monkeypatch.setattr(linux_platform.time, "sleep", lambda _s: None)
        linux_platform.activate_window("999")
        assert calls == [["xdotool", "windowactivate", "--sync", "999"]]

    def test_activate_window_noop_when_none(self, monkeypatch):
        called = False

        def fake_run(*a, **kw):
            nonlocal called
            called = True

        monkeypatch.setattr(subprocess, "run", fake_run)
        linux_platform.activate_window(None)
        assert not called


class TestClipboardShortcuts:
    def test_send_copy_and_paste_use_pynput(self, monkeypatch):
        pressed_ctx = MagicMock()
        ctrl_instance = MagicMock()
        ctrl_instance.pressed.return_value = pressed_ctx

        fake_keyboard = types.SimpleNamespace(
            Controller=lambda: ctrl_instance,
            Key=types.SimpleNamespace(
                ctrl="CTRL", alt="ALT", alt_l="ALTL", alt_r="ALTR",
                ctrl_l="CTRLL", ctrl_r="CTRLR", shift="SHIFT", shift_l="SHIFTL",
                shift_r="SHIFTR", cmd="CMD", cmd_l="CMDL", cmd_r="CMDR",
            ),
        )
        fake_pynput = types.SimpleNamespace(keyboard=fake_keyboard)
        monkeypatch.setitem(sys.modules, "pynput", fake_pynput)
        monkeypatch.setattr(linux_platform.time, "sleep", lambda _s: None)

        linux_platform.send_copy()
        ctrl_instance.pressed.assert_called_with("CTRL")
        ctrl_instance.press.assert_called_with("c")
        ctrl_instance.release.assert_any_call("c")

        ctrl_instance.reset_mock()
        linux_platform.send_paste()
        ctrl_instance.pressed.assert_called_with("CTRL")
        ctrl_instance.press.assert_called_with("v")
        ctrl_instance.release.assert_any_call("v")


class TestHotkeyManager:
    def test_start_and_stop(self, monkeypatch):
        listener = MagicMock()
        captured = {}

        def fake_global_hotkeys(mapping):
            captured.update(mapping)
            return listener

        fake_keyboard = types.SimpleNamespace(GlobalHotKeys=fake_global_hotkeys)
        monkeypatch.setitem(sys.modules, "pynput", types.SimpleNamespace(keyboard=fake_keyboard))

        root = MagicMock()
        mgr = linux_platform.HotkeyManager(root, lambda: None, "Ctrl+Alt+E")
        mgr.start()
        assert "<ctrl>+<alt>+e" in captured
        listener.start.assert_called_once()

        mgr.stop()
        listener.stop.assert_called_once()

    def test_start_error_notifies_callback(self, monkeypatch):
        def fail(*_a, **_kw):
            raise RuntimeError("no X display")

        fake_keyboard = types.SimpleNamespace(GlobalHotKeys=fail)
        monkeypatch.setitem(sys.modules, "pynput", types.SimpleNamespace(keyboard=fake_keyboard))

        root = MagicMock()
        root.after = lambda _ms, fn: fn()
        errors = []
        mgr = linux_platform.HotkeyManager(root, lambda error=False: errors.append(error))
        mgr.start()
        assert errors == [True]


class TestStartupManager:
    def test_enable_is_enabled_and_disable(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        mgr = linux_platform.StartupManager

        assert mgr.is_enabled() is False
        mgr.enable()
        assert mgr.is_enabled() is True

        path = mgr.desktop_path()
        assert os.path.exists(path)
        content = open(path, encoding="utf-8").read()
        assert "[Desktop Entry]" in content
        assert "Name=Escriba" in content
        assert "Exec=" in content

        mgr.disable()
        assert mgr.is_enabled() is False
        # disable idempotente
        mgr.disable()
