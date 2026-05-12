import pytest
from app.shared.pdf_generator import generate_pdf, _inject_print_css


class TestGeneratePdf:
    @pytest.mark.unit
    def test_rejects_empty_html(self):
        with pytest.raises(ValueError, match="Kein HTML-Inhalt"):
            generate_pdf("", paper_size="portrait")

    @pytest.mark.unit
    def test_rejects_invalid_paper_size(self):
        with pytest.raises(ValueError, match="paper_size"):
            generate_pdf("<html></html>", paper_size="square")

    @pytest.mark.unit
    def test_portrait_pdf_dimensions_injected(self):
        html = _inject_print_css("<html><head></head><body></body></html>", "portrait")
        assert "size: 210mm 297mm" in html

    @pytest.mark.unit
    def test_landscape_pdf_dimensions_injected(self):
        html = _inject_print_css("<html><head></head><body></body></html>", "landscape")
        assert "size: 297mm 210mm" in html

    @pytest.mark.unit
    def test_chrome_pdf_params_landscape(self, mocker):
        mock_driver = mocker.MagicMock()
        mock_driver.execute_cdp_cmd.return_value = {"data": "dGVzdA=="}

        mock_chrome = mocker.patch("app.shared.pdf_generator.webdriver.Chrome")
        mock_chrome.return_value = mock_driver

        mocker.patch("os.fdopen")
        mocker.patch("tempfile.mkstemp", return_value=(3, "/tmp/test.html"))
        mocker.patch("pathlib.Path.unlink")

        result = generate_pdf("<html><body></body></html>", paper_size="landscape")

        call_args = mock_driver.execute_cdp_cmd.call_args_list
        pdf_calls = [c for c in call_args if c[0][0] == "Page.printToPDF"]
        assert len(pdf_calls) == 1
        pdf_args = pdf_calls[0][0][1]
        assert pdf_args["paperWidth"] == 11.69
        assert pdf_args["paperHeight"] == 8.27
        assert result == b"test"
