"""PDF-Generierung aus Artikel-HTML via Headless Chrome (Selenium CDP)."""
import base64
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def _rewrite_html_for_pdf(html_content: str | None, article_output_dir: str | None) -> str | None:
    """Bereitet HTML für die PDF-Generierung vor:
    - ./images/ Pfade zu absoluten file:/// Pfaden umschreiben
    - max-width: 780px auf max-width: 100% setzen
    - @page CSS für A4-Drucklayout injizieren
    """
    if not html_content:
        return html_content

    # Basisverzeichnis für Bildpfade
    if article_output_dir:
        base_dir = os.path.abspath(article_output_dir)
    else:
        base_dir = os.path.abspath(".")

    # ./images/ → file:///... absolute Pfade
    html_content = re.sub(
        r'src="\./images/',
        f'src="file://{base_dir}/images/',
        html_content,
    )

    # max-width: 780px → 100% (Volle Breite für PDF)
    html_content = html_content.replace("max-width: 780px", "max-width: 100%")

    # @page CSS für A4-Druck injizieren
    print_css = '<style>@page { size: A4; margin: 15mm; } @media print { body { max-width: 100% !important; } }</style>'

    if "</head>" in html_content:
        html_content = html_content.replace("</head>", f"{print_css}\n</head>")
    else:
        html_content = print_css + html_content

    return html_content


def generate_pdf(html_content: str, article_output_dir: str | None = None) -> bytes:
    """Wandelt Artikel-HTML via Headless Chrome in PDF um.

    Args:
        html_content: Vollständiges HTML des Artikels (mit ./images/ Pfaden)
        article_output_dir: Verzeichnis, das den Output-Ordner des Artikels enthält

    Returns:
        PDF als Bytes

    Raises:
        RuntimeError: Wenn Chrome nicht verfügbar ist oder die Generierung fehlschlägt
    """
    if not html_content:
        raise ValueError("Kein HTML-Inhalt für die PDF-Generierung")

    processed_html = _rewrite_html_for_pdf(html_content, article_output_dir)

    # Temporäre HTML-Datei schreiben
    fd, html_path = tempfile.mkstemp(suffix=".html")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(processed_html)

        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")

        driver = webdriver.Chrome(options=options)
        try:
            abs_path = os.path.abspath(html_path)
            driver.get(f"file:///{abs_path}")
            time.sleep(1)  # Warten bis Bilder geladen sind

            pdf_result = driver.execute_cdp_cmd("Page.printToPDF", {
                "printBackground": True,
                "paperWidth": 8.27,   # A4
                "paperHeight": 11.69,  # A4
                "marginTop": 0.59,     # 15mm in Zoll
                "marginBottom": 0.59,
                "marginLeft": 0.59,
                "marginRight": 0.59,
                "preferCSSPageSize": True,
            })

            pdf_bytes = base64.b64decode(pdf_result["data"])
            return pdf_bytes
        finally:
            driver.quit()
    finally:
        if os.path.exists(html_path):
            os.unlink(html_path)
