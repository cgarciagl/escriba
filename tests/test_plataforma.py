import importlib
import sys

import pytest

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
