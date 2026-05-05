"""PDF-Generierung fuer Fotobuch via Headless Chrome (Selenium CDP).

Basiert auf dem gleichen Mechanismus wie app/services/generate_pdf.py,
aber optimiert fuer Fotobuch-Seiten (Single A4 / Spread A3).
"""

import base64
import os
import tempfile
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def _inject_print_css(html_content: str) -> str:
    """Injiziert @page CSS fuer A4 Einzelseiten und A3 Doppelseiten."""
    print_css = (
        '<style>'
        '@page { size: A4; margin: 0; }'
        '@media print { body { background: #fff !important; margin: 0; } }'
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
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(processed)

        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")

        driver = webdriver.Chrome(options=options)
        try:
            abs_path = os.path.abspath(html_path)
            driver.get(f"file:///{abs_path}")
            time.sleep(1)

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
        if os.path.exists(html_path):
            os.unlink(html_path)
