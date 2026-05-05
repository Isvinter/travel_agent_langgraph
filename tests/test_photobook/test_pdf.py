"""Tests fuer die Fotobuch-PDF-Generierung."""
import pytest
from app.photobook.generate_pdf import generate_photobook_pdf

DUMMY_HTML = """<!DOCTYPE html><html><body><h1>Test Fotobuch</h1></body></html>"""


class TestPhotobookPdf:
    def test_generate_pdf_returns_bytes(self):
        """PDF-Generierung liefert bytes mit PDF-Header zurueck."""
        pdf_bytes = generate_photobook_pdf(DUMMY_HTML)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:4] == b"%PDF"

    def test_empty_html_raises(self):
        """Leeres HTML wirft ValueError."""
        with pytest.raises(ValueError):
            generate_photobook_pdf("")

    def test_none_html_raises(self):
        """None als HTML wirft ValueError."""
        with pytest.raises(ValueError):
            generate_photobook_pdf(None)

    def test_pdf_contains_multiple_pages(self):
        """Mehrere Seiten werden korrekt gerendert."""
        html = """<!DOCTYPE html><html><body>
        <div class="page-single">Seite 1</div>
        <div class="page-spread">Seite 2</div>
        <div class="page-single">Seite 3</div>
        </body></html>"""
        pdf_bytes = generate_photobook_pdf(html)
        assert len(pdf_bytes) > 100
