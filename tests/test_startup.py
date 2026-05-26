import winreg
from unittest.mock import MagicMock, patch

import pytest

from constants import APP_NAME
from startup import StartupManager


class TestStartupManagerIsEnabled:
    @patch("startup.winreg.CloseKey")
    @patch("startup.winreg.OpenKey")
    @patch("startup.winreg.QueryValueEx")
    def test_is_enabled_returns_true(self, mock_query, mock_open, mock_close):
        mock_open.return_value = MagicMock()

        assert StartupManager.is_enabled() is True
        mock_open.assert_called_once()
        mock_query.assert_called_once()
        mock_close.assert_called_once()

    @patch("startup.winreg.OpenKey", side_effect=FileNotFoundError)
    def test_is_enabled_returns_false(self, mock_open):
        assert StartupManager.is_enabled() is False


class TestStartupManagerEnable:
    @patch("startup.winreg.OpenKey")
    @patch("startup.winreg.SetValueEx")
    @patch("startup.winreg.CloseKey")
    def test_enable_writes_to_registry(self, mock_close, mock_set, mock_open):
        mock_open.return_value = MagicMock()

        StartupManager.enable()

        mock_open.assert_called_once()
        mock_set.assert_called_once()
        assert mock_set.call_args[0][1] == APP_NAME
        assert mock_set.call_args[0][3] == winreg.REG_SZ
        mock_close.assert_called_once()

    @patch("startup.winreg.CloseKey")
    @patch("startup.winreg.OpenKey")
    @patch("startup.winreg.SetValueEx")
    def test_enable_sets_correct_value(self, mock_set, mock_open, mock_close):
        mock_open.return_value = MagicMock()

        StartupManager.enable()

        value = mock_set.call_args[0][4]
        assert "escriba" in value.lower()


class TestStartupManagerDisable:
    @patch("startup.winreg.OpenKey")
    @patch("startup.winreg.DeleteValue")
    @patch("startup.winreg.CloseKey")
    def test_disable_deletes_value(self, mock_close, mock_del, mock_open):
        mock_open.return_value = MagicMock()

        StartupManager.disable()

        mock_open.assert_called_once()
        mock_del.assert_called_once_with(mock_open.return_value, APP_NAME)
        mock_close.assert_called_once()

    @patch("startup.winreg.OpenKey", side_effect=FileNotFoundError)
    def test_disable_no_crash_when_missing(self, mock_open):
        StartupManager.disable()


class TestStartupManagerExePath:
    @patch("startup.sys")
    def test_frozen_returns_executable(self, mock_sys):
        mock_sys.frozen = True
        mock_sys.executable = "C:\\dist\\Escriba.exe"

        path = StartupManager._exe_path()
        assert path == "C:\\dist\\Escriba.exe"

    @patch("startup.sys")
    def test_non_frozen_returns_python_script(self, mock_sys):
        mock_sys.frozen = False
        mock_sys.executable = "C:\\Python\\python.exe"

        path = StartupManager._exe_path()
        assert "python.exe" in path
        assert "escriba.py" in path
