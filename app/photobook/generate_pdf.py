"""PDF-Generierung fuer Fotobuch via Headless Chrome (Selenium CDP)."""

import base64
import logging
import os
import tempfile
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)


def _inject_print_css(html_content: str) -> str:
    """Injiziert @page CSS und Print-Styles fuer Chrome."""
    print_css = (
        '<style>'
        '@page { size: 210mm 297mm; margin: 0 !important; }'
        'body { margin: 0 !important; padding: 0 !important; }'
        '.photobook-page:last-child { margin-bottom: 0 !important; }'
        '</style>'
    )
    if "</head>" in html_content:
        return html_content.replace("</head>", f"{print_css}\n</head>")
    return print_css + html_content


def generate_photobook_pdf(html_content: str) -> bytes:
    """Wandelt Fotobuch-HTML via Headless Chrome in PDF um.

    Args:
        html_content: Vollstaendiges HTML des Fotobuchs

    Returns:
        PDF als Bytes

    Raises:
        ValueError: Wenn html_content leer ist
        RuntimeError: Wenn Chrome/PDF-Generierung fehlschlaegt
    """
    if not html_content:
        raise ValueError("Kein HTML-Inhalt fuer die PDF-Generierung")

    processed = _inject_print_css(html_content)

    fd, html_path = tempfile.mkstemp(suffix=".html")
    try:
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(processed)
        except Exception:
            os.close(fd)  # fdopen fehlgeschlagen → fd manuell schließen
            raise

        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=options)
        try:
            abs_path = os.path.abspath(html_path)
            driver.get(f"file:///{abs_path}")
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            # Erzwinge Print-Media für korrekte @media print und @page Anwendung
            driver.execute_cdp_cmd("Emulation.setEmulatedMedia", {"media": "print"})

            pdf_result = driver.execute_cdp_cmd("Page.printToPDF", {
                "printBackground": True,
                "paperWidth": 8.27,
                "paperHeight": 11.69,
                "marginTop": 0,
                "marginBottom": 0,
                "marginLeft": 0,
                "marginRight": 0,
                "preferCSSPageSize": True,
            })

            return base64.b64decode(pdf_result["data"])
        finally:
            driver.quit()
    finally:
        try:
            Path(html_path).unlink(missing_ok=True)
        except Exception as e:
            logger.warning("Konnte temp-Datei nicht löschen %s: %s", html_path, e)
