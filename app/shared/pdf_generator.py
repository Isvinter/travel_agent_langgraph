"""PDF-Generierung via Headless Chrome (shared zwischen Photobuch und Kalender)."""
import base64
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)

PAPER_SIZES = {
    "portrait":  {"width": 8.27, "height": 11.69, "css": "size: 210mm 297mm"},
    "landscape": {"width": 11.69, "height": 8.27, "css": "size: 297mm 210mm"},
}


def _inject_print_css(html_content: str, paper_size: str) -> str:
    paper = PAPER_SIZES[paper_size]
    print_css = (
        f'<style>'
        f'@page {{ {paper["css"]}; margin: 0 !important; }}'
        f'body {{ margin: 0 !important; padding: 0 !important; display: block !important; }}'
        f'</style>'
    )
    if "</head>" in html_content:
        return html_content.replace("</head>", f"{print_css}\n</head>")
    return print_css + html_content


def generate_pdf(
    html_content: str,
    paper_size: str = "portrait",
    source_path: Optional[str] = None,
) -> bytes:
    """Wandelt HTML via Headless Chrome in PDF um.

    Args:
        html_content: Vollständiges HTML-Dokument.
        paper_size: "portrait" oder "landscape".
        source_path: Pfad zur HTML-Datei (für file:// Bilder).

    Returns:
        PDF als Bytes.
    """
    if not html_content:
        raise ValueError("Kein HTML-Inhalt für die PDF-Generierung")
    if paper_size not in PAPER_SIZES:
        raise ValueError(f"Unbekanntes paper_size: {paper_size}. Erlaubt: {sorted(PAPER_SIZES.keys())}")

    processed = _inject_print_css(html_content, paper_size)

    tmp_dir = os.path.dirname(source_path) if source_path and os.path.isfile(source_path) else None
    fd, html_path = tempfile.mkstemp(suffix=".html", dir=tmp_dir)
    try:
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(processed)
        except Exception:
            os.close(fd)
            raise

        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")

        with webdriver.Chrome(options=options) as driver:
            driver.set_page_load_timeout(30)
            abs_load = os.path.abspath(html_path)
            driver.get(f"file:///{abs_load}")
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            driver.execute_cdp_cmd("Emulation.setEmulatedMedia", {"media": "print"})

            paper = PAPER_SIZES[paper_size]
            pdf_result = driver.execute_cdp_cmd("Page.printToPDF", {
                "printBackground": True,
                "paperWidth": paper["width"],
                "paperHeight": paper["height"],
                "marginTop": 0,
                "marginBottom": 0,
                "marginLeft": 0,
                "marginRight": 0,
                "preferCSSPageSize": True,
            })

            return base64.b64decode(pdf_result["data"])

    finally:
        try:
            Path(html_path).unlink(missing_ok=True)
        except Exception as e:
            logger.warning("Konnte temp-Datei nicht löschen %s: %s", html_path, e)
