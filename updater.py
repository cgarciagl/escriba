"""
Escriba — Comprobación y descarga de actualizaciones desde GitHub Releases.

Revisa periódicamente (por defecto cada 24 h) si existe un release más reciente
en GitHub, verifica la integridad de la descarga (tamaño y SHA-256 si está
disponible) y reemplaza el ejecutable o bundle actual tras cerrar la app.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import zipfile
from dataclasses import dataclass
from typing import Callable

import requests

from config import ConfigManager
from constants import APP_VERSION, GITHUB_REPO, UPDATE_CHECK_INTERVAL

_GITHUB_API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
_REQUEST_TIMEOUT = 8
_DOWNLOAD_TIMEOUT = 60
_CHUNK_SIZE = 65536


class UpdateCancelled(Exception):
    """El usuario canceló la descarga de la actualización."""


@dataclass(frozen=True)
class ReleaseInfo:
    """Metadatos de una versión disponible en GitHub Releases."""

    version: str
    tag: str
    html_url: str
    asset_name: str
    asset_url: str
    asset_size: int = 0
    asset_sha256: str = ""


def parse_version(tag: str) -> tuple[int, ...]:
    """Convierte una etiqueta (ej. 'v0.0.6' o '1.2.3-beta') en tupla numérica."""
    cleaned = (tag or "").strip().lstrip("vV")
    nums = re.findall(r"\d+", cleaned.split("-", 1)[0].split("+", 1)[0])
    return tuple(int(n) for n in nums) if nums else (0,)


def is_newer_version(remote_tag: str, current_version: str = APP_VERSION) -> bool:
    """Devuelve True si `remote_tag` representa una versión mayor que `current_version`."""
    remote = parse_version(remote_tag)
    local = parse_version(current_version)
    length = max(len(remote), len(local))
    remote += (0,) * (length - len(remote))
    local += (0,) * (length - len(local))
    return remote > local


def platform_asset_name(platform: str | None = None) -> str:
    """Nombre esperado del artefacto en GitHub Releases para la plataforma actual."""
    plat = platform or sys.platform
    if plat == "win32":
        return "Escriba.exe"
    if plat == "darwin":
        return "Escriba-macos.zip"
    return "Escriba-linux.tar.gz"


def _macos_app_bundle(executable_path: str | None = None) -> str | None:
    """Si `executable_path` vive dentro de un .app, devuelve la ruta del bundle."""
    exe = os.path.abspath(executable_path or sys.executable)
    # .../Escriba.app/Contents/MacOS/Escriba -> .../Escriba.app
    bundle = os.path.abspath(os.path.join(os.path.dirname(exe), "..", ".."))
    return bundle if bundle.endswith(".app") else None


def can_self_update() -> bool:
    """Indica si la app corre empaquetada y tiene permisos para reemplazarse."""
    if not getattr(sys, "frozen", False):
        return False
    if sys.platform == "darwin":
        bundle = _macos_app_bundle()
        if not bundle or not os.path.isdir(bundle):
            return False
        return os.access(os.path.dirname(bundle), os.W_OK)
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    return os.access(exe_dir, os.W_OK)


def should_auto_check(now: float | None = None) -> bool:
    """Devuelve True si toca comprobar actualizaciones automáticamente al iniciar."""
    if not ConfigManager.get("auto_update_check", True):
        return False
    last_check = float(ConfigManager.get("last_update_check", 0) or 0)
    current = time.time() if now is None else now
    return (current - last_check) >= UPDATE_CHECK_INTERVAL


def check_for_update() -> tuple[ReleaseInfo | None, str | None]:
    """Consulta el último release en GitHub.

    Devuelve `(ReleaseInfo, None)` si hay una versión más reciente con artefacto
    compatible, `(None, None)` si ya está al día, o `(None, error)` si falló.
    """
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"Escriba/{APP_VERSION}",
    }
    try:
        resp = requests.get(_GITHUB_API_LATEST, headers=headers, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        return None, str(exc)

    try:
        ConfigManager.set("last_update_check", int(time.time()))
    except Exception:
        pass

    tag = (data.get("tag_name") or "").strip()
    if not tag or data.get("draft") or data.get("prerelease"):
        return None, None
    if not is_newer_version(tag, APP_VERSION):
        return None, None

    expected_asset = platform_asset_name()
    matched = next(
        (a for a in (data.get("assets") or []) if a.get("name") == expected_asset),
        None,
    )
    if not matched or not matched.get("browser_download_url"):
        return None, None

    digest = (matched.get("digest") or "").strip()
    sha256_hex = digest.split("sha256:", 1)[1].lower() if digest.startswith("sha256:") else ""

    return ReleaseInfo(
        version=tag.lstrip("vV"),
        tag=tag,
        html_url=data.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases/latest",
        asset_name=expected_asset,
        asset_url=matched["browser_download_url"],
        asset_size=int(matched.get("size") or 0),
        asset_sha256=sha256_hex,
    ), None


def download_and_prepare(
    info: ReleaseInfo,
    on_progress: Callable[[int | None], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> str:
    """Descarga el artefacto del release, valida su integridad y lo prepara en temp."""
    staging_dir = tempfile.mkdtemp(prefix="escriba_update_")
    download_path = os.path.join(staging_dir, info.asset_name)
    hasher = hashlib.sha256()

    try:
        headers = {"User-Agent": f"Escriba/{APP_VERSION}"}
        with requests.get(
            info.asset_url, headers=headers, stream=True, timeout=_DOWNLOAD_TIMEOUT
        ) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length") or info.asset_size or 0)
            downloaded = 0
            last_pct = -1

            with open(download_path, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=_CHUNK_SIZE):
                    if cancel_event and cancel_event.is_set():
                        raise UpdateCancelled("Actualización cancelada por el usuario.")
                    if not chunk:
                        continue
                    fh.write(chunk)
                    hasher.update(chunk)
                    downloaded += len(chunk)
                    if on_progress and total > 0:
                        pct = min(100, int(downloaded * 100 / total))
                        if pct != last_pct:
                            last_pct = pct
                            on_progress(pct)

        actual_size = os.path.getsize(download_path)
        if actual_size == 0 or (info.asset_size > 0 and actual_size != info.asset_size):
            raise RuntimeError("El archivo descargado está incompleto.")

        if info.asset_sha256 and hasher.hexdigest().lower() != info.asset_sha256:
            raise RuntimeError("La verificación SHA-256 de la descarga falló.")

        return _extract_prepared_target(download_path, staging_dir)
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise


def _extract_prepared_target(download_path: str, staging_dir: str) -> str:
    """Devuelve la ruta del nuevo binario o .app listo para reemplazar al actual."""
    if sys.platform == "win32":
        return download_path

    if sys.platform == "darwin":
        extract_dir = os.path.join(staging_dir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        if shutil.which("ditto"):
            subprocess.run(["ditto", "-xk", download_path, extract_dir], check=True)
        else:
            with zipfile.ZipFile(download_path, "r") as zf:
                zf.extractall(extract_dir)
        app_path = os.path.join(extract_dir, "Escriba.app")
        if not os.path.isdir(app_path):
            raise RuntimeError("No se encontró Escriba.app dentro del archivo descargado.")
        return app_path

    # Linux (.tar.gz con el binario `Escriba`)
    extract_dir = os.path.join(staging_dir, "extracted")
    os.makedirs(extract_dir, exist_ok=True)
    with tarfile.open(download_path, "r:gz") as tf:
        tf.extractall(extract_dir)
    bin_path = os.path.join(extract_dir, "Escriba")
    if not os.path.isfile(bin_path):
        raise RuntimeError("No se encontró el binario Escriba dentro del archivo descargado.")
    os.chmod(bin_path, 0o755)
    return bin_path


def apply_update_and_restart(prepared_path: str, on_quit: Callable[[], None]):
    """Lanza el reemplazador en segundo plano, cierra la app y relanza la nueva versión."""
    staging_dir = os.path.dirname(prepared_path)
    if sys.platform == "win32":
        _spawn_windows_replacer(prepared_path, os.path.abspath(sys.executable), staging_dir)
    elif sys.platform == "darwin":
        bundle = _macos_app_bundle()
        if not bundle:
            raise RuntimeError("No se pudo determinar la ruta de Escriba.app.")
        _spawn_macos_replacer(prepared_path, bundle, os.path.dirname(staging_dir))
    else:
        _spawn_linux_replacer(prepared_path, os.path.abspath(sys.executable), os.path.dirname(staging_dir))

    on_quit()


def _spawn_windows_replacer(new_exe: str, cur_exe: str, staging_dir: str):
    bat_path = os.path.join(staging_dir, "update_escriba.bat")
    script = (
        "@echo off\n"
        "setlocal\n"
        "set /a tries=0\n"
        "timeout /t 2 /nobreak >nul\n"
        ":retry\n"
        f'move /y "{new_exe}" "{cur_exe}" >nul 2>&1\n'
        "if errorlevel 1 (\n"
        "    set /a tries+=1\n"
        "    if %tries% GEQ 15 exit /b 1\n"
        "    timeout /t 1 /nobreak >nul\n"
        "    goto retry\n"
        ")\n"
        f'start "" "{cur_exe}"\n'
        f'rmdir /s /q "{staging_dir}" >nul 2>&1\n'
    )
    with open(bat_path, "w", encoding="utf-8") as fh:
        fh.write(script)

    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(
        ["cmd.exe", "/c", bat_path],
        creationflags=flags,
        close_fds=True,
    )


def _spawn_macos_replacer(new_app: str, cur_app: str, staging_dir: str):
    script = (
        "sleep 2\n"
        f'rm -rf "{cur_app}"\n'
        f'mv "{new_app}" "{cur_app}"\n'
        f'xattr -dr com.apple.quarantine "{cur_app}" 2>/dev/null || true\n'
        f'open "{cur_app}"\n'
        f'rm -rf "{staging_dir}"\n'
    )
    subprocess.Popen(["/bin/sh", "-c", script], start_new_session=True, close_fds=True)


def _spawn_linux_replacer(new_bin: str, cur_exe: str, staging_dir: str):
    script = (
        "sleep 1\n"
        f'mv -f "{new_bin}" "{cur_exe}"\n'
        f'chmod +x "{cur_exe}"\n'
        f'nohup "{cur_exe}" >/dev/null 2>&1 &\n'
        f'rm -rf "{staging_dir}"\n'
    )
    subprocess.Popen(["/bin/sh", "-c", script], start_new_session=True, close_fds=True)
