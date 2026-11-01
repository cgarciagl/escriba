"""
Escriba — Persistencia de configuración (config.json).

- El archivo vive en %APPDATA%\\Escriba\\config.json (ver constants.CONFIG_DIR).
  Si existe un config.json en la ubicación anterior (junto al .exe) se migra.
- Los secretos (API Keys) se guardan:
    Windows → cifrados con DPAPI (CryptProtectData) dentro de config.json
    macOS   → en el Llavero (config.json no contiene la clave)
    otros   → en texto plano (solo desarrollo / CI)
"""

import base64
import ctypes
import json
import os
import shutil
import sys

import constants
from constants import GEMINI_DEFAULT_MODEL

# Alias a nivel de módulo (los tests los sustituyen con monkeypatch).
CONFIG_FILE = constants.CONFIG_FILE
LEGACY_CONFIG_FILE = constants.LEGACY_CONFIG_FILE



# ─────────────────────────────────────────────────────────────
# DPAPI (Windows) vía ctypes — sin dependencias externas
# ─────────────────────────────────────────────────────────────
def _dpapi_available() -> bool:
    return sys.platform == "win32"


def _keychain_available() -> bool:
    return sys.platform == "darwin"


def keychain_get(name: str) -> str:
    from macos import keychain_get as _get
    return _get(name)


def keychain_set(name: str, value: str):
    from macos import keychain_set as _set
    _set(name, value)


def _dpapi(data: bytes, protect: bool) -> bytes:
    import ctypes.wintypes as wt

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    func = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    if not func(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise OSError("DPAPI: no se pudo procesar la API Key.")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def encrypt_secret(value: str) -> str:
    return base64.b64encode(_dpapi(value.encode("utf-8"), protect=True)).decode("ascii")


def decrypt_secret(value: str) -> str:
    return _dpapi(base64.b64decode(value), protect=False).decode("utf-8")


# ─────────────────────────────────────────────────────────────
# ConfigManager
# ─────────────────────────────────────────────────────────────
class ConfigManager:
    """Lee y escribe la configuración de la app en disco."""

    _cache: dict | None = None

    @staticmethod
    def _migrate_legacy_file():
        """Copia el config.json de la ubicación anterior (junto al .exe) si aplica."""
        if (
            not os.path.exists(CONFIG_FILE)
            and os.path.abspath(LEGACY_CONFIG_FILE) != os.path.abspath(CONFIG_FILE)
            and os.path.exists(LEGACY_CONFIG_FILE)
        ):
            try:
                os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
                shutil.copy2(LEGACY_CONFIG_FILE, CONFIG_FILE)
            except OSError:
                pass

    @classmethod
    def load(cls) -> dict:
        if cls._cache is not None:
            return cls._cache
        cls._migrate_legacy_file()
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cls._cache = json.load(f)
                    return cls._cache
            except Exception:
                pass
        # Primer arranque: crear config por defecto.
        # El inicio automático es opt-in: se activa desde la ventana de Configuración.
        default_config = {
            "api_key": "",
            "model": GEMINI_DEFAULT_MODEL,
            "autostart": False,
        }
        cls.save(default_config)
        cls._cache = default_config
        return default_config

    @classmethod
    def save(cls, data: dict):
        cls._cache = data
        directory = os.path.dirname(CONFIG_FILE)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @classmethod
    def get(cls, key: str, default=None):
        return cls.load().get(key, default)

    @classmethod
    def set(cls, key: str, value):
        data = cls.load()
        data[key] = value
        cls.save(data)

    # ── Secretos (cifrados con DPAPI en Windows) ────────────
    # Cada secreto `name` se guarda como `name_enc` (DPAPI, Windows), en el
    # Llavero con la marca `name_keychain` (macOS) o como `name` en texto plano.
    @classmethod
    def get_secret(cls, name: str) -> str:
        data = cls.load()
        if _keychain_available() and data.get(f"{name}_keychain"):
            try:
                return keychain_get(name)
            except Exception:
                return ""
        encrypted = data.get(f"{name}_enc")
        if encrypted:
            try:
                return decrypt_secret(encrypted)
            except Exception:
                return ""
        plain = data.get(name, "") or ""
        # Migración: un secreto guardado en texto plano se protege en cuanto se lee.
        if plain and (_dpapi_available() or _keychain_available()):
            try:
                cls.set_secret(name, plain)
            except Exception:
                pass
        return plain

    @classmethod
    def set_secret(cls, name: str, value: str):
        data = cls.load()
        value = (value or "").strip()
        data.pop(f"{name}_enc", None)
        data.pop(f"{name}_keychain", None)
        if _keychain_available():
            keychain_set(name, value)
            data[name] = ""
            if value:
                data[f"{name}_keychain"] = True  # marca: el valor está en el Llavero
        elif value and _dpapi_available():
            data[f"{name}_enc"] = encrypt_secret(value)
            data[name] = ""
        else:
            data[name] = value
        cls.save(data)

    @classmethod
    def get_api_key(cls) -> str:
        """API Key de Google Gemini."""
        return cls.get_secret("api_key")

    @classmethod
    def set_api_key(cls, key: str):
        cls.set_secret("api_key", key)

    @classmethod
    def get_openai_api_key(cls) -> str:
        """API Key del proveedor compatible con OpenAI (opcional para Ollama)."""
        return cls.get_secret("openai_api_key")

    @classmethod
    def set_openai_api_key(cls, key: str):
        cls.set_secret("openai_api_key", key)

    @classmethod
    def is_configured(cls) -> bool:
        return bool(cls.get_api_key().strip())

    @classmethod
    def get_model(cls) -> str:
        return cls.get("model", GEMINI_DEFAULT_MODEL)

    @classmethod
    def set_model(cls, model_name: str):
        cls.set("model", model_name)
