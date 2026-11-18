from unittest.mock import MagicMock, call, patch

import pytest

import escriba
from escriba import EscribaApp


@pytest.fixture
def mock_escriba_deps():
    with patch("escriba.tb.Window") as mock_window:
        mock_window_instance = MagicMock()
        mock_window.return_value = mock_window_instance
        with patch("escriba.ConfigWindow"):
            with patch("escriba.FloatingMenu"):
                with patch("escriba.TooltipNotification"):
                    with patch("escriba.TrayIconManager"):
                        with (
                            patch("escriba.HotkeyManager", side_effect=lambda *a, **kw: MagicMock()),
                            patch("escriba.init_app"),
                            patch("escriba.configure_styles"),
                        ):
                            yield mock_window_instance


@pytest.fixture
def app(mock_escriba_deps):
    with (
        patch("escriba.pyperclip") as mock_pyperclip,
        patch("escriba.send_copy") as mock_send_ctrl_c,
        patch("escriba.time.sleep") as mock_sleep,
    ):
        eapp = EscribaApp()
        yield eapp, mock_pyperclip, mock_send_ctrl_c, mock_sleep


class TestSafePaste:
    def test_returns_clipboard_content(self, app):
        eapp, mock_pyperclip, _, _ = app
        mock_pyperclip.paste.return_value = "hello"
        assert eapp._safe_paste() == "hello"

    def test_handles_exception_gracefully(self, app):
        eapp, mock_pyperclip, _, _ = app
        mock_pyperclip.paste.side_effect = Exception("clipboard error")
        assert eapp._safe_paste() == ""


class TestSafeCopy:
    def test_calls_pyperclip_copy(self, app):
        eapp, mock_pyperclip, _, _ = app
        eapp._safe_copy("test text")
        mock_pyperclip.copy.assert_called_once_with("test text")

    def test_handles_exception_gracefully(self, app):
        eapp, mock_pyperclip, _, _ = app
        mock_pyperclip.copy.side_effect = Exception("copy error")
        eapp._safe_copy("test text")


class TestCaptureSelectedText:
    def test_captures_and_restores_clipboard(self, app):
        eapp, mock_pyperclip, mock_send, _ = app
        mock_pyperclip.paste.side_effect = ["original", "selected text"]

        result = eapp._capture_selected_text()

        assert result == "selected text"
        assert mock_pyperclip.copy.call_args_list == [call(""), call("original")]
        assert mock_send.call_count == 1

    def test_waits_until_clipboard_is_filled(self, app):
        eapp, mock_pyperclip, mock_send, _ = app
        mock_pyperclip.paste.side_effect = ["original", "", "", "selected"]

        result = eapp._capture_selected_text()

        assert result == "selected"
        assert mock_send.call_count == 1

    def test_no_selection_returns_empty_not_old_clipboard(self, app):
        eapp, mock_pyperclip, mock_send, _ = app
        mock_pyperclip.paste.side_effect = ["original"] + [""] * 100

        result = eapp._capture_selected_text()

        assert result == ""
        assert mock_send.call_count == 1
        assert mock_pyperclip.copy.call_args_list[-1] == call("original")

    def test_restores_empty_clipboard_after_capture(self, app):
        eapp, mock_pyperclip, mock_send, _ = app
        mock_pyperclip.paste.side_effect = ["", "selected text"]

        result = eapp._capture_selected_text()

        assert result == "selected text"
        assert mock_pyperclip.copy.call_args_list == [call(""), call("")]

    def test_preserves_non_text_clipboard_when_image_present(self, app):
        eapp, mock_pyperclip, mock_send, _ = app
        mock_pyperclip.paste.return_value = ""
        with patch("escriba.clipboard_has_non_text", return_value=True):
            result = eapp._capture_selected_text()

        assert result == ""
        assert mock_send.call_count == 1
        mock_pyperclip.copy.assert_not_called()

    def test_restores_clipboard_when_copy_fails(self, app):
        eapp, mock_pyperclip, mock_send, _ = app
        mock_pyperclip.paste.return_value = "original"
        mock_send.side_effect = RuntimeError("copy failed")

        with pytest.raises(RuntimeError, match="copy failed"):
            eapp._capture_selected_text()

        assert mock_pyperclip.copy.call_args_list == [call(""), call("original")]


class TestOnHotkey:
    def test_error_flag_shows_tooltip(self, app):
        eapp, _, _, _ = app

        eapp._on_hotkey(error=True)

        eapp.tooltip.show.assert_called_once()
        args = eapp.tooltip.show.call_args[0]
        assert "Error" in args[0]
        assert args[1] == "danger"

    def test_normal_flow_captures_and_shows_menu(self, app):
        eapp, mock_pyperclip, mock_send, mock_sleep = app
        mock_pyperclip.paste.side_effect = ["original", "selected text"]

        eapp._on_hotkey(error=False)

        assert mock_pyperclip.copy.call_args_list[-1] == call("original")
        eapp.root.after.assert_called_once_with(
            0, eapp.floating_menu.show, "selected text"
        )

    def test_lock_prevents_concurrent_execution(self, app):
        eapp, mock_pyperclip, mock_send, _ = app
        mock_pyperclip.paste.side_effect = ["original", "selected text"]
        eapp._lock.acquire(blocking=True)

        try:
            eapp._on_hotkey(error=False)
            assert mock_send.call_count == 0
            eapp.root.after.assert_not_called()
        finally:
            eapp._lock.release()

    def test_reload_hotkey_updates_tray(self, app):
        eapp, _, _, _ = app
        eapp.reload_hotkey("Ctrl+Alt+K", "Ctrl+Shift+R")
        eapp.hotkey.stop.assert_called_once()
        eapp.repeat_hotkey.stop.assert_called_once()
        eapp.tray.update_hotkey.assert_called_once()


class TestRepeatHotkeyAndWayland:
    def test_repeat_hotkey_runs_last_action_directly(self, app):
        eapp, mock_pyperclip, _, _ = app
        mock_pyperclip.paste.side_effect = ["orig", "texto nuevo"]
        eapp.remember_last_action(
            prompt="Resume para {app}",
            label="≡  Resumir",
            auto_replace=False,
            model="gemini-2.5-flash",
            temperature=0.3,
        )
        with (
            patch("escriba.get_foreground_window", return_value=42),
            patch("escriba.get_foreground_app_name", return_value="slack"),
        ):
            eapp._on_repeat_hotkey(error=False)

        eapp.root.after.assert_called_once()
        cb, prompt_arg, sel_arg, hwnd_arg, last_arg = eapp.root.after.call_args[0][1:]
        assert cb == eapp._launch_repeat
        assert prompt_arg == "Resume para slack"
        assert sel_arg == "texto nuevo"
        assert hwnd_arg == 42
        assert last_arg["label"] == "≡  Resumir"

    def test_repeat_hotkey_without_last_action_opens_menu(self, app):
        eapp, mock_pyperclip, _, _ = app
        mock_pyperclip.paste.side_effect = ["orig", "hola"]
        with patch("escriba.get_foreground_window", return_value=1):
            eapp._on_repeat_hotkey(error=False)
        eapp.root.after.assert_called_once_with(0, eapp.floating_menu.show, "hola")

    def test_repeat_hotkey_error_shows_tooltip(self, app):
        eapp, _, _, _ = app
        with patch("escriba.ConfigManager.get", return_value="Ctrl+Alt+R"):
            eapp._on_repeat_hotkey(error=True)
        eapp.tooltip.show.assert_called_once()
        assert eapp.tooltip.show.call_args[0][1] == "danger"

    def test_notify_wayland_shows_warning_tooltip(self, app):
        eapp, _, _, _ = app
        eapp._notify_wayland()
        eapp.tooltip.show.assert_called_once()
        msg, style, _ = eapp.tooltip.show.call_args[0]
        assert "Wayland" in msg
        assert style == "warning"


class TestQuitAppAndMain:
    def test_stops_all_components(self, app):
        eapp, _, _, _ = app

        with (
            patch("escriba.os._exit") as mock_exit,
            patch("escriba.release_single_instance") as mock_rel,
        ):
            eapp.quit_app()

            eapp.hotkey.stop.assert_called_once()
            eapp.repeat_hotkey.stop.assert_called_once()
            eapp.tray.stop.assert_called_once()
            eapp.floating_menu.hide.assert_called_once()
            eapp.tooltip.hide.assert_called_once()
            mock_rel.assert_called_once()
            eapp.root.quit.assert_called_once()
            eapp.root.destroy.assert_called_once()
            mock_exit.assert_called_once_with(0)

    def test_quit_handles_root_destroy_exception(self, app):
        eapp, _, _, _ = app
        eapp.root.destroy.side_effect = Exception("destroy error")

        with (
            patch("escriba.os._exit") as mock_exit,
            patch("escriba.release_single_instance"),
        ):
            eapp.quit_app()
            mock_exit.assert_called_once_with(0)

    def test_main_aborts_when_already_running(self):
        import sys

        mock_tk = MagicMock()
        with (
            patch.dict(sys.modules, {"tkinter": mock_tk, "tkinter.messagebox": mock_tk.messagebox}),
            patch("escriba.acquire_single_instance", return_value=False),
            patch("escriba.EscribaApp") as mock_app_cls,
        ):
            escriba.main()
        mock_app_cls.assert_not_called()
        mock_tk.messagebox.showinfo.assert_called_once()

    def test_main_starts_app_when_lock_acquired(self):
        with (
            patch("escriba.acquire_single_instance", return_value=True),
            patch("escriba.EscribaApp") as mock_app_cls,
        ):
            escriba.main()
        mock_app_cls.return_value.run.assert_called_once()
