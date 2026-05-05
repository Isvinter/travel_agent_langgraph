import os
from datetime import datetime
from pathlib import Path
from app.state import AppState
from app.photobook.generate_pdf import generate_photobook_pdf
from app.config import OUTPUT_DIR


def generate_photobook_pdf_node(state: AppState) -> AppState:
    print("📄 Erzeuge Fotobuch-PDF...")
    if not state.photobook_html:
        print("⚠️ Kein HTML zum PDF-Export vorhanden.")
        return state
    try:
        pdf_bytes = generate_photobook_pdf(state.photobook_html)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_dir = Path(OUTPUT_DIR) / f"photobook_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = output_dir / f"{timestamp}_photobook.pdf"
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        state.photobook_pdf_path = str(pdf_path)
        print(f"✅ PDF gespeichert: {pdf_path} ({len(pdf_bytes)} Bytes)")
    except Exception as e:
        print(f"❌ Fehler bei PDF-Generierung: {e}")
    return state
