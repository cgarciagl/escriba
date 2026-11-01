"""
Escriba — Clientes de IA.

- GeminiClient: API oficial de Google Gemini.
- OpenAICompatibleClient: cualquier servidor con la API de OpenAI
  (Ollama local, OpenAI, OpenRouter, LM Studio…).
- generate_text(): punto de entrada único para la UI. Usa el proveedor
  configurado y, si está habilitado, recurre al otro cuando el primero falla.

Ambos clientes:
- Envían las instrucciones de la acción como *system instruction*, separadas
  del texto del usuario (reduce la inyección de prompt desde el texto).
- Admiten streaming: si se pasa `on_chunk`, cada fragmento se entrega en cuanto
  llega y la función devuelve el texto completo al final.
- Reintentan errores transitorios con retroceso exponencial y jitter. Con
  streaming solo se reintenta si todavía no se entregó ningún fragmento.
"""

from __future__ import annotations

import json
import random
import time
from typing import Callable, Iterator

import requests

from constants import (
    GEMINI_BASE,
    GEMINI_DEFAULT_MODEL,
    GEMINI_FALLBACK_MODELS,
    OPENAI_DEFAULT_BASE_URL,
    OPENAI_DEFAULT_MODEL,
)
from config import ConfigManager

RetryCallback = Callable[[int, int, float, str], None]
ChunkCallback = Callable[[str], None]

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
RETRYABLE_KEYWORDS = (
    "overloaded",
    "busy",
    "ocupado",
    "resource has been exhausted",
    "resource_exhausted",
    "quota",
    "rate limit",
    "demasiadas solicitudes",
    "temporarily unavailable",
    "try again later",
    "high traffic",
    "capacity",
    "servicio temporalmente no disponible",
)
BUSY_MARKERS = ("el modelo está ocupado", "the model is overloaded")

BACKOFF_MULTIPLIER = 2.0


def is_retryable_error(exc: Exception) -> tuple[bool, str]:
    """Determina si una excepción corresponde a un fallo transitorio o de saturación."""
    if isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
        return True, "Problema temporal de conexión"

    if isinstance(exc, requests.exceptions.HTTPError):
        status_code = getattr(exc.response, "status_code", 0)
        if status_code in RETRYABLE_STATUS_CODES:
            err_msg = ""
            try:
                err_json = exc.response.json()
                err_msg = err_json.get("error", {}).get("message", "")
            except Exception:
                err_msg = exc.response.text if exc.response is not None else ""
            return True, err_msg or f"HTTP {status_code}"

        body_text = (exc.response.text or "").lower() if exc.response is not None else ""
        if any(kw in body_text for kw in RETRYABLE_KEYWORDS):
            return True, "Modelo ocupado"

    if isinstance(exc, RuntimeError):
        msg_lower = str(exc).lower()
        if any(kw in msg_lower for kw in RETRYABLE_KEYWORDS):
            return True, str(exc)

    return False, ""


# ─────────────────────────────────────────────────────────────
# Utilidades compartidas
# ─────────────────────────────────────────────────────────────
def backoff_delay(base_delay: float, attempt: int) -> float:
    """Retroceso exponencial con jitter."""
    return base_delay * (BACKOFF_MULTIPLIER ** (attempt - 1)) + random.uniform(0.1, 0.4)


def iter_sse_data(response) -> Iterator[str]:
    """Itera los campos `data:` de una respuesta Server-Sent Events."""
    for line in response.iter_lines(decode_unicode=True):
        if line and line.startswith("data:"):
            yield line[5:].strip()


def to_user_error(exc: Exception, retries: int, name: str, short: str) -> Exception:
    """Convierte la excepción final en un mensaje legible para el usuario."""
    if isinstance(exc, requests.exceptions.HTTPError):
        status_code = getattr(exc.response, "status_code", 0)
        error_details = ""
        try:
            err_json = exc.response.json()
            if "error" in err_json and "message" in err_json["error"]:
                error_details = f": {err_json['error']['message']}"
        except Exception:
            text = getattr(exc.response, "text", "") or ""
            error_details = f": {text[:200]}" if text else ""

        low = error_details.lower()
        if status_code in (429, 503) or "overload" in low or "exhaust" in low:
            return RuntimeError(
                f"El modelo de {short} está ocupado o con límite de uso excedido (HTTP {status_code}){error_details}. "
                f"Reintentos agotados ({retries}/{retries})."
            )
        return RuntimeError(f"{short} HTTP {status_code}{error_details}")

    if isinstance(exc, requests.exceptions.ConnectionError):
        return RuntimeError(f"Error de red: No se pudo conectar a {name}. Revisa tu conexión a internet.")
    if isinstance(exc, requests.exceptions.Timeout):
        return RuntimeError(f"Tiempo de espera agotado al conectar con {name}.")
    if isinstance(exc, (RuntimeError, ValueError)):
        # Errores propios (respuesta vacía, modelo ocupado…): ya son legibles.
        return exc
    return RuntimeError(f"{short}: {exc}")


def run_with_retries(
    attempt_fn: Callable[[ChunkCallback | None], str],
    retries: int,
    base_delay: float,
    on_retry: RetryCallback | None,
    on_chunk: ChunkCallback | None,
    name: str,
    short: str,
) -> str:
    """Ejecuta `attempt_fn` con reintentos. No reintenta si ya se emitió streaming."""
    emitted = False

    def chunk_proxy(piece: str):
        nonlocal emitted
        if piece:
            emitted = True
            on_chunk(piece)

    for attempt in range(1, retries + 1):
        try:
            return attempt_fn(chunk_proxy if on_chunk else None)
        except Exception as exc:
            retryable, reason = is_retryable_error(exc)
            if retryable and not emitted and attempt < retries:
                delay = backoff_delay(base_delay, attempt)
                if on_retry:
                    on_retry(attempt, retries, delay, reason)
                time.sleep(delay)
                continue
            raise to_user_error(exc, retries, name, short) from exc

    raise RuntimeError(f"{short}: no se realizó ningún intento (max_retries < 1).")


def _check_not_busy(text: str):
    if any(kw in text.lower() for kw in BUSY_MARKERS):
        raise RuntimeError(text)


# ─────────────────────────────────────────────────────────────
# Cliente Google Gemini — API oficial
# ─────────────────────────────────────────────────────────────
class GeminiClient:
    """Llama a la API oficial de Google Gemini con gestión de modelos y reintentos automáticos."""

    NAME = "Google Gemini"
    SHORT = "Gemini"
    MAX_RETRIES = 3
    INITIAL_BACKOFF = 2.0

    @staticmethod
    def is_configured() -> bool:
        return bool(ConfigManager.get_api_key().strip())

    @classmethod
    def fetch_available_models(cls, api_key: str | None = None) -> list[str]:
        """Descarga la lista de modelos Gemini válidos para generateContent."""
        key = api_key or ConfigManager.get_api_key()
        if not key:
            return list(GEMINI_FALLBACK_MODELS)

        try:
            response = requests.get(GEMINI_BASE, headers={"x-goog-api-key": key}, timeout=10)
            response.raise_for_status()
            raw_models = response.json().get("models", [])
            valid_models = []

            # Excluir modelos especializados que no son de generación de texto general
            excluded_keywords = [
                "tts", "image", "transcribe", "robotics", "computer-use", "customtools"
            ]

            for m in raw_models:
                methods = m.get("supportedGenerationMethods", [])
                name = m.get("name", "").replace("models/", "").strip()
                if "generateContent" in methods and name.startswith("gemini"):
                    if not any(kw in name.lower() for kw in excluded_keywords):
                        valid_models.append(name)

            if not valid_models:
                return list(GEMINI_FALLBACK_MODELS)

            # El modelo predeterminado siempre va al principio
            if GEMINI_DEFAULT_MODEL in valid_models:
                valid_models.remove(GEMINI_DEFAULT_MODEL)
            valid_models.insert(0, GEMINI_DEFAULT_MODEL)
            return valid_models
        except Exception:
            return list(GEMINI_FALLBACK_MODELS)

    @staticmethod
    def build_payload(prompt: str, text: str) -> dict:
        return {
            "systemInstruction": {"parts": [{"text": prompt}]},
            "contents": [{"role": "user", "parts": [{"text": text}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096},
        }

    @classmethod
    def generate(
        cls,
        prompt: str,
        text: str,
        max_retries: int | None = None,
        initial_delay: float | None = None,
        on_retry: RetryCallback | None = None,
        on_chunk: ChunkCallback | None = None,
    ) -> str:
        """Genera texto con Google Gemini, aplicando reintentos si el modelo está ocupado."""
        api_key = ConfigManager.get_api_key()
        if not api_key:
            raise ValueError("API Key de Google Gemini no configurada.")

        model = ConfigManager.get("model", GEMINI_DEFAULT_MODEL)
        payload = cls.build_payload(prompt, text)
        headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}

        def attempt(chunk_cb: ChunkCallback | None) -> str:
            if chunk_cb:
                return cls._stream_once(model, payload, headers, chunk_cb)
            return cls._request_once(model, payload, headers)

        return run_with_retries(
            attempt,
            max_retries if max_retries is not None else cls.MAX_RETRIES,
            initial_delay if initial_delay is not None else cls.INITIAL_BACKOFF,
            on_retry, on_chunk, cls.NAME, cls.SHORT,
        )

    @staticmethod
    def _extract_text(data: dict) -> str:
        candidates = data.get("candidates", [])
        if not candidates or "content" not in candidates[0]:
            return ""
        parts = candidates[0]["content"].get("parts", [])
        return "".join(p.get("text", "") for p in parts)

    @classmethod
    def _request_once(cls, model: str, payload: dict, headers: dict) -> str:
        response = requests.post(
            f"{GEMINI_BASE}/{model}:generateContent",
            json=payload, headers=headers, timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates or "content" not in candidates[0]:
            raise RuntimeError("La respuesta de Gemini no contiene contenido válido.")
        parts = candidates[0]["content"].get("parts", [])
        if not parts or "text" not in parts[0]:
            raise RuntimeError("La respuesta de Gemini vino vacía.")

        content_text = cls._extract_text(data).strip()
        _check_not_busy(content_text)
        return content_text

    @classmethod
    def _stream_once(cls, model: str, payload: dict, headers: dict, on_chunk: ChunkCallback) -> str:
        response = requests.post(
            f"{GEMINI_BASE}/{model}:streamGenerateContent?alt=sse",
            json=payload, headers=headers, timeout=60, stream=True,
        )
        try:
            response.raise_for_status()
            pieces: list[str] = []
            for raw in iter_sse_data(response):
                try:
                    data = json.loads(raw)
                except ValueError:
                    continue
                piece = cls._extract_text(data)
                if piece:
                    if not pieces:
                        _check_not_busy(piece)
                    pieces.append(piece)
                    on_chunk(piece)
        finally:
            response.close()

        full = "".join(pieces).strip()
        if not full:
            raise RuntimeError("La respuesta de Gemini vino vacía.")
        return full


# ─────────────────────────────────────────────────────────────
# Cliente compatible con la API de OpenAI (Ollama, OpenAI, OpenRouter…)
# ─────────────────────────────────────────────────────────────
class OpenAICompatibleClient:
    """Cliente para servidores con el endpoint /chat/completions de OpenAI."""

    NAME = "el proveedor alternativo"
    SHORT = "Proveedor alternativo"
    MAX_RETRIES = 3
    INITIAL_BACKOFF = 1.0

    @staticmethod
    def settings() -> tuple[str, str, str]:
        base = (ConfigManager.get("openai_base_url", OPENAI_DEFAULT_BASE_URL) or "").strip().rstrip("/")
        model = (ConfigManager.get("openai_model", OPENAI_DEFAULT_MODEL) or "").strip()
        return base, model, ConfigManager.get_openai_api_key()

    @classmethod
    def is_configured(cls) -> bool:
        base, model, _ = cls.settings()
        return bool(base and model)

    @staticmethod
    def _headers(api_key: str) -> dict:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    @classmethod
    def fetch_available_models(cls, base_url: str, api_key: str = "") -> list[str]:
        """Lista los modelos del servidor (GET /models). Lista vacía si falla."""
        base = (base_url or "").strip().rstrip("/")
        if not base:
            return []
        try:
            response = requests.get(f"{base}/models", headers=cls._headers(api_key), timeout=10)
            response.raise_for_status()
            return sorted(m["id"] for m in response.json().get("data", []) if m.get("id"))
        except Exception:
            return []

    @staticmethod
    def build_payload(model: str, prompt: str, text: str, stream: bool) -> dict:
        return {
            "model": model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
            "temperature": 0.7,
            "stream": stream,
        }

    @classmethod
    def generate(
        cls,
        prompt: str,
        text: str,
        max_retries: int | None = None,
        initial_delay: float | None = None,
        on_retry: RetryCallback | None = None,
        on_chunk: ChunkCallback | None = None,
    ) -> str:
        base, model, api_key = cls.settings()
        if not base or not model:
            raise ValueError("Proveedor alternativo no configurado (falta la URL o el modelo).")

        url = f"{base}/chat/completions"
        headers = cls._headers(api_key)
        name = f"{cls.NAME} ({base})"

        def attempt(chunk_cb: ChunkCallback | None) -> str:
            payload = cls.build_payload(model, prompt, text, stream=bool(chunk_cb))
            if chunk_cb:
                return cls._stream_once(url, payload, headers, chunk_cb)
            return cls._request_once(url, payload, headers)

        return run_with_retries(
            attempt,
            max_retries if max_retries is not None else cls.MAX_RETRIES,
            initial_delay if initial_delay is not None else cls.INITIAL_BACKOFF,
            on_retry, on_chunk, name, cls.SHORT,
        )

    @staticmethod
    def _request_once(url: str, payload: dict, headers: dict) -> str:
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        response.raise_for_status()
        choices = response.json().get("choices", [])
        content = ""
        if choices:
            content = (choices[0].get("message") or {}).get("content") or ""
        content = content.strip()
        if not content:
            raise RuntimeError("La respuesta del proveedor alternativo vino vacía.")
        _check_not_busy(content)
        return content

    @staticmethod
    def _stream_once(url: str, payload: dict, headers: dict, on_chunk: ChunkCallback) -> str:
        response = requests.post(url, json=payload, headers=headers, timeout=120, stream=True)
        try:
            response.raise_for_status()
            pieces: list[str] = []
            for raw in iter_sse_data(response):
                if raw == "[DONE]":
                    break
                try:
                    data = json.loads(raw)
                except ValueError:
                    continue
                choices = data.get("choices") or [{}]
                piece = (choices[0].get("delta") or {}).get("content") or ""
                if piece:
                    pieces.append(piece)
                    on_chunk(piece)
        finally:
            response.close()

        full = "".join(pieces).strip()
        if not full:
            raise RuntimeError("La respuesta del proveedor alternativo vino vacía.")
        return full


# ─────────────────────────────────────────────────────────────
# Entrada unificada
# ─────────────────────────────────────────────────────────────
PROVIDERS = {
    "gemini": GeminiClient,
    "openai": OpenAICompatibleClient,
}
PROVIDER_LABELS = {
    "gemini": "Gemini",
    "openai": "OpenAI-compatible",
}


def provider_order() -> list[str]:
    """Proveedores a intentar, en orden, según la configuración."""
    primary = ConfigManager.get("provider", "gemini")
    if primary not in PROVIDERS:
        primary = "gemini"
    order = [primary]
    if ConfigManager.get("fallback_enabled", False):
        other = "openai" if primary == "gemini" else "gemini"
        if PROVIDERS[other].is_configured():
            order.append(other)
    return order


def generate_text(
    prompt: str,
    text: str,
    on_retry: RetryCallback | None = None,
    on_chunk: ChunkCallback | None = None,
    on_status: Callable[[str], None] | None = None,
) -> tuple[str, str]:
    """Genera la respuesta con el proveedor configurado (y el alternativo si falla).

    El fallback solo ocurre si el primer proveedor no llegó a emitir texto en
    streaming, para no mezclar respuestas de dos modelos.

    Returns:
        (resultado, proveedor)  donde proveedor es "gemini" u "openai".
    """
    order = provider_order()
    emitted = False

    def chunk_proxy(piece: str):
        nonlocal emitted
        emitted = True
        on_chunk(piece)

    for i, name in enumerate(order):
        try:
            result = PROVIDERS[name].generate(
                prompt, text,
                on_retry=on_retry,
                on_chunk=chunk_proxy if on_chunk else None,
            )
            return result, name
        except Exception:
            if emitted or i == len(order) - 1:
                raise
            if on_status:
                on_status(
                    f"↪ {PROVIDER_LABELS[name]} falló; probando {PROVIDER_LABELS[order[i + 1]]}…"
                )
    raise RuntimeError("No hay proveedores de IA configurados.")
