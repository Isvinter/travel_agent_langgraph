"""Service für die LLM-basierte Überarbeitung von Blog-Drafts."""
import re
from typing import Dict, Any, List, Optional

from app.config import OLLAMA_BASE_URL


def _call_ollama_text(
    system_prompt: str,
    user_prompt: str,
    model: str = "gemma4:26b-ctx128k",
) -> Optional[str]:
    """Ruft Ollama mit reinem Text auf (keine Bilder)."""
    import requests

    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {
            "temperature": 0.7,
            "top_p": 0.9,
            "num_predict": 16384,
        },
        "keep_alive": "10m",
    }

    try:
        response = requests.post(url, json=payload, timeout=600)
        if response.status_code == 200:
            result = response.json()
            return result.get("message", {}).get("content", "")
        else:
            print(f"❌ Ollama API Error: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return None
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to Ollama. Is it running? (ollama serve)")
        return None
    except Exception as e:
        print(f"❌ Error calling Ollama: {e}")
        return None


def _count_paragraphs(markdown: str) -> int:
    """Zählt Text-Absätze im Markdown (nicht-Überschrift, nicht-leer)."""
    paragraphs = 0
    for line in markdown.split("\n"):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("!"):
            paragraphs += 1
    return paragraphs


def _build_revision_prompt(
    current_markdown: str,
    changes: list[dict],
    full_context: dict,
    persona: str,
    length: str,
) -> str:
    """Baut den Revisions-Prompt für Ollama."""
    persona_descriptions = {
        "mountain_veteran": "Ein erfahrener Bergsteiger mit trockenem Humor und tiefer Naturverbundenheit. Schreibt in klarer, präziser Sprache.",
        "field_reporter": "Ein Reisejournalist mit lebendigem, atmosphärischem Schreibstil. Schreibt detailreich und einfühlsam.",
    }
    persona_text = persona_descriptions.get(persona, persona_descriptions["mountain_veteran"])

    length_hints = {
        "short": "Halte den Text knapp und fokussiert.",
        "normal": "Gute Balance zwischen Detail und Lesbarkeit.",
        "detailed": "Detaillierte Beschreibungen sind erwünscht.",
    }
    length_hint = length_hints.get(length, length_hints["normal"])

    context_lines = []
    notes = full_context.get("notes")
    if notes:
        context_lines.append(f"Notizen des Autors: {notes}")

    gpx = full_context.get("gpx_stats", {})
    if gpx:
        dist = gpx.get("total_distance_km")
        gain = gpx.get("elevation_gain_m")
        loss = gpx.get("elevation_loss_m")
        if dist:
            context_lines.append(f"Distanz: {dist} km")
        if gain:
            context_lines.append(f"Aufstieg: {gain} m")
        if loss:
            context_lines.append(f"Abstieg: {loss} m")

    context_block = "\n".join(context_lines) if context_lines else "Keine Zusatzinformationen verfügbar."

    changes_block = ""
    for i, change in enumerate(changes, 1):
        changes_block += f"""
### Änderung {i}
- **Element-Typ:** {change.get('element_type', 'paragraph')}
- **Index:** {change.get('element_index', '?')}
- **Original-Text:** {change.get('original_content', '')[:300]}
- **Anweisung:** {change.get('instruction', 'Bitte umschreiben/verbessern')}
"""

    prompt = f"""Du bist ein erfahrener Reiseblog-Autor. {persona_text} {length_hint}

## Zusätzlicher Kontext
{context_block}

## Dein Auftrag
Überarbeite den folgenden Blog-Artikel NUR an den unten markierten Stellen. Alle nicht markierten Absätze MÜSSEN unverändert bleiben. Achte darauf, dass die überarbeiteten Absätze stilistisch und inhaltlich perfekt zu den umgebenden, unveränderten Absätzen passen.

WICHTIG: Ändere NUR die markierten Absätze. Wenn ein Bild markiert ist und die Anweisung ein anderes Bild vorschlägt, beschreibe kurz welche Art von Bild besser passen würde. Lösche KEINE Absätze, füge KEINE neuen Absätze hinzu.

## Vollständiger Artikel

{current_markdown}

## Markierte Änderungen
{changes_block}

Gib den KOMPLETTEN überarbeiteten Artikel aus (alle Absätze, auch die unveränderten). Das Format muss exakt dem Original entsprechen (gleiche Anzahl Absätze, gleiche Bild-Referenzen wo nicht anders angegeben).
"""
    return prompt


def revise_blog_post(
    current_markdown: str,
    changes: list[dict],
    full_context: dict,
    available_images: list[str],
    output_config,
    model: str,
) -> dict:
    """Führt eine LLM-basierte Revision des Blogposts durch.

    Args:
        current_markdown: Der aktuelle Markdown-Text des Artikels
        changes: Liste von Dictionaries mit {element_type, element_index, original_content, instruction}
        full_context: Dictionary mit {notes, gpx_stats}
        available_images: Liste der verfügbaren Bild-Pfade
        output_config: OutputConfig mit style_persona und article_length
        model: Ollama-Modellname

    Returns:
        dict mit {success, markdown, html, paragraph_count_changed}
    """
    old_count = _count_paragraphs(current_markdown)

    system_prompt = "Du bist ein professioneller Reiseblog-Autor. Deine Aufgabe ist es, Blog-Artikel auf Anweisung punktuell zu überarbeiten."

    user_prompt = _build_revision_prompt(
        current_markdown,
        changes,
        full_context,
        output_config.style_persona,
        output_config.article_length,
    )

    response = _call_ollama_text(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
    )

    if response is None:
        return {"success": False, "markdown": "", "html": "", "paragraph_count_changed": False}

    # Clean thinking tokens
    cleaned = re.sub(r'<thinking>.*?</thinking>', '', response, flags=re.DOTALL)
    cleaned = cleaned.strip()

    new_count = _count_paragraphs(cleaned)
    paragraph_count_changed = new_count != old_count

    return {
        "success": True,
        "markdown": cleaned,
        "html": "",
        "paragraph_count_changed": paragraph_count_changed,
    }
