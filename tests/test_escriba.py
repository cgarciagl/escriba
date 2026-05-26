import threading
from unittest.mock import MagicMock, patch

import pytest

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
                        with patch("escriba.HotkeyManager"):
                            yield mock_window_instance


@pytest.fixture
def app(mock_escriba_deps):
    with (
        patch("escriba.pyperclip") as mock_pyperclip,
        patch("escriba.send_ctrl_c") as mock_send_ctrl_c,
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
        mock_pyperclip.copy.assert_called_once_with("original")
        assert mock_send.call_count == 1

    def test_retry_on_same_text(self, app):
        eapp, mock_pyperclip, mock_send, _ = app
        mock_pyperclip.paste.side_effect = ["same", "same", "different"]

        result = eapp._capture_selected_text()

        assert result == "different"
        assert mock_send.call_count == 2
        mock_pyperclip.copy.assert_called_once_with("same")

    def test_no_restore_when_original_empty(self, app):
        eapp, mock_pyperclip, mock_send, _ = app
        mock_pyperclip.paste.side_effect = ["", "selected text"]

        result = eapp._capture_selected_text()

        assert result == "selected text"
        mock_pyperclip.copy.assert_not_called()


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

        mock_pyperclip.copy.assert_called_once_with("original")
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


class TestQuitApp:
    def test_stops_all_components(self, app):
        eapp, _, _, _ = app

        with patch("escriba.os._exit") as mock_exit:
            eapp.quit_app()

            eapp.hotkey.stop.assert_called_once()
            eapp.tray.stop.assert_called_once()
            eapp.floating_menu.hide.assert_called_once()
            eapp.tooltip.hide.assert_called_once()
            eapp.root.quit.assert_called_once()
            eapp.root.destroy.assert_called_once()
            mock_exit.assert_called_once_with(0)

    def test_quit_handles_root_destroy_exception(self, app):
        eapp, _, _, _ = app
        eapp.root.destroy.side_effect = Exception("destroy error")

        with patch("escriba.os._exit") as mock_exit:
            eapp.quit_app()
            mock_exit.assert_called_once_with(0)
