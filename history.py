"""
Escriba — Historial de las últimas respuestas de la IA.

Soporta almacenamiento en memoria o persistencia opcional en disco (history.json
con permisos restringidos 0600 en POSIX).
"""

from __future__ import annotations

import json
import os
import tempfile
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

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "prompt": self.prompt,
            "selected_text": self.selected_text,
            "result": self.result,
            "provider": self.provider,
            "timestamp": self.timestamp.isoformat(),
            "model": self.model,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> HistoryEntry:
        ts_raw = raw.get("timestamp")
        try:
            ts = datetime.fromisoformat(ts_raw) if isinstance(ts_raw, str) else datetime.now()
        except ValueError:
            ts = datetime.now()
        return cls(
            label=str(raw.get("label", "")),
            prompt=str(raw.get("prompt", "")),
            selected_text=str(raw.get("selected_text", "")),
            result=str(raw.get("result", "")),
            provider=str(raw.get("provider", "")),
            timestamp=ts,
            model=str(raw.get("model", "")),
        )


class History:
    """Cola acotada y segura entre hilos; la entrada más reciente va primero."""

    def __init__(
        self,
        max_items: int = HISTORY_MAX_ITEMS,
        on_change: Callable[[], None] | None = None,
        storage_path: str | None = None,
    ):
        self._items: deque[HistoryEntry] = deque(maxlen=max_items)
        self._lock = threading.Lock()
        self.on_change = on_change  # p. ej. refrescar el menú de la bandeja
        self._storage_path = storage_path
        if storage_path:
            self.load()

    def _notify(self):
        if self.on_change:
            try:
                self.on_change()
            except Exception:
                pass

    def _save_locked(self):
        if not self._storage_path:
            return
        try:
            directory = os.path.dirname(os.path.abspath(self._storage_path))
            if directory:
                os.makedirs(directory, exist_ok=True)
            payload = [entry.to_dict() for entry in self._items]
            fd, tmp_path = tempfile.mkstemp(
                prefix=".history_", suffix=".tmp", dir=directory or "."
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2, ensure_ascii=False)
                if os.name != "nt":
                    os.chmod(tmp_path, 0o600)
                os.replace(tmp_path, self._storage_path)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        except Exception:
            pass

    def _remove_file_locked(self, path: str | None):
        if path and os.path.exists(path):
            try:
                os.unlink(path)
            except OSError:
                pass

    def load(self):
        if not self._storage_path or not os.path.exists(self._storage_path):
            return
        try:
            with open(self._storage_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if not isinstance(raw, list):
                return
            loaded = [
                HistoryEntry.from_dict(item)
                for item in raw
                if isinstance(item, dict) and item.get("result") is not None
            ]
            with self._lock:
                self._items.clear()
                for entry in loaded[: self._items.maxlen]:
                    self._items.append(entry)
        except Exception:
            pass

    def set_storage_path(self, storage_path: str | None, clear_disk: bool = False):
        with self._lock:
            prev = self._storage_path
            self._storage_path = storage_path
            if clear_disk:
                self._remove_file_locked(prev)
            elif storage_path:
                self._save_locked()

    def add(
        self,
        label: str,
        prompt: str,
        selected_text: str,
        result: str,
        provider: str,
        model: str = "",
    ) -> HistoryEntry:
        entry = HistoryEntry(label, prompt, selected_text, result, provider, model=model)
        with self._lock:
            self._items.appendleft(entry)
            self._save_locked()
        self._notify()
        return entry

    def entries(self) -> list[HistoryEntry]:
        with self._lock:
            return list(self._items)

    def clear(self):
        with self._lock:
            self._items.clear()
            self._remove_file_locked(self._storage_path)
        self._notify()

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)
