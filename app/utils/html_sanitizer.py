"""Gemeinsame HTML-Sanitisierung fuer LLM-generierte Inhalte.

Wird von routes.py (Auslieferung ans Frontend), persist_article.py und
persist_photobook.py verwendet. Als defense-in-depth vor XSS durch
LLM-Halluzinationen oder kompromittierte Ollama-Instanzen.
"""

import re


def sanitize_html(html: str, *, keep_style: bool = False) -> str:
    """Entfernt potenziell gefaehrliche Inhalte aus HTML.

    Args:
        html: Roher HTML-String
        keep_style: Wenn True, werden <style>-Tags erhalten
                    (benoetigt fuer Fotobuch-CSS im iframe).

    Bereinigt:
    - <script>-Tags und deren Inhalt
    - Event-Handler-Attribute (onerror, onclick, ...)
    - javascript:-URIs in href/src
    - <style>-Tags (wenn keep_style=False)
    """
    if not html:
        return html

    html = re.sub(
        r"<script[^>]*>.*?</script\s*>",
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    html = re.sub(r"<script[^>]*/>", "", html, flags=re.IGNORECASE)

    if not keep_style:
        html = re.sub(
            r"<style[^>]*>.*?</style\s*>",
            "",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )

    html = re.sub(
        r'\s+on\w+\s*=\s*"[^"]*"', "", html, flags=re.IGNORECASE
    )
    html = re.sub(
        r"\s+on\w+\s*=\s*'[^']*'", "", html, flags=re.IGNORECASE
    )
    html = re.sub(r"\s+on\w+\s*=\s*\S+", "", html, flags=re.IGNORECASE)

    html = re.sub(
        r'(href|src)\s*=\s*"[^"]*javascript:[^"]*"',
        r'\1="#"',
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(
        r"(href|src)\s*=\s*'[^']*javascript:[^']*'",
        r"\1='#'",
        html,
        flags=re.IGNORECASE,
    )

    return html
