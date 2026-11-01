"""Pruebas de macos.py con las APIs del sistema simuladas (corren en cualquier SO)."""

import plistlib
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

import macos


class TestStartupManager:
    @pytest.fixture(autouse=True)
    def agents_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("macos.LAUNCH_AGENTS_DIR", str(tmp_path / "LaunchAgents"))
        return tmp_path / "LaunchAgents"

    def test_enable_writes_plist(self, agents_dir):
        macos.StartupManager.enable()

        assert macos.StartupManager.is_enabled()
        with open(macos.StartupManager.plist_path(), "rb") as f:
            data = plistlib.load(f)
        assert data["Label"] == macos.LAUNCH_AGENT_LABEL
        assert data["RunAtLoad"] is True
        assert data["ProgramArguments"][0] == sys.executable
        assert data["ProgramArguments"][1].endswith("escriba.py")

    def test_frozen_app_uses_executable_only(self, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        assert macos.StartupManager._program_arguments() == [sys.executable]

    def test_disable_removes_plist_and_is_idempotent(self):
        macos.StartupManager.enable()
        macos.StartupManager.disable()
        macos.StartupManager.disable()
        assert not macos.StartupManager.is_enabled()


class TestKeychain:
    def test_get_returns_password(self):
        with patch("macos.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="clave\n", stderr="")) as run:
            assert macos.keychain_get("api_key") == "clave"
        args = run.call_args[0][0]
        assert args[:2] == ["security", "find-generic-password"]
        assert ["-s", "Escriba"] == args[2:4] and ["-a", "api_key"] == args[4:6]

    def test_get_missing_returns_empty(self):
        with patch("macos.subprocess.run", return_value=SimpleNamespace(returncode=44, stdout="", stderr="")):
            assert macos.keychain_get("api_key") == ""

    def test_set_updates_entry(self):
        with patch("macos.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="", stderr="")) as run:
            macos.keychain_set("api_key", "nueva")
        args = run.call_args[0][0]
        assert args[:3] == ["security", "add-generic-password", "-U"]
        assert args[-2:] == ["-w", "nueva"]

    def test_set_empty_deletes_entry(self):
        with patch("macos.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="", stderr="")) as run:
            macos.keychain_set("api_key", "")
        assert run.call_args[0][0][1] == "delete-generic-password"

    def test_set_failure_raises(self):
        with patch("macos.subprocess.run", return_value=SimpleNamespace(returncode=1, stdout="", stderr="denegado")):
            with pytest.raises(OSError, match="denegado"):
                macos.keychain_set("api_key", "x")


class TestKeyboard:
    def test_copy_posts_cmd_c_with_explicit_flags(self):
        quartz = MagicMock()
        with patch.dict(sys.modules, {"Quartz": quartz}), patch("macos.time.sleep"):
            macos.send_copy()

        keycodes = [c.args[1] for c in quartz.CGEventCreateKeyboardEvent.call_args_list]
        downs = [c.args[2] for c in quartz.CGEventCreateKeyboardEvent.call_args_list]
        assert keycodes == [macos._KVK_ANSI_C] * 2
        assert downs == [True, False]
        assert all(c.args[1] == macos._FLAG_COMMAND for c in quartz.CGEventSetFlags.call_args_list)
        assert quartz.CGEventPost.call_count == 2

    def test_paste_posts_cmd_v(self):
        quartz = MagicMock()
        with patch.dict(sys.modules, {"Quartz": quartz}), patch("macos.time.sleep"):
            macos.send_paste()
        assert quartz.CGEventCreateKeyboardEvent.call_args_list[0].args[1] == macos._KVK_ANSI_V


class TestForegroundApp:
    def test_get_and_activate(self):
        appkit = MagicMock()
        front = MagicMock()
        appkit.NSWorkspace.sharedWorkspace.return_value.frontmostApplication.return_value = front
        with patch.dict(sys.modules, {"AppKit": appkit}), patch("macos.time.sleep"):
            handle = macos.get_foreground_window()
            macos.activate_window(handle)
        assert handle is front
        front.activateWithOptions_.assert_called_once_with(appkit.NSApplicationActivateIgnoringOtherApps)

    def test_activate_none_is_noop(self):
        macos.activate_window(None)

    def test_get_without_appkit_returns_none(self):
        with patch.dict(sys.modules, {"AppKit": None}):
            assert macos.get_foreground_window() is None


class TestHotkeyManager:
    def test_registers_ctrl_cmd_e(self):
        pynput = MagicMock()
        with patch.dict(sys.modules, {"pynput": pynput, "pynput.keyboard": pynput.keyboard}):
            hm = macos.HotkeyManager(MagicMock(), MagicMock())
            hm.start()
            mapping = pynput.keyboard.GlobalHotKeys.call_args[0][0]
            hm.stop()

        assert list(mapping) == ["<ctrl>+<cmd>+e"]
        pynput.keyboard.GlobalHotKeys.return_value.start.assert_called_once()
        pynput.keyboard.GlobalHotKeys.return_value.stop.assert_called_once()

    def test_fire_runs_callback_in_thread(self):
        callback = MagicMock()
        hm = macos.HotkeyManager(MagicMock(), callback)
        with patch("macos.threading.Thread") as thread:
            hm._fire()
        thread.assert_called_once_with(target=callback, daemon=True)

    def test_start_failure_reports_error(self):
        root = MagicMock()
        callback = MagicMock()
        with patch.dict(sys.modules, {"pynput": None}):
            macos.HotkeyManager(root, callback).start()
        root.after.assert_called_once()
        root.after.call_args[0][1]()
        callback.assert_called_once_with(error=True)
