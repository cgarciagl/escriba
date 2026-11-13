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
    sys.modules.setdefault("keyboard", MagicMock())
    try:
        import pystray  # noqa: F401
    except ImportError:
        sys.modules.setdefault("pystray", MagicMock())

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
    # Nunca tocar el Llavero ni DPAPI reales; los tests que lo necesitan lo simulan.
    monkeypatch.setattr("config._keychain_available", lambda: False)
    monkeypatch.setattr("config._dpapi_available", lambda: False)
    ConfigManager._cache = None
    yield
    ConfigManager._cache = None
