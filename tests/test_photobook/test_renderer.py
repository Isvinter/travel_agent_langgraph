"""Tests fuer den Fotobuch-Renderer."""
from app.state import PageDescription, ImageData
from app.photobook.renderer import render_photobook

TEST_IMAGES = [
    ImageData(path="/tmp/test_img_0.jpg", timestamp=None, latitude=None, longitude=None),
    ImageData(path="/tmp/test_img_1.jpg", timestamp=None, latitude=None, longitude=None),
    ImageData(path="/tmp/test_img_2.jpg", timestamp=None, latitude=None, longitude=None),
    ImageData(path="/tmp/test_img_3.jpg", timestamp=None, latitude=None, longitude=None),
]


class TestRenderer:
    def test_render_single_page_hero(self):
        pages = [
            PageDescription(
                template_id="cover_hero",
                page_type="single",
                slots=[
                    {"slot_id": "main", "image_index": 0},
                    {"slot_id": "title", "text": "Cover"},
                ],
            )
        ]
        html = render_photobook(pages, TEST_IMAGES)
        assert "<!DOCTYPE html>" in html
        assert "preset-cover-hero" in html
        assert "slot-image" in html
        assert "Cover" in html

    def test_caption_uses_correct_grid_area(self):
        """Caption soll im dedizierten caption-grid-area landen, nicht im image-grid-area."""
        pages = [
            PageDescription(
                template_id="panorama",
                page_type="single",
                slots=[
                    {"slot_id": "main", "image_index": 0},
                    {"slot_id": "caption", "text": "Panorama-Blick"},
                ],
            )
        ]
        html = render_photobook(pages, TEST_IMAGES)
        # Caption muss im grid-area: caption erscheinen, nicht grid-area: main
        assert 'slot-caption' in html
        # Der caption-Slot des panorama presets hat css_area="caption"
        assert 'grid-area: caption' in html

    def test_render_includes_page_header(self):
        """Nicht-Cover-Seiten haben einen page-header mit Titel."""
        pages = [
            PageDescription(template_id="single_full", page_type="single",
                          slots=[{"slot_id": "main", "image_index": 0}]),
        ]
        html = render_photobook(pages, TEST_IMAGES)
        assert "page-header" in html
        assert "page-title" in html
        assert "page-content" in html

    def test_render_cover_page_has_overlay(self):
        """Cover-Seite hat kein page-header sondern ein cover-overlay."""
        pages = [
            PageDescription(template_id="cover_hero", page_type="single",
                          slots=[{"slot_id": "main", "image_index": 0}]),
        ]
        html = render_photobook(pages, TEST_IMAGES)
        assert "cover-page" in html
        assert "cover-overlay" in html
        assert "cover-image" in html
        assert '<div class="page-header">' not in html  # Cover hat kein page-header

    def test_render_title_in_header_not_in_content(self):
        """Title-Slot wird im page-header einer normalen Seite gerendert."""
        pages = [
            PageDescription(template_id="single_full", page_type="single",
                          slots=[
                              {"slot_id": "main", "image_index": 0},
                              {"slot_id": "title", "text": "Mein Titel"},
                          ]),
        ]
        html = render_photobook(pages, TEST_IMAGES)
        assert '<div class="page-title">Mein Titel</div>' in html

    def test_render_fallback_title(self):
        """Ohne title-Slot wird 'Seite N' als Fallback verwendet."""
        pages = [
            PageDescription(template_id="single_full", page_type="single",
                          slots=[{"slot_id": "main", "image_index": 0}]),
        ]
        html = render_photobook(pages, TEST_IMAGES)
        assert '<div class="page-title">Seite 1</div>' in html

    def test_render_double_stacked(self):
        """double_stacked: 2 Bilder vertikal, keine Text-Slots."""
        pages = [
            PageDescription(template_id="double_stacked", page_type="single",
                          slots=[
                              {"slot_id": "top", "image_index": 0},
                              {"slot_id": "bottom", "image_index": 1},
                          ]),
        ]
        html = render_photobook(pages, TEST_IMAGES)
        assert "preset-double-stacked" in html
        assert html.count("slot-image") >= 2

    def test_render_double_stacked_text(self):
        """double_stacked_text: 2 Bilder + caption."""
        pages = [
            PageDescription(template_id="double_stacked_text", page_type="single",
                          slots=[
                              {"slot_id": "top", "image_index": 0},
                              {"slot_id": "bottom", "image_index": 1},
                              {"slot_id": "caption", "text": "Waldpfad"},
                          ]),
        ]
        html = render_photobook(pages, TEST_IMAGES)
        assert "preset-double-stacked-text" in html
        assert "Waldpfad" in html

    def test_render_quad_grid_text(self):
        """quad_grid_text: 2x2 Raster + caption."""
        pages = [
            PageDescription(template_id="quad_grid_text", page_type="single",
                          slots=[
                              {"slot_id": "tl", "image_index": 0},
                              {"slot_id": "tr", "image_index": 1},
                              {"slot_id": "bl", "image_index": 2},
                              {"slot_id": "br", "image_index": 3},
                              {"slot_id": "caption", "text": "Rundumblick"},
                          ]),
        ]
        html = render_photobook(pages, TEST_IMAGES)
        assert "preset-quad-grid-text" in html
        assert "Rundumblick" in html

    def test_render_multiple_pages(self):
        pages = [
            PageDescription(template_id="cover_hero", page_type="single", slots=[{"slot_id": "main", "image_index": 0}]),
            PageDescription(template_id="quad_grid", page_type="single", slots=[
                {"slot_id": "tl", "image_index": 0},
                {"slot_id": "tr", "image_index": 1},
                {"slot_id": "bl", "image_index": 2},
                {"slot_id": "br", "image_index": 3},
            ]),
        ]
        html = render_photobook(pages, TEST_IMAGES)
        assert html.count("slot-image") >= 5
        assert "preset-cover-hero" in html
        assert "preset-quad-grid" in html

    def test_render_includes_css_classes(self):
        pages = [
            PageDescription(template_id="cover_hero", page_type="single", slots=[{"slot_id": "main", "image_index": 0}]),
        ]
        html = render_photobook(pages, TEST_IMAGES)
        assert "grid-template-areas" in html

    def test_render_text_slot(self):
        pages = [
            PageDescription(
                template_id="image_text_split",
                page_type="spread",
                slots=[
                    {"slot_id": "image", "image_index": 0},
                    {"slot_id": "text", "text": "Einleitungstext zur Tour"},
                ],
            )
        ]
        html = render_photobook(pages, TEST_IMAGES)
        assert "Einleitungstext zur Tour" in html
        assert "slot-text" in html

    def test_render_title_slot(self):
        """Title-Slot wird als slot-title gerendert."""
        pages = [
            PageDescription(
                template_id="cover_hero",
                page_type="single",
                slots=[
                    {"slot_id": "title", "text": "Gipfelstürmer"},
                    {"slot_id": "main", "image_index": 0},
                ],
            )
        ]
        html = render_photobook(pages, TEST_IMAGES)
        assert "slot-title" in html
        assert "Gipfelstürmer" in html


class TestPresetRenderer:
    def test_cover_hero_uses_preset_css_class(self):
        """Renderer muss preset-cover-hero CSS-Klasse verwenden."""
        from app.photobook.renderer import render_photobook
        from app.state import PageDescription, ImageData
        from app.photobook.preset_loader import load_preset

        preset = load_preset("cover_hero")
        page = PageDescription(
            template_id="cover_hero",
            page_type="single",
            slots=[
                {"slot_id": "main", "image_index": 0},
                {"slot_id": "title", "text": "Mein Fotobuch"},
            ],
        )
        images = [ImageData(path="/tmp/test.jpg")]
        html = render_photobook([page], images)
        assert "preset-cover-hero" in html
