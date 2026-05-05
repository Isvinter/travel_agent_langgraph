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
                template_id="hero_single",
                page_type="single",
                slots=[{"slot_id": "main", "image_index": 0, "caption": "Cover"}],
            )
        ]
        html = render_photobook(pages, TEST_IMAGES)
        assert "<!DOCTYPE html>" in html
        assert "layout-hero-single" in html
        assert "slot-image" in html
        assert "Cover" in html

    def test_render_spread_has_correct_dimensions(self):
        pages = [
            PageDescription(
                template_id="split_equal",
                page_type="spread",
                slots=[
                    {"slot_id": "left", "image_index": 0},
                    {"slot_id": "right", "image_index": 1},
                ],
            )
        ]
        html = render_photobook(pages, TEST_IMAGES)
        assert "page-spread" in html
        assert "layout-split-equal" in html

    def test_render_multiple_pages(self):
        pages = [
            PageDescription(template_id="hero_single", page_type="single", slots=[{"slot_id": "main", "image_index": 0}]),
            PageDescription(template_id="grid_2x2", page_type="single", slots=[
                {"slot_id": "tl", "image_index": 0},
                {"slot_id": "tr", "image_index": 1},
                {"slot_id": "bl", "image_index": 2},
                {"slot_id": "br", "image_index": 3},
            ]),
        ]
        html = render_photobook(pages, TEST_IMAGES)
        assert html.count("slot-image") >= 5
        assert "layout-hero-single" in html
        assert "layout-grid-2x2" in html

    def test_render_includes_css_classes(self):
        pages = [
            PageDescription(template_id="hero_single", page_type="single", slots=[{"slot_id": "main", "image_index": 0}]),
        ]
        html = render_photobook(pages, TEST_IMAGES)
        assert "grid-template-areas" in html

    def test_render_text_slot(self):
        pages = [
            PageDescription(
                template_id="image_text_left",
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
