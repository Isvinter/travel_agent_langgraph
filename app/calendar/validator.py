"""Strukturelle HTML-Validierung für den Kalender (Layer 5)."""
import logging
import re

logger = logging.getLogger(__name__)


def validate_calendar_html(html_content: str) -> list[str]:
    """Prüft das gerenderte HTML auf strukturelle Probleme.

    Checked:
    - HTML nicht leer
    - 13 Seiten vorhanden (Cover + 12 Monate)
    - Keine slot-placeholder divs (indiziert fehlende Bilder)
    - Keine doppelten Bild-src innerhalb einer Seite

    Returns:
        Liste von Warnungen/Fehlern (leer = alles ok).
    """
    issues = []

    if not html_content or not html_content.strip():
        return ["HTML-Inhalt ist leer"]

    # 13 Seiten prüfen
    page_count = html_content.count('class="calendar-page')
    if page_count != 13:
        issues.append(
            f"Erwartet 13 Seiten, gefunden: {page_count}"
        )

    # slot-placeholder prüfen (nur im Body, nicht im CSS-Style-Tag)
    body_match = re.search(r"<body>(.*?)</body>", html_content, re.DOTALL)
    body = body_match.group(1) if body_match else ""
    placeholder_count = body.count("slot-placeholder")
    if placeholder_count > 0:
        issues.append(
            f"{placeholder_count} slot-placeholder(s) gefunden — "
            f"fehlende Bilder"
        )

    # Doppelte Bilder pro Seite prüfen
    pages = html_content.split('class="calendar-page')
    for i, page in enumerate(pages[1:], start=1):
        img_srcs = re.findall(r'<img[^>]+src="([^"]+)"', page)
        seen = set()
        duplicates = set()
        for src in img_srcs:
            if src in seen:
                duplicates.add(src)
            seen.add(src)
        if duplicates:
            issues.append(
                f"Seite {i}: {len(duplicates)} doppelte(s) Bild(er) — "
                f"{', '.join(list(duplicates)[:3])}"
            )

    if issues:
        logger.warning("Kalender-HTML-Validierung: %d Problem(e)", len(issues))
        for issue in issues:
            logger.warning("  - %s", issue)
    else:
        logger.info("Kalender-HTML-Validierung: OK (13 Seiten, keine Platzhalter)")

    return issues
