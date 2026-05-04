"""Pipeline-Node zur PDF-Generierung aus dem fertigen Blogpost."""
import os
from pathlib import Path

from app.state import AppState
from app.services.generate_pdf import generate_pdf


def generate_pdf_node(state: AppState) -> AppState:
    """Generiert ein PDF aus dem generierten HTML-Blogpost (nur wenn pdf_export=True)."""
    print("📄 Generating PDF from blogpost...")

    if not state.blog_post or not state.blog_post.get("html"):
        print("⚠️ No HTML content available for PDF generation.")
        return state

    html_content = state.blog_post["html"]
    file_paths = state.blog_post.get("file_paths", {})
    html_path = file_paths.get("html", "")

    # Output-Verzeichnis aus html_path ableiten
    if html_path:
        output_dir = str(Path(html_path).parent)
    else:
        output_dir = "."

    try:
        pdf_bytes = generate_pdf(html_content, output_dir)

        # PDF-Datei im selben Verzeichnis wie die HTML-Datei speichern
        if html_path:
            pdf_path = html_path.replace(".html", ".pdf")
        else:
            pdf_path = os.path.join(output_dir, "blogpost.pdf")

        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)

        state.blog_post["pdf_bytes"] = pdf_bytes
        state.blog_post.setdefault("file_paths", {})["pdf"] = pdf_path
        print(f"✅ PDF saved ({len(pdf_bytes)} bytes) → {pdf_path}")
    except Exception as e:
        print(f"❌ PDF generation failed: {e}")
        state.blog_post["pdf_error"] = str(e)

    return state
