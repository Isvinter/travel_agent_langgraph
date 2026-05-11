"""Zentraler Ollama API-Client — vermeidet Code-Duplikation in Services.

Verwendet von: blog_generator, content_reviewer, revise_blogpost, image_selector,
sowie photobook/plan, photobook/generate, photobook/image_selector.
"""

import logging
import re
import time
from typing import Optional

import requests

from app.config import OLLAMA_BASE_URL
from app.services.http_client import get_http_session

logger = logging.getLogger(__name__)

_session = get_http_session()


THINKING_PATTERN = re.compile(
    r'<(?:think|thinking)\b[^>]*>.*?</(?:think|thinking)\s*>|'
    r'<(?:think|thinking)\b[^>]*/>',
    re.DOTALL | re.IGNORECASE,
)


def strip_thinking_tokens(text: str) -> str:
    """Entfernt <think>/<thinking>-Tags aus LLM-Antworten."""
    return THINKING_PATTERN.sub('', text).lstrip('\n')


def call_ollama(
    prompt: str,
    *,
    model: str = "gemma4:26b-ctx128k",
    base_url: str = OLLAMA_BASE_URL,
    images: Optional[list[str]] = None,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    top_p: Optional[float] = 0.9,
    num_predict: int = 16384,
    timeout: int = 600,
    keep_alive: str = "10m",
    strip_thinking: bool = False,
) -> Optional[str]:
    """Sendet einen Chat-Request an die Ollama-API.

    Args:
        prompt: Der User-Prompt (Text).
        model: Ollama-Modellname.
        base_url: Ollama-Server-URL.
        images: Liste von Base64-encodierten Bildern (für multimodale Modelle).
        system_prompt: Optionaler System-Prompt (als system-Nachricht vorangestellt).
        temperature: Kreativitätsparameter (0.0 = deterministisch).
        top_p: Nucleus-Sampling (None = nicht setzen).
        num_predict: Maximale Antwort-Token.
        timeout: Request-Timeout in Sekunden.
        keep_alive: Ollama keep_alive-Dauer.
        strip_thinking: Entferne <think>/<thinking>-Tags aus der Antwort.

    Returns:
        Antwort-Text des LLM oder None bei Fehler.
    """
    url = f"{base_url.rstrip('/')}/api/chat"

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    user_msg: dict = {"role": "user", "content": prompt}
    if images:
        user_msg["images"] = images
    messages.append(user_msg)

    options: dict = {"temperature": temperature, "num_predict": num_predict}
    if top_p is not None:
        options["top_p"] = top_p

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": options,
        "keep_alive": keep_alive,
    }

    try:
        t0 = time.time()
        resp = _session.post(url, json=payload, timeout=timeout)
        elapsed = time.time() - t0
    except requests.exceptions.ConnectionError:
        logger.error("Could not connect to Ollama at %s", base_url)
        return None
    except requests.exceptions.Timeout:
        logger.error("Ollama request timed out after %ss", timeout)
        return None
    except Exception as e:
        logger.error("Ollama request failed: %s", e)
        return None

    if resp.status_code != 200:
        logger.error("Ollama returned HTTP %s: %s", resp.status_code, resp.text[:500])
        return None

    msg = resp.json().get("message", {})
    content = msg.get("content", "")
    # Gemma-Modelle legen Output manchmal ins "thinking"-Feld statt "content"
    # Aber NICHT bei done_reason="length" (trunkierte Antwort) — da enthält
    # thinking nur Reasoning, nicht die eigentliche Antwort.
    done_reason = resp.json().get("done_reason", "")
    if not content and msg.get("thinking") and done_reason != "length":
        content = msg["thinking"]
    if not content:
        thinking_raw = msg.get("thinking", "")
        eval_count = resp.json().get("eval_count", 0)
        logger.warning("Ollama returned HTTP 200 but empty content after %.1fs. eval_count=%s, done_reason=%s, thinking_len=%s",
                       elapsed, eval_count, done_reason, len(thinking_raw))
    if strip_thinking and content:
        content = strip_thinking_tokens(content)
    return content or None
