import logging
from datetime import datetime
from pathlib import Path
from app.state import AppState
from app.photobook.generate_pdf import generate_photobook_pdf
from app.config import OUTPUT_DIR

logger = logging.getLogger(__name__)


def generate_photobook_pdf_node(state: AppState) -> AppState:
    logger.info("Erzeuge Fotobuch-PDF...")
    if not state.photobook_html:
        logger.warning("Kein HTML zum PDF-Export vorhanden.")
        return state
    try:
        pdf_bytes = generate_photobook_pdf(state.photobook_html, source_path=state.photobook_html_path)
        timestamp = state.photobook_timestamp or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_dir = Path(OUTPUT_DIR) / f"photobook_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = output_dir / f"{timestamp}_photobook.pdf"
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        state.photobook_pdf_path = str(pdf_path)
        logger.info("PDF gespeichert: %s (%s Bytes)", pdf_path, len(pdf_bytes))
    except Exception as e:
        logger.error("Fehler bei PDF-Generierung: %s", e)
    return state
