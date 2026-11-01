"""
Escriba — Acciones de IA configurables por el usuario.

Las acciones se leen de %APPDATA%\\Escriba\\actions.json. Si el archivo no existe
se usan las predeterminadas (constants.AI_ACTIONS); el archivo solo se crea
cuando el usuario decide editarlas desde la ventana de Configuración.

Formato de cada acción (JSON):
    {
      "label":     "✎  Reescribir",          # obligatorio (icono + dos espacios + texto)
      "prompt":    "Reescribe el texto…",    # obligatorio
      "section":   "Texto y Contenido",      # opcional
      "bootstyle": "info-outline",           # opcional (estilo ttkbootstrap)
      "shortcut":  "Ctrl+R"                  # opcional (Ctrl/Alt/Shift + tecla; en macOS Ctrl = ⌘)
    }
"""

from __future__ import annotations

import copy
import json
import os
import sys

import constants
from constants import AI_ACTIONS

ACTIONS_FILE = os.path.join(constants.CONFIG_DIR, "actions.json")

DEFAULT_SECTION = "Texto y Contenido"
DEFAULT_BOOTSTYLE = "info-outline"

IS_MAC = sys.platform == "darwin"

# "Ctrl" es el modificador principal: en macOS se traduce a Command (⌘), que es
# la convención de la plataforma. "Cmd"/"Command" también se aceptan.
_MODIFIERS_WIN = {"ctrl": "Control", "control": "Control", "cmd": "Control", "command": "Control",
                  "alt": "Alt", "option": "Alt", "shift": "Shift"}
_MODIFIERS_MAC = {"ctrl": "Command", "control": "Command", "cmd": "Command", "command": "Command",
                  "alt": "Option", "option": "Option", "shift": "Shift"}
_MAC_SYMBOLS = {"Command": "⌘", "Option": "⌥", "Shift": "⇧"}


def _split(shortcut: str, mac: bool):
    """Devuelve (modificadores Tk, tecla Tk) o None si el atajo no es válido."""
    if not shortcut or not isinstance(shortcut, str):
        return None
    parts = [p.strip() for p in shortcut.split("+") if p.strip()]
    if len(parts) < 2:
        return None
    *mods, key = parts
    table = _MODIFIERS_MAC if mac else _MODIFIERS_WIN
    tk_mods: list[str] = []
    for m in mods:
        name = table.get(m.lower())
        if not name or name in tk_mods:
            return None
        tk_mods.append(name)
    if len(key) == 1 and key.isalnum():
        key = key.lower()
    elif key.upper() in {f"F{i}" for i in range(1, 13)}:
        key = key.upper()
    else:
        return None
    return tk_mods, key


def shortcut_to_tk(shortcut: str, mac: bool | None = None) -> str | None:
    """Convierte "Ctrl+R" → "<Control-r>" (o "<Command-r>" en macOS).

    Devuelve None si no es válido. Se exige al menos un modificador para que una
    tecla suelta no dispare acciones por accidente.
    """
    parsed = _split(shortcut, IS_MAC if mac is None else mac)
    if parsed is None:
        return None
    tk_mods, key = parsed
    return "<" + "-".join(tk_mods + [key]) + ">"


def display_shortcut(shortcut: str, mac: bool | None = None) -> str:
    """Texto a mostrar: "Ctrl+R" en Windows, "⌘R" en macOS."""
    mac = IS_MAC if mac is None else mac
    parsed = _split(shortcut, mac)
    if parsed is None or not mac:
        return shortcut
    tk_mods, key = parsed
    return "".join(_MAC_SYMBOLS[m] for m in tk_mods) + key.upper()


def _normalize(raw: list) -> tuple[list[dict], list[str]]:
    """Valida y completa las acciones. Devuelve (acciones, advertencias)."""
    if not isinstance(raw, list):
        raise ValueError("El archivo debe contener una lista de acciones.")

    actions: list[dict] = []
    warnings: list[str] = []
    used_keys: set[str] = set()

    for i, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            warnings.append(f"Acción {i}: no es un objeto; se omite.")
            continue
        label = str(item.get("label", "")).strip()
        prompt = str(item.get("prompt", "")).strip()
        if not label or not prompt:
            warnings.append(f"Acción {i}: requiere 'label' y 'prompt'; se omite.")
            continue

        action = {
            "label": label,
            "prompt": prompt,
            "section": str(item.get("section") or DEFAULT_SECTION).strip(),
            "bootstyle": str(item.get("bootstyle") or DEFAULT_BOOTSTYLE).strip(),
            "shortcut": "",
            "shortcut_key": None,
        }

        shortcut = str(item.get("shortcut") or "").strip()
        if shortcut:
            tk_key = shortcut_to_tk(shortcut)
            if tk_key is None:
                warnings.append(f"'{label}': atajo '{shortcut}' no válido; se ignora.")
            elif tk_key in used_keys:
                warnings.append(f"'{label}': atajo '{shortcut}' repetido; se ignora.")
            else:
                used_keys.add(tk_key)
                action["shortcut"] = shortcut
                action["shortcut_key"] = tk_key
        actions.append(action)

    if not actions:
        raise ValueError("No hay ninguna acción válida.")
    return actions, warnings


def default_actions() -> list[dict]:
    actions, _ = _normalize(copy.deepcopy(AI_ACTIONS))
    return actions


def load_actions() -> tuple[list[dict], list[str]]:
    """Carga las acciones del usuario (o las predeterminadas).

    Nunca lanza excepción: ante un archivo inválido devuelve las predeterminadas
    y una advertencia que la UI puede mostrar.
    """
    if not os.path.exists(ACTIONS_FILE):
        return default_actions(), []
    try:
        with open(ACTIONS_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return _normalize(raw)
    except Exception as exc:
        return default_actions(), [
            f"No se pudo leer actions.json ({exc}). Se usan las acciones predeterminadas."
        ]


def _serializable(actions: list[dict]) -> list[dict]:
    keys = ("label", "prompt", "section", "bootstyle", "shortcut")
    return [{k: a[k] for k in keys if a.get(k)} for a in actions]


def write_defaults(overwrite: bool = False) -> str:
    """Crea actions.json con las acciones predeterminadas y devuelve su ruta."""
    if overwrite or not os.path.exists(ACTIONS_FILE):
        os.makedirs(os.path.dirname(ACTIONS_FILE), exist_ok=True)
        with open(ACTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(_serializable(default_actions()), f, indent=2, ensure_ascii=False)
    return ACTIONS_FILE
