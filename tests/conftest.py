import ctypes
import os
import sys
from unittest.mock import MagicMock

# ─────────────────────────────────────────────────────────────
# Permite ejecutar la suite fuera de Windows (CI en Linux, etc.):
# se simulan los módulos exclusivos de Windows ANTES de importar la app.
# ─────────────────────────────────────────────────────────────
if sys.platform != "win32":
    sys.modules.setdefault("winreg", MagicMock())
    if not hasattr(ctypes, "windll"):
        ctypes.windll = MagicMock()
    for _mod in ("keyboard", "pystray"):
        sys.modules.setdefault(_mod, MagicMock())

# Algunas imágenes de CI traen Python sin Tk: en ese caso se simula la capa de UI
# (los tests de lógica no la necesitan; la UI se prueba en el runner de Windows).
try:
    import tkinter  # noqa: F401
except ImportError:
    for _mod in ("tkinter", "ttkbootstrap", "ttkbootstrap.constants", "ui_windows"):
        sys.modules.setdefault(_mod, MagicMock())

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from config import ConfigManager  # noqa: E402


@pytest.fixture(autouse=True)
def reset_config_cache(tmp_path, monkeypatch):
    # Ningún test debe leer ni escribir el config.json real del usuario.
    monkeypatch.setattr("config.CONFIG_FILE", str(tmp_path / "isolated" / "config.json"))
    monkeypatch.setattr("config.LEGACY_CONFIG_FILE", str(tmp_path / "no-legacy" / "config.json"))
    ConfigManager._cache = None
    yield
    ConfigManager._cache = None
