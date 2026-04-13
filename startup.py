"""
Escriba — Gestión del arranque automático con Windows (Registro).
"""

import os
import sys
import winreg

from constants import APP_NAME, STARTUP_KEY


class StartupManager:
    """Registra/desregistra la app en el registro de Windows para auto-inicio."""

    @staticmethod
    def _exe_path() -> str:
        """Ruta al ejecutable actual."""
        if getattr(sys, "frozen", False):
            return sys.executable
        return f'"{sys.executable}" "{os.path.abspath(__file__)}"'

    @staticmethod
    def is_enabled() -> bool:
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0, winreg.KEY_READ
            )
            winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return False

    @staticmethod
    def enable():
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ,
                          StartupManager._exe_path())
        winreg.CloseKey(key)

    @staticmethod
    def disable():
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0, winreg.KEY_SET_VALUE
            )
            winreg.DeleteValue(key, APP_NAME)
            winreg.CloseKey(key)
        except FileNotFoundError:
            pass
