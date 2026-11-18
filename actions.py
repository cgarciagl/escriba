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
import re
import sys
import unicodedata
from datetime import datetime

import constants
from constants import AI_ACTIONS

ACTIONS_FILE = os.path.join(constants.CONFIG_DIR, "actions.json")

DEFAULT_SECTION = "Texto y Contenido"
DEFAULT_BOOTSTYLE = "info-outline"
VALID_MODES = ("selection", "compose", "both")

IS_MAC = sys.platform == "darwin"

# "Ctrl" es el modificador principal: en macOS se traduce a Command (⌘), que es
# la convención de la plataforma. "Cmd"/"Command" también se aceptan.
_MODIFIERS_WIN = {"ctrl": "Control", "control": "Control", "cmd": "Control", "command": "Control",
                  "alt": "Alt", "option": "Alt", "shift": "Shift"}
_MODIFIERS_MAC = {"ctrl": "Command", "control": "Command", "cmd": "Command", "command": "Command",
                  "alt": "Option", "option": "Option", "shift": "Shift"}
_MAC_SYMBOLS = {"Command": "⌘", "Option": "⌥", "Shift": "⇧"}

_INPUT_VAR_RE = re.compile(r"\{input:([^{}]+)\}")
_CODE_FENCE_RE = re.compile(r"^\s*```[^\n]*\n([\s\S]*?)\n?```\s*$")


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
        if item.get("auto_replace"):
            action["auto_replace"] = True
        if item.get("strip_markdown"):
            action["strip_markdown"] = True

        mode = str(item.get("mode") or "").strip().lower()
        if mode and mode != "selection":
            if mode in VALID_MODES:
                action["mode"] = mode
            else:
                warnings.append(f"'{label}': modo '{mode}' no válido; se usa 'selection'.")

        raw_temp = item.get("temperature")
        if raw_temp is not None and str(raw_temp).strip() != "":
            try:
                temp = float(raw_temp)
                if 0.0 <= temp <= 2.0:
                    action["temperature"] = round(temp, 2)
                else:
                    warnings.append(f"'{label}': temperatura fuera de rango (0.0–2.0); se ignora.")
            except (TypeError, ValueError):
                warnings.append(f"'{label}': temperatura '{raw_temp}' no válida; se ignora.")

        model = str(item.get("model") or "").strip()
        if model:
            action["model"] = model

        raw_apps = item.get("apps")
        if isinstance(raw_apps, str):
            apps_list = [p.strip().lower() for p in raw_apps.split(",") if p.strip()]
        elif isinstance(raw_apps, list):
            apps_list = [str(p).strip().lower() for p in raw_apps if str(p).strip()]
        else:
            apps_list = []
        if apps_list:
            action["apps"] = apps_list

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
    keys = ("label", "prompt", "section", "bootstyle", "shortcut", "mode", "model", "apps")
    out = []
    for a in actions:
        item = {k: a[k] for k in keys if a.get(k)}
        if a.get("auto_replace"):
            item["auto_replace"] = True
        if a.get("strip_markdown"):
            item["strip_markdown"] = True
        if a.get("temperature") is not None:
            item["temperature"] = a["temperature"]
        out.append(item)
    return out


def save_actions(actions: list[dict]) -> list[str]:
    """Valida y guarda las acciones en actions.json. Devuelve advertencias."""
    normalized, warnings = _normalize(actions)
    os.makedirs(os.path.dirname(ACTIONS_FILE), exist_ok=True)
    with open(ACTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(_serializable(normalized), f, indent=2, ensure_ascii=False)
    return warnings


def add_custom_action(
    label: str,
    prompt: str,
    mode: str = "both",
    section: str = "Personalizadas",
) -> list[str]:
    """Añade una nueva acción personalizada y la guarda en actions.json."""
    existing, _ = load_actions()
    used_labels = {a["label"] for a in existing}
    candidate = label.strip()
    if not candidate.startswith(("✨", "✎", "✏", "★")):
        candidate = f"✨  {candidate}"
    final_label = candidate
    n = 2
    while final_label in used_labels:
        final_label = f"{candidate} ({n})"
        n += 1
    new_action = {
        "label": final_label,
        "prompt": prompt.strip(),
        "section": section,
        "bootstyle": DEFAULT_BOOTSTYLE,
        "mode": mode,
    }
    return save_actions(existing + [new_action])


def action_matches_app(action: dict, app_name: str) -> bool:
    """Indica si una acción aplica a `app_name` (si no define 'apps', aplica a todas)."""
    patterns = action.get("apps")
    if not patterns:
        return True
    if not app_name:
        return True
    low = app_name.lower()
    return any(p in low for p in patterns)


def export_actions(path: str, actions: list[dict] | None = None):
    """Exporta las acciones dadas (o las activas) a un archivo JSON."""
    if actions is None:
        actions, _ = load_actions()
    normalized, _ = _normalize(actions)
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_serializable(normalized), f, indent=2, ensure_ascii=False)


def import_actions(path: str) -> tuple[list[dict], list[str]]:
    """Importa y valida un archivo JSON de acciones sin sobrescribir hasta guardar."""
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return _normalize(raw)


def strip_code_fences(text: str) -> str:
    """Elimina envoltorios ```lang ... ``` cuando el modelo responde con bloques Markdown."""
    m = _CODE_FENCE_RE.match(text or "")
    return m.group(1).strip() if m else text


def extract_prompt_inputs(prompt: str) -> list[str]:
    """Devuelve los nombres únicos de variables `{input:Etiqueta}` en orden de aparición."""
    seen: list[str] = []
    for name in _INPUT_VAR_RE.findall(prompt or ""):
        clean = name.strip()
        if clean and clean not in seen:
            seen.append(clean)
    return seen


def expand_prompt_vars(prompt: str, extra_vars: dict[str, str] | None = None) -> str:
    """Expande variables opcionales: {clipboard}, {lang}, {app}, {date}, {time}, {datetime}, {input:...}."""
    if "{clipboard}" in prompt:
        try:
            import pyperclip
            clip = pyperclip.paste() or ""
        except Exception:
            clip = ""
        prompt = prompt.replace("{clipboard}", clip)
    if "{lang}" in prompt:
        import locale
        lang = (locale.getlocale()[0] or "es").split("_")[0]
        prompt = prompt.replace("{lang}", lang)
    if "{app}" in prompt:
        app_val = (extra_vars or {}).get("app")
        if app_val is None:
            try:
                from plataforma import get_foreground_app_name

                app_val = get_foreground_app_name()
            except Exception:
                app_val = ""
        prompt = prompt.replace("{app}", app_val or "")
    if any(tok in prompt for tok in ("{date}", "{time}", "{datetime}")):
        now = datetime.now()
        prompt = (
            prompt.replace("{date}", now.strftime("%Y-%m-%d"))
            .replace("{time}", now.strftime("%H:%M"))
            .replace("{datetime}", now.strftime("%Y-%m-%d %H:%M"))
        )
    if extra_vars:
        def _repl(match):
            key = match.group(1).strip()
            return extra_vars.get(key, match.group(0))

        prompt = _INPUT_VAR_RE.sub(_repl, prompt)
    return prompt


def write_defaults(overwrite: bool = False) -> str:
    """Crea actions.json con las acciones predeterminadas y devuelve su ruta."""
    if overwrite or not os.path.exists(ACTIONS_FILE):
        os.makedirs(os.path.dirname(ACTIONS_FILE), exist_ok=True)
        with open(ACTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(_serializable(default_actions()), f, indent=2, ensure_ascii=False)
    return ACTIONS_FILE



# ─────────────────────────────────────────────────────────────
# Búsqueda en el menú (paleta de comandos)
# ─────────────────────────────────────────────────────────────
def normalize_text(text: str) -> str:
    """Minúsculas y sin acentos: "Traducir al Español" → "traducir al espanol"."""
    decomposed = unicodedata.normalize("NFD", text or "")
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn").lower().strip()


def action_name(action: dict) -> str:
    """Nombre sin el icono: "✎  Reescribir" → "Reescribir"."""
    parts = action["label"].split("  ", 1)
    return (parts[1] if len(parts) == 2 else parts[0]).strip()


def action_icon(action: dict) -> str:
    parts = action["label"].split("  ", 1)
    return parts[0].strip() if len(parts) == 2 else "•"


def filter_actions(actions: list[dict], query: str) -> list[dict]:
    """Filtra por nombre o sección; todas las palabras de la búsqueda deben aparecer.

    Las coincidencias al inicio del nombre van primero; el resto conserva el orden.
    """
    words = normalize_text(query).split()
    if not words:
        return list(actions)
    starts, contains = [], []
    for action in actions:
        name = normalize_text(action_name(action))
        haystack = f"{name} {normalize_text(action.get('section', ''))}"
        if all(w in haystack for w in words):
            (starts if name.startswith(words[0]) else contains).append(action)
    return starts + contains
