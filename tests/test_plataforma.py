import importlib
import sys
from unittest.mock import MagicMock, patch

import plataforma


class TestHelpers:
    def test_shortcut_label_windows(self, monkeypatch):
        monkeypatch.setattr(plataforma, "IS_MAC", False)
        assert plataforma.shortcut_label("Ctrl+Enter") == "Ctrl+Enter"

    def test_shortcut_label_mac(self, monkeypatch):
        monkeypatch.setattr(plataforma, "IS_MAC", True)
        assert plataforma.shortcut_label("Ctrl+Enter") == "⌘↩"

    def test_tk_shortcut_uses_primary_modifier(self, monkeypatch):
        monkeypatch.setattr(plataforma, "PRIMARY_MODIFIER_TK", "Command")
        assert plataforma.tk_shortcut("Return") == "<Command-Return>"

    def test_format_hotkey_label_windows_and_linux(self, monkeypatch):
        monkeypatch.setattr(plataforma, "IS_MAC", False)
        monkeypatch.setattr(plataforma, "IS_LINUX", False)
        assert plataforma.format_hotkey_label("win+alt+k") == "Win + Alt + K"
        assert plataforma.format_hotkey_label("") == plataforma.HOTKEY_LABEL

    def test_format_hotkey_label_mac(self, monkeypatch):
        monkeypatch.setattr(plataforma, "IS_MAC", True)
        assert plataforma.format_hotkey_label("ctrl+cmd+e") == "⌃ + ⌘ + E"

    def test_active_hotkey_label_uses_config(self, monkeypatch):
        monkeypatch.setattr(plataforma, "IS_MAC", False)
        monkeypatch.setattr(plataforma, "IS_LINUX", False)
        with patch("config.ConfigManager.get", return_value="ctrl+shift+e"):
            assert plataforma.active_hotkey_label() == "Ctrl + Shift + E"


class TestSingleInstanceAndClipboard:
    def test_posix_single_instance_lock_blocks_second_acquire(self, tmp_path, monkeypatch):
        monkeypatch.setattr(plataforma, "IS_WINDOWS", False)
        monkeypatch.setattr(plataforma, "_INSTANCE_LOCK", None)
        with patch("tempfile.gettempdir", return_value=str(tmp_path)):
            assert plataforma.acquire_single_instance("EscribaTest") is True
            # Simula un segundo proceso mientras el primero mantiene el flock
            fh2 = open(tmp_path / "escribatest.lock", "a+", encoding="utf-8")
            try:
                import fcntl
                try:
                    fcntl.flock(fh2.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    blocked = False
                except OSError:
                    blocked = True
                assert blocked is True
            finally:
                fh2.close()
                plataforma.release_single_instance()
            assert plataforma._INSTANCE_LOCK is None
            assert plataforma.acquire_single_instance("EscribaTest") is True
            plataforma.release_single_instance()

    def test_clipboard_has_non_text_non_windows(self, monkeypatch):
        if not plataforma.IS_WINDOWS:
            assert plataforma.clipboard_has_non_text() is False

    def test_clipboard_has_non_text_windows_logic(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        try:
            mod = importlib.reload(plataforma)
            user32 = MagicMock()
            user32.CountClipboardFormats.return_value = 2
            user32.IsClipboardFormatAvailable.return_value = False
            with patch.object(mod.ctypes, "windll", MagicMock(user32=user32)):
                assert mod.clipboard_has_non_text() is True
                user32.IsClipboardFormatAvailable.side_effect = lambda fmt: fmt == 13
                assert mod.clipboard_has_non_text() is False
        finally:
            monkeypatch.undo()
            importlib.reload(plataforma)


class TestDispatch:
    def test_exposes_common_interface(self):
        for name in ("HotkeyManager", "StartupManager", "send_copy", "send_paste",
                     "get_foreground_window", "activate_window", "init_app",
                     "bring_app_to_front", "HOTKEY_LABEL", "SECRET_BACKEND"):
            assert hasattr(plataforma, name), name

    def test_macos_branch_selects_mac_implementation(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        try:
            mod = importlib.reload(plataforma)
            import macos

            assert mod.IS_MAC is True
            assert mod.HotkeyManager is macos.HotkeyManager
            assert mod.StartupManager is macos.StartupManager
            assert mod.SECRET_BACKEND == "keychain"
            assert mod.HOTKEY_LABEL == macos.HOTKEY_LABEL
        finally:
            monkeypatch.undo()
            importlib.reload(plataforma)

    def test_linux_branch_selects_linux_implementation(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        try:
            mod = importlib.reload(plataforma)
            import linux_platform

            assert mod.IS_LINUX is True
            assert mod.IS_MAC is False
            assert mod.IS_WINDOWS is False
            assert mod.HotkeyManager is linux_platform.HotkeyManager
            assert mod.StartupManager is linux_platform.StartupManager
            assert mod.SECRET_BACKEND == "plain"
            assert mod.HOTKEY_LABEL == linux_platform.HOTKEY_LABEL
        finally:
            monkeypatch.undo()
            importlib.reload(plataforma)


class TestClampToArea:
    AREA = (0, 0, 1920, 1040)

    def test_inside_unchanged(self):
        assert plataforma.clamp_to_area(100, 100, 300, 400, self.AREA) == (100, 100)

    def test_pushed_left_and_up_near_edges(self):
        assert plataforma.clamp_to_area(1900, 1000, 300, 400, self.AREA) == (1620, 640)

    def test_secondary_monitor_with_negative_origin(self):
        area = (-1280, 0, 0, 1024)
        assert plataforma.clamp_to_area(-50, 900, 300, 400, area) == (-300, 624)

    def test_window_larger_than_area_sticks_to_top_left(self):
        assert plataforma.clamp_to_area(500, 500, 3000, 3000, self.AREA) == (0, 0)
