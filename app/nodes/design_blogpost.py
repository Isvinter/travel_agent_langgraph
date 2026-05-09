import logging

from app.state import AppState
from app.services.design_blogpost import design_blogpost_service

logger = logging.getLogger(__name__)


def design_blogpost_node(state: AppState) -> AppState:
    """Wraps das Blog-HTML in ein vollständiges gestyltes HTML-Dokument.

    Template-basiert — kein LLM-Aufruf, deterministisches Ergebnis.
    Liest state.blog_post["html"], wrapped es in ein HTML-Dokument mit
    eingebettetem CSS und überschreibt state.blog_post["html"] sowie
    die .html-Datei.

    Best-Effort: Bei Fehlern bleibt das Original-HTML erhalten.
    """
    logger.info("Applying design styling to blog HTML...")

    if not state.blog_post or not state.blog_post.get("success"):
        logger.warning("Design: Kein erfolgreicher Blog-Post — überspringe")
        return state

    html = state.blog_post.get("html", "")
    if not html:
        logger.warning("Design: Kein HTML-Inhalt — überspringe")
        return state

    try:
        styled = design_blogpost_service(html, model=state.model)

        if styled:
            # State zuerst aktualisieren — auch wenn Datei-Schreiben fehlschlägt,
            # wird das gestylte HTML so in die DB persistiert.
            state.blog_post["html"] = styled

            html_path = state.blog_post.get("file_paths", {}).get("html")
            if html_path:
                try:
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(styled)
                    logger.info("Styled HTML written to: %s", html_path)
                except Exception as e:
                    logger.warning("Design: Could not write styled HTML file: %s", e)
            logger.info("Design styling applied successfully")
        else:
            logger.warning("Design: Styling failed — Original-HTML bleibt erhalten")
    except Exception as e:
        logger.warning("Design: Error during styling: %s — Original-HTML bleibt erhalten", e)

    return state
