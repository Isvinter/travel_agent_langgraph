"""Integrationstests für Bildkompression im render_photobook_node."""
import os
import pytest
from PIL import Image
from app.state import AppState, PageDescription, ImageData
from app.nodes.render_photobook_node import render_photobook_node


def _make_test_image(path: str, size=(2000, 1500), color="red"):
    """Erzeugt ein Testbild und speichert es."""
    img = Image.new("RGB", size, color=color)
    img.save(path)
    return path


class TestRenderPhotobookNodeCompression:
    """Testet dass render_photobook_node Bilder vor dem Rendern komprimiert."""

    @pytest.mark.integration
    def test_compresses_images_before_rendering(self, tmp_path, monkeypatch):
        """Node soll komprimierte Bildkopien im output-Verzeichnis erzeugen."""
        output_dir = str(tmp_path / "output")
        monkeypatch.setattr("app.nodes.render_photobook_node.OUTPUT_DIR", output_dir)

        # Testbilder erstellen (gross, damit Kompression greift)
        img_dir = tmp_path / "images"
        img_dir.mkdir()
        img_paths = []
        for i in range(3):
            p = str(img_dir / f"photo_{i}.jpg")
            _make_test_image(p, size=(2000, 1500))
            img_paths.append(p)

        # State vorbereiten
        state = AppState(
            photobook_images=[
                ImageData(path=img_paths[0]),
                ImageData(path=img_paths[1]),
                ImageData(path=img_paths[2]),
            ],
            photobook_pages=[
                PageDescription(
                    template_id="hero_single",
                    page_type="single",
                    slots=[{"slot_id": "main", "image_index": 0}],
                ),
            ],
        )

        result = render_photobook_node(state)

        # HTML muss erzeugt worden sein
        assert result.photobook_html is not None
        assert "slot-image" in result.photobook_html

        # Bild-Pfade im HTML müssen auf komprimierte Kopien im output-Verzeichnis zeigen
        assert output_dir in result.photobook_html

        # Originale müssen unverändert existieren
        for p in img_paths:
            assert os.path.exists(p)

    @pytest.mark.integration
    def test_handles_empty_image_list(self, tmp_path, monkeypatch):
        """Leere photobook_images-Liste sollte keinen Fehler werfen."""
        output_dir = str(tmp_path / "output")
        monkeypatch.setattr("app.nodes.render_photobook_node.OUTPUT_DIR", output_dir)

        state = AppState(
            photobook_images=[],
            photobook_pages=[
                PageDescription(
                    template_id="hero_single",
                    page_type="single",
                    slots=[{"slot_id": "main", "image_index": 0}],
                ),
            ],
        )

        result = render_photobook_node(state)
        assert result.photobook_html is not None

    @pytest.mark.integration
    def test_handles_missing_image_file(self, tmp_path, monkeypatch):
        """Nicht existierende Bilddateien sollten nicht crashen."""
        output_dir = str(tmp_path / "output")
        monkeypatch.setattr("app.nodes.render_photobook_node.OUTPUT_DIR", output_dir)

        state = AppState(
            photobook_images=[
                ImageData(path="/nonexistent/path/photo.jpg"),
            ],
            photobook_pages=[
                PageDescription(
                    template_id="hero_single",
                    page_type="single",
                    slots=[{"slot_id": "main", "image_index": 0}],
                ),
            ],
        )

        result = render_photobook_node(state)
        assert result.photobook_html is not None
