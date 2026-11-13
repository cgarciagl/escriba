"""
Escriba — Historial de las últimas respuestas de la IA.

Se mantiene solo en memoria (no se escribe a disco) para no dejar copias del
texto del usuario; se pierde al cerrar la aplicación.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from constants import HISTORY_MAX_ITEMS


@dataclass(frozen=True)
class HistoryEntry:
    label: str
    prompt: str
    selected_text: str
    result: str
    provider: str
    timestamp: datetime = field(default_factory=datetime.now)
    model: str = ""

    def menu_title(self, width: int = 40) -> str:
        """Texto corto para el menú de la bandeja: "14:05 · Resumir · Lorem…"."""
        label = self.label.split("  ", 1)[-1].strip()
        preview = " ".join(self.result.split())
        if len(preview) > width:
            preview = preview[: width - 1] + "…"
        return f"{self.timestamp:%H:%M} · {label} · {preview}"


class History:
    """Cola acotada y segura entre hilos; la entrada más reciente va primero."""

    def __init__(self, max_items: int = HISTORY_MAX_ITEMS, on_change: Callable[[], None] | None = None):
        self._items: deque[HistoryEntry] = deque(maxlen=max_items)
        self._lock = threading.Lock()
        self.on_change = on_change  # p. ej. refrescar el menú de la bandeja

    def _notify(self):
        if self.on_change:
            try:
                self.on_change()
            except Exception:
                pass

    def add(self, label: str, prompt: str, selected_text: str, result: str, provider: str, model: str = "") -> HistoryEntry:
        entry = HistoryEntry(label, prompt, selected_text, result, provider, model=model)
        with self._lock:
            self._items.appendleft(entry)
        self._notify()
        return entry

    def entries(self) -> list[HistoryEntry]:
        with self._lock:
            return list(self._items)

    def clear(self):
        with self._lock:
            self._items.clear()
        self._notify()

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)
