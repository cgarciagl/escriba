"""
Escriba — Persistencia de configuración (config.json).

- El archivo vive en %APPDATA%\\Escriba\\config.json (ver constants.CONFIG_DIR).
  Si existe un config.json en la ubicación anterior (junto al .exe) se migra.
- La API Key se guarda cifrada con DPAPI de Windows (CryptProtectData), ligada
  a la cuenta del usuario. Fuera de Windows se guarda en texto plano.
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

_ENC_KEY = "api_key_enc"


# ─────────────────────────────────────────────────────────────
# DPAPI (Windows) vía ctypes — sin dependencias externas
# ─────────────────────────────────────────────────────────────
def _dpapi_available() -> bool:
    return sys.platform == "win32"


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

    # ── API Key (cifrada con DPAPI en Windows) ──────────────
    @classmethod
    def get_api_key(cls) -> str:
        data = cls.load()
        encrypted = data.get(_ENC_KEY)
        if encrypted:
            try:
                return decrypt_secret(encrypted)
            except Exception:
                return ""
        plain = data.get("api_key", "") or ""
        # Migración: una clave guardada en texto plano se cifra en cuanto se lee.
        if plain and _dpapi_available():
            try:
                cls.set_api_key(plain)
            except Exception:
                pass
        return plain

    @classmethod
    def set_api_key(cls, key: str):
        data = cls.load()
        key = (key or "").strip()
        if key and _dpapi_available():
            data[_ENC_KEY] = encrypt_secret(key)
            data["api_key"] = ""
        else:
            data.pop(_ENC_KEY, None)
            data["api_key"] = key
        cls.save(data)

    @classmethod
    def is_configured(cls) -> bool:
        return bool(cls.get_api_key().strip())

    @classmethod
    def get_model(cls) -> str:
        return cls.get("model", GEMINI_DEFAULT_MODEL)

    @classmethod
    def set_model(cls, model_name: str):
        cls.set("model", model_name)
