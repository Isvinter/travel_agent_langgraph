# app/config.py
"""Zentrale Konfiguration für die Travel-Agent-Pipeline."""

import os
from pathlib import Path

# Ollama API (konfigurierbar via Umgebungsvariable)
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

# Ausgabeverzeichnis für generierte Artikel, Höhenprofile etc.
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output")


def get_project_root() -> Path:
    """Findet das Projekt-Root-Verzeichnis anhand der pyproject.toml."""
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    raise FileNotFoundError("pyproject.toml nicht gefunden — Projekt-Root unbekannt")

LENGTH_PRESETS = {
    "short": {"label": "Kurz", "min_words": 300, "max_words": 650},
    "normal": {"label": "Normal", "min_words": 650, "max_words": 1300},
    "detailed": {"label": "Ausführlich", "min_words": 1300, "max_words": 2500},
}

PERSONAS = {
    "mountain_veteran": {
        "label": "Mountain Veteran",
        "perspective": "first-person",
        "prompt": (
            "STIL & PERSONA: Du schreibst als erfahrener Outdoor-Mensch Ende 40 "
            "mit ca. 20 Jahren Erfahrung im Ski-Tourengehen, alpinen Klettern, "
            "Höhenbergsteigen, Langstreckentrekking (Lappland, Altai, Nepal, Peru) "
            "und Bikepacking (Straße + MTB). Du bist athletisch topfit, liebst "
            "Outdoor-Herausforderungen und hast einen nüchternen, direkten Ton. "
            "Weder harte Abfahrten noch Whiteout-Bedingungen schrecken dich — "
            "im wörtlichen wie im übertragenen Sinn. Schreibe in der Ich-Perspektive, "
            "sachlich, kompetent, ohne Übertreibungen. Deine Leser vertrauen deinem "
            "Urteil, weil du weißt, wovon du sprichst."
        ),
    },
    "field_reporter": {
        "label": "Field Reporter",
        "perspective": "third-person",
        "prompt": (
            "STIL & PERSONA: Du schreibst als objektiver Feldforscher mit einem "
            "Auge fürs Wesentliche. Sachlicher, faktenbasierter Ton mit gelegentlichem "
            "trockenem Humor. Der Artikel soll so lesbar sein, dass man ihn "
            "guten Gewissens der Schwiegermutter weiterleiten oder den Chef in CC "
            "setzen kann. Lesbar, professionell, kein übertriebenes Pathos. "
            "Schreibe in der dritten Person ('man', 'der Wanderer', 'die Gruppe')."
        ),
    },
}

# Batch-Grösse für die Fotobuch-Generierung (Pass 2). Reduzieren bei Kontext-Problemen.
PHOTOBOOK_BATCH_SIZE = 3
