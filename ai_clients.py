"""
Escriba — Cliente de IA para Google Gemini.
"""

import random
import time
from typing import Callable

import requests

from constants import (
    GEMINI_BASE,
    GEMINI_DEFAULT_MODEL,
    GEMINI_FALLBACK_MODELS,
)
from config import ConfigManager

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
# Cliente Google Gemini — API oficial
# ─────────────────────────────────────────────────────────────
class GeminiClient:
    """Llama a la API oficial de Google Gemini con gestión de modelos y reintentos automáticos."""

    MAX_RETRIES = 3
    INITIAL_BACKOFF = 2.0
    BACKOFF_MULTIPLIER = 2.0

    @classmethod
    def fetch_available_models(cls, api_key: str | None = None) -> list[str]:
        """Descarga la lista de modelos Gemini válidos para generateContent."""
        key = api_key or ConfigManager.get_api_key()
        if not key:
            return list(GEMINI_FALLBACK_MODELS)

        url = GEMINI_BASE
        try:
            response = requests.get(
                url,
                headers={"x-goog-api-key": key},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            raw_models = data.get("models", [])
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

            # Asegurar que gemini-3.5-flash-lite esté al principio
            if GEMINI_DEFAULT_MODEL in valid_models:
                valid_models.remove(GEMINI_DEFAULT_MODEL)
                valid_models.insert(0, GEMINI_DEFAULT_MODEL)
            else:
                valid_models.insert(0, GEMINI_DEFAULT_MODEL)

            return valid_models
        except Exception:
            return list(GEMINI_FALLBACK_MODELS)

    @classmethod
    def generate(
        cls,
        prompt: str,
        text: str,
        max_retries: int | None = None,
        initial_delay: float | None = None,
        on_retry: Callable[[int, int, float, str], None] | None = None,
    ) -> str:
        """Genera texto con Google Gemini, aplicando reintentos si el modelo está ocupado."""
        api_key = ConfigManager.get_api_key()
        if not api_key:
            raise ValueError("API Key de Google Gemini no configurada.")

        model = ConfigManager.get("model", GEMINI_DEFAULT_MODEL)
        url = f"{GEMINI_BASE}/{model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": f"{prompt}\n\n---\n\n{text}"}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096},
        }

        retries = max_retries if max_retries is not None else cls.MAX_RETRIES
        base_delay = initial_delay if initial_delay is not None else cls.INITIAL_BACKOFF

        for attempt in range(1, retries + 1):
            try:
                response = requests.post(
                    url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "x-goog-api-key": api_key,
                    },
                    timeout=60,
                )
                response.raise_for_status()
                data = response.json()
                candidates = data.get("candidates", [])
                if not candidates or "content" not in candidates[0]:
                    raise RuntimeError("La respuesta de Gemini no contiene contenido válido.")
                parts = candidates[0]["content"].get("parts", [])
                if not parts or "text" not in parts[0]:
                    raise RuntimeError("La respuesta de Gemini vino vacía.")

                content_text = parts[0]["text"].strip()
                if any(kw in content_text.lower() for kw in ("el modelo está ocupado", "the model is overloaded")):
                    raise RuntimeError(content_text)

                return content_text

            except requests.exceptions.HTTPError as e:
                status_code = getattr(e.response, "status_code", 0)
                error_details = ""
                try:
                    err_json = e.response.json()
                    if "error" in err_json and "message" in err_json["error"]:
                        error_details = f": {err_json['error']['message']}"
                except Exception:
                    error_details = f": {e.response.text[:200]}"

                retryable, reason = is_retryable_error(e)
                if retryable and attempt < retries:
                    delay = base_delay * (cls.BACKOFF_MULTIPLIER ** (attempt - 1)) + random.uniform(0.1, 0.4)
                    if on_retry:
                        on_retry(attempt, retries, delay, reason)
                    time.sleep(delay)
                    continue

                if status_code in (429, 503) or "overload" in error_details.lower() or "exhaust" in error_details.lower():
                    raise RuntimeError(
                        f"El modelo de Gemini está ocupado o con límite de uso excedido (HTTP {status_code}){error_details}. "
                        f"Reintentos agotados ({retries}/{retries})."
                    )
                raise RuntimeError(f"Gemini HTTP {status_code}{error_details}")

            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                retryable, reason = is_retryable_error(e)
                if retryable and attempt < retries:
                    delay = base_delay * (cls.BACKOFF_MULTIPLIER ** (attempt - 1)) + random.uniform(0.1, 0.4)
                    if on_retry:
                        on_retry(attempt, retries, delay, reason)
                    time.sleep(delay)
                    continue
                if isinstance(e, requests.exceptions.ConnectionError):
                    raise RuntimeError("Error de red: No se pudo conectar a Google Gemini. Revisa tu conexión a internet.")
                raise RuntimeError("Tiempo de espera agotado al conectar con Google Gemini.")

            except Exception as e:
                retryable, reason = is_retryable_error(e)
                if retryable and attempt < retries:
                    delay = base_delay * (cls.BACKOFF_MULTIPLIER ** (attempt - 1)) + random.uniform(0.1, 0.4)
                    if on_retry:
                        on_retry(attempt, retries, delay, reason)
                    time.sleep(delay)
                    continue
                raise RuntimeError(f"Gemini: {e}")


# ─────────────────────────────────────────────────────────────
# Entrada unificada
# ─────────────────────────────────────────────────────────────
def generate_with_fallback(
    prompt: str,
    text: str,
    on_retry: Callable[[int, int, float, str], None] | None = None,
) -> tuple[str, str]:
    """Genera respuesta utilizando Google Gemini con el modelo configurado y soporte de reintentos.

    Returns:
        (resultado: str, provider: str)  donde provider es "gemini".
    """
    result = GeminiClient.generate(prompt, text, on_retry=on_retry)
    return result, "gemini"
