"""Gemeinsame HTML-Sanitisierung fuer LLM-generierte Inhalte.

Wird von routes.py (Auslieferung ans Frontend), persist_article.py und
persist_photobook.py verwendet. Als defense-in-depth vor XSS durch
LLM-Halluzinationen oder kompromittierte Ollama-Instanzen.

Verwendet nh3 (ammonia-Nachfolger), einen robusten Rust-basierten HTML-Sanitizer.
"""

import nh3

_EXTRA_TAGS = {
    "section", "article", "main", "header", "footer", "figure",
    "figcaption", "details", "summary", "nav", "dl", "dt", "dd",
}

_ATTRIBUTES = {
    "a": {"href", "title", "target"},
    "img": {"src", "alt", "width", "height", "loading", "class", "style"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan"},
    "div": {"class", "style"},
    "span": {"class", "style"},
    "section": {"class", "style"},
    "article": {"class", "style"},
}


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

    tags = nh3.ALLOWED_TAGS | _EXTRA_TAGS

    clean_content_tags = set(nh3.CLEAN_CONTENT_TAGS)

    if keep_style:
        tags.add("style")
        clean_content_tags.discard("style")

    return nh3.clean(
        html,
        tags=tags,
        attributes=_ATTRIBUTES,
        clean_content_tags=frozenset(clean_content_tags),
        strip_comments=True,
    )
