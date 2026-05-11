"""
Escriba — Clientes de IA (Gemini + Pollinations) y lógica de fallback.
"""

import requests

from constants import GEMINI_MODELS, GEMINI_BASE
from config import ConfigManager


# ─────────────────────────────────────────────────────────────
# Cliente Gemini — auto-detección del modelo disponible
# ─────────────────────────────────────────────────────────────
class GeminiClient:
    """Llama a la API de Gemini probando modelos en orden de preferencia."""

    _working_model: str = None

    @classmethod
    def generate(cls, prompt: str, text: str) -> str:
        api_key = ConfigManager.get_api_key()
        if not api_key:
            raise ValueError("API Key no configurada.")

        # Intentar el modelo que funcionó antes primero
        candidates = (
            [cls._working_model] + GEMINI_MODELS
            if cls._working_model
            else GEMINI_MODELS
        )
        seen, ordered = set(), []
        for m in candidates:
            if m and m not in seen:
                ordered.append(m)
                seen.add(m)

        last_error = "Sin modelos disponibles."
        for model in ordered:
            url = f"{GEMINI_BASE}/{model}:generateContent"
            payload = {
                "contents": [{"parts": [{"text": f"{prompt}\n\n---\n\n{text}"}]}],
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096},
            }
            try:
                r = requests.post(
                    url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "x-goog-api-key": api_key
                    },
                    timeout=60,
                )
                if r.status_code == 404:
                    last_error = f"{model}: no disponible para esta API key (404)"
                    continue
                r.raise_for_status()
                result = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                cls._working_model = model
                return result.strip()
            except requests.HTTPError as e:
                last_error = f"{model}: HTTP {e.response.status_code}"
            except Exception as e:
                last_error = f"{model}: {e}"

        raise RuntimeError(f"Error de API — {last_error}")


# ─────────────────────────────────────────────────────────────
# Cliente gratuito — Pollinations AI (sin API Key)
# ─────────────────────────────────────────────────────────────
class FreeAIClient:
    """Fallback gratuito usando Pollinations AI."""

    _ENDPOINT = "https://text.pollinations.ai/"

    @staticmethod
    def generate(prompt: str, text: str) -> str:
        full_prompt = f"{prompt}\n\n---\n\n{text}"
        payload = {
            "messages": [{"role": "user", "content": full_prompt}],
            "model": "openai",
            "private": True,
        }
        try:
            r = requests.post(
                FreeAIClient._ENDPOINT,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60,
            )
            r.raise_for_status()
            result = r.text.strip()
            if not result:
                raise RuntimeError("La respuesta fue vacía.")
            return result
        except Exception as e:
            raise RuntimeError(f"Pollinations AI: {e}")


# ─────────────────────────────────────────────────────────────
# Fallback unificado (elimina triplicación de lógica)
# ─────────────────────────────────────────────────────────────
def generate_with_fallback(
    prompt: str, text: str, reset_model: bool = False
) -> tuple:
    """Intenta Gemini; si falla, hace fallback a Pollinations.

    Args:
        prompt:      Instrucción para la IA.
        text:        Texto del usuario.
        reset_model: Si True, fuerza re-detección del modelo Gemini.

    Returns:
        (resultado: str, used_gemini: bool)
    """
    result = None
    last_error = None
    used_gemini = False

    if reset_model:
        GeminiClient._working_model = None

    if ConfigManager.is_configured():
        try:
            result = GeminiClient.generate(prompt, text)
            used_gemini = True
        except Exception as e:
            last_error = str(e)

    if result is None:
        try:
            result = FreeAIClient.generate(prompt, text)
        except Exception as e:
            if last_error:
                raise RuntimeError(
                    f"Gemini: {last_error} | Pollinations: {e}"
                )
            raise

    return result, used_gemini
