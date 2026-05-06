"""PDF-Generierung fuer Fotobuch via Headless Chrome (Selenium CDP) oder WeasyPrint.

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
    """Injiziert @page CSS fuer A4 Einzelseiten und erzwungene Print-Styles."""
    print_css = (
        '<style>'
        '@page { size: A4; margin: 0 !important; }'
        '</style>'
    )
    if "</head>" in html_content:
        return html_content.replace("</head>", f"{print_css}\n</head>")
    return print_css + html_content


def generate_photobook_pdf_weasyprint(html_content: str) -> bytes:
    """Wandelt Fotobuch-HTML via WeasyPrint in PDF um (kein Chrome nötig)."""
    import weasyprint
    processed = _inject_print_css(html_content)
    # WeasyPrint erwartet file:// URIs oder base_url für lokale Dateien
    doc = weasyprint.HTML(string=processed)
    return doc.write_pdf()


def generate_photobook_pdf_chrome(html_content: str) -> bytes:
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


def generate_photobook_pdf(html_content: str, method: str = "weasyprint") -> bytes:
    """Wandelt Fotobuch-HTML in PDF um.

    Args:
        html_content: Vollstaendiges HTML des Fotobuchs
        method: "weasyprint" (default, kein Chrome nötig) oder "chrome"

    Returns:
        PDF als Bytes
    """
    if not html_content:
        raise ValueError("Kein HTML-Inhalt fuer die PDF-Generierung")

    if method == "weasyprint":
        try:
            return generate_photobook_pdf_weasyprint(html_content)
        except Exception as e:
            print(f"⚠️ WeasyPrint fehlgeschlagen: {e}, versuche Chrome...")
            return generate_photobook_pdf_chrome(html_content)
    else:
        return generate_photobook_pdf_chrome(html_content)
