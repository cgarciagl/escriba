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

    @classmethod
    def reset_model_cache(cls):
        """Limpia el modelo que funcionó anteriormente para forzar re-detección."""
        cls._working_model = None

    @classmethod
    def generate(cls, prompt: str, text: str) -> str:
        api_key = ConfigManager.get_api_key()
        if not api_key:
            raise ValueError("API Key no configurada.")

        # Construir lista de modelos a probar (priorizando el último exitoso)
        priority_models = cls._get_priority_models()

        last_failure_reason = "Sin modelos disponibles."
        for model in priority_models:
            url = f"{GEMINI_BASE}/{model}:generateContent"
            payload = {
                "contents": [{"parts": [{"text": f"{prompt}\n\n---\n\n{text}"}]}],
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096},
            }
            try:
                response = requests.post(
                    url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "x-goog-api-key": api_key
                    },
                    timeout=60,
                )
                if response.status_code == 404:
                    last_failure_reason = f"{model}: no disponible para esta API key (404)"
                    continue
                response.raise_for_status()
                result = response.json()["candidates"][0]["content"]["parts"][0]["text"]
                cls._working_model = model
                return result.strip()
            except requests.exceptions.ConnectionError:
                last_failure_reason = f"{model}: Error de conexión (revisa tu internet)"
            except requests.exceptions.HTTPError as e:
                last_failure_reason = f"{model}: HTTP {e.response.status_code}"
            except Exception as e:
                last_failure_reason = f"{model}: {e}"

        raise RuntimeError(f"Error de API — {last_failure_reason}")

    @classmethod
    def _get_priority_models(cls) -> list[str]:
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
        return ordered


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
        except requests.exceptions.ConnectionError:
            raise RuntimeError("Error de red: No se pudo conectar a Pollinations AI. Revisa tu conexión a Internet.")
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
        GeminiClient.reset_model_cache()

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
