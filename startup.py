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
            return f'"{sys.executable}"' if " " in sys.executable else sys.executable
        # En desarrollo, apuntar a escriba.py
        main_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "escriba.py")
        return f'"{sys.executable}" "{main_script}"'

    @staticmethod
    def is_enabled() -> bool:
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0, winreg.KEY_READ
            )
        except FileNotFoundError:
            return False
        try:
            winreg.QueryValueEx(key, APP_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)

    @staticmethod
    def enable():
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0, winreg.KEY_SET_VALUE
        )
        try:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ,
                              StartupManager._exe_path())
        finally:
            winreg.CloseKey(key)

    @staticmethod
    def disable():
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0, winreg.KEY_SET_VALUE
            )
        except FileNotFoundError:
            return
        try:
            winreg.DeleteValue(key, APP_NAME)
        except FileNotFoundError:
            pass
        finally:
            winreg.CloseKey(key)
