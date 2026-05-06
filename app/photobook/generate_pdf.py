"""PDF-Generierung fuer Fotobuch via Headless Chrome (Selenium CDP)."""

import base64
import os
import tempfile
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


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
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(processed)

        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=options)
        try:
            abs_path = os.path.abspath(html_path)
            driver.get(f"file:///{abs_path}")
            # Erzwinge Print-Media für korrekte @media print und @page Anwendung
            driver.execute_cdp_cmd("Emulation.setEmulatedMedia", {"media": "print"})
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
