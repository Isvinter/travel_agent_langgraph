"""Zentrales Logging-Setup für die gesamte Pipeline.

Ersetzt die bisherigen print()-Statements durch strukturiertes Logging
mit Timestamps, Log-Leveln und optionaler File-Ausgabe.

Verwendung:
    from app.logging_setup import setup_logging, get_logger
    setup_logging()
    logger = get_logger(__name__)
    logger.info("Verarbeite GPX-Datei...")
"""

import logging
import os
import sys

_initialized = False


def setup_logging(
    level: int = logging.INFO,
    log_file: str | None = None,
) -> None:
    """Konfiguriert das Logging-System einmalig.

    Args:
        level: Logging-Level (Default INFO)
        log_file: Optionaler Pfad für File-basiertes Logging
    """
    global _initialized
    if _initialized:
        return
    _initialized = True

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(fmt)
    root.handlers.clear()
    root.addHandler(console)

    # Optional file handler
    if log_file:
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(fmt)
        root.addHandler(fh)


def get_logger(name: str) -> logging.Logger:
    """Gibt einen Logger für das angegebene Modul zurück."""
    return logging.getLogger(name)
