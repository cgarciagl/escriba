"""
Escriba — Clientes de IA (OpenRouter + Pollinations) y lógica de fallback.
"""

import requests

from constants import OPENROUTER_BASE, OPENROUTER_DEFAULT_MODEL
from config import ConfigManager


# ─────────────────────────────────────────────────────────────
# Cliente OpenRouter — API compatible con OpenAI
# ─────────────────────────────────────────────────────────────
class OpenRouterClient:
    """Llama a la API de OpenRouter con el modelo configurado."""

    @classmethod
    def generate(cls, prompt: str, text: str) -> str:
        api_key = ConfigManager.get_api_key()
        if not api_key:
            raise ValueError("API Key no configurada.")

        model = ConfigManager.get("model", OPENROUTER_DEFAULT_MODEL)
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": f"{prompt}\n\n---\n\n{text}"}],
        }
        try:
            response = requests.post(
                f"{OPENROUTER_BASE}/chat/completions",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "X-Title": "Escriba",
                },
                timeout=60,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except requests.exceptions.ConnectionError:
            raise RuntimeError("Error de red: No se pudo conectar a OpenRouter. Revisa tu conexión.")
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"OpenRouter HTTP {e.response.status_code}: {e.response.text[:200]}")
        except Exception as e:
            raise RuntimeError(f"OpenRouter: {e}")


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
# Fallback unificado
# ─────────────────────────────────────────────────────────────
def generate_with_fallback(prompt: str, text: str) -> tuple:
    """Intenta OpenRouter; si falla o no hay key, hace fallback a Pollinations.

    Returns:
        (resultado: str, used_openrouter: bool)
    """
    result = None
    last_error = None
    used_openrouter = False

    if ConfigManager.is_configured():
        try:
            result = OpenRouterClient.generate(prompt, text)
            used_openrouter = True
        except Exception as e:
            last_error = str(e)

    if result is None:
        try:
            result = FreeAIClient.generate(prompt, text)
        except Exception as e:
            if last_error:
                raise RuntimeError(f"OpenRouter: {last_error} | Pollinations: {e}")
            raise

    return result, used_openrouter
