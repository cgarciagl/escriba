import threading
from unittest.mock import MagicMock, patch

import pytest

from hotkey import (
    HotkeyManager,
    _KEYEVENTF_KEYUP,
    _release_modifiers,
    send_ctrl_c,
    send_ctrl_v,
)


class FakeMSG:
    def __init__(self):
        self.message = 0
        self.wParam = 0


@pytest.fixture
def mock_hotkey():
    with patch("hotkey.ctypes.windll") as windll:
        with patch("hotkey.ctypes.wintypes") as wintypes:
            with patch("hotkey.ctypes.byref", lambda x: x):
                with patch("hotkey.keyboard") as keyboard:
                    mock_msg = FakeMSG()
                    wintypes.MSG = lambda: mock_msg
                    yield {
                        "windll": windll,
                        "wintypes": wintypes,
                        "keyboard": keyboard,
                        "msg": mock_msg,
                    }


class TestReleaseModifiers:
    def test_releases_win_and_alt(self, mock_hotkey):
        _release_modifiers()

        calls = mock_hotkey["windll"].user32.keybd_event.call_args_list
        assert len(calls) == 3
        virtual_keys = [c[0][0] for c in calls]
        assert 0x5B in virtual_keys  # VK_LWIN
        assert 0x5C in virtual_keys  # VK_RWIN
        assert 0x12 in virtual_keys  # VK_MENU (Alt)
        for c in calls:
            assert c[0][2] == _KEYEVENTF_KEYUP


class TestSendCtrlC:
    @patch("hotkey._release_modifiers")
    @patch("hotkey.keyboard.send")
    def test_sends_ctrl_c_after_release(self, mock_send, mock_release):
        send_ctrl_c()
        mock_release.assert_called_once()
        mock_send.assert_called_once_with("ctrl+c")


class TestSendCtrlV:
    @patch("hotkey.keyboard.send")
    def test_sends_ctrl_v(self, mock_send):
        send_ctrl_v()
        mock_send.assert_called_once_with("ctrl+v")


class TestHotkeyManager:
    def test_start_registers_hotkey(self, mock_hotkey):
        root = MagicMock()
        callback = MagicMock()
        mock_hotkey["windll"].user32.RegisterHotKey.return_value = True
        mock_hotkey["windll"].user32.GetMessageW.return_value = 0

        hm = HotkeyManager(root, callback)
        hm.start()
        hm._thread.join(timeout=3)

        mock_hotkey["windll"].user32.RegisterHotKey.assert_called_once_with(
            None, 1, 0x0008 | 0x0001, 0x45
        )

    def test_start_triggers_callback_on_hotkey(self, mock_hotkey):
        root = MagicMock()
        callback = MagicMock()
        mock_hotkey["windll"].user32.RegisterHotKey.return_value = True

        getmessage_calls = [0]

        def mock_getmessage(msg_ptr, hwnd, min_msg, max_msg):
            getmessage_calls[0] += 1
            if getmessage_calls[0] == 1:
                msg_ptr.message = 0x0312
                msg_ptr.wParam = 1
                return 1
            return 0

        mock_hotkey["windll"].user32.GetMessageW.side_effect = mock_getmessage

        hm = HotkeyManager(root, callback)
        hm.start()
        hm._thread.join(timeout=3)

        callback.assert_called_once()

    def test_start_notifies_error_on_failed_register(self, mock_hotkey):
        root = MagicMock()
        callback = MagicMock()
        mock_hotkey["windll"].user32.RegisterHotKey.return_value = False

        hm = HotkeyManager(root, callback)
        hm.start()
        hm._thread.join(timeout=3)

        root.after.assert_called_once()
        scheduled = root.after.call_args[0][1]
        scheduled()
        callback.assert_called_once_with(error=True)

    def test_stop_posts_quit_message(self, mock_hotkey):
        root = MagicMock()
        callback = MagicMock()
        mock_hotkey["windll"].user32.RegisterHotKey.return_value = True
        mock_hotkey["windll"].user32.GetMessageW.return_value = 0

        hm = HotkeyManager(root, callback)
        hm.start()
        hm._thread.join(timeout=3)
        hm.stop()

        mock_hotkey["windll"].user32.PostThreadMessageW.assert_called_once()

    def test_unregisters_hotkey_on_loop_exit(self, mock_hotkey):
        root = MagicMock()
        callback = MagicMock()
        mock_hotkey["windll"].user32.RegisterHotKey.return_value = True
        mock_hotkey["windll"].user32.GetMessageW.return_value = 0

        hm = HotkeyManager(root, callback)
        hm.start()
        hm._thread.join(timeout=3)

        mock_hotkey["windll"].user32.UnregisterHotKey.assert_called_once_with(None, 1)

    def test_stop_is_safe_when_not_started(self, mock_hotkey):
        root = MagicMock()
        callback = MagicMock()

        hm = HotkeyManager(root, callback)
        hm.stop()
