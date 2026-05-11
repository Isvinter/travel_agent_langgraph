"""Zentraler HTTP-Client mit Connection-Pooling via requests.Session.

Stellt eine einzige Session-Instanz für alle HTTP-Anfragen bereit.
Module, die requests.Session nutzen (ollama_client, poi_enricher,
weather_enricher), importieren get_http_session() aus diesem Modul.
"""

import atexit
import logging

import requests

logger = logging.getLogger(__name__)

_session_cache: requests.Session | None = None


def get_http_session() -> requests.Session:
    """Gibt eine gecachte requests.Session mit User-Agent Header zurück."""
    global _session_cache
    if _session_cache is None:
        _session_cache = requests.Session()
        _session_cache.headers.update({"User-Agent": "travel-agent/1.0"})
    return _session_cache


def close_http_session() -> None:
    """Schliesst die gecachte Session (wird via atexit aufgerufen)."""
    global _session_cache
    if _session_cache is not None:
        _session_cache.close()
        _session_cache = None


atexit.register(close_http_session)
