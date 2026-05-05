"""Tests fuer den deterministischen Validator."""
import pytest
from app.photobook.validator import validate_page
from app.state import PageDescription


def make_page(template_id, slots=None):
    return PageDescription(template_id=template_id, page_type="single", slots=slots or [])


class TestValidator:
    def test_valid_hero_single_passes(self):
        page = make_page("hero_single", slots=[
            {"slot_id": "main", "image_index": 0, "caption": "Cover"}
        ])
        errors = validate_page(page)
        assert errors == []

    def test_overfill_rejected(self):
        page = make_page("hero_single", slots=[
            {"slot_id": "main", "image_index": 0},
            {"slot_id": "main", "image_index": 1},
        ])
        errors = validate_page(page)
        assert len(errors) == 1
        assert any("Bilder" in e or "max_images" in e.lower() for e in errors)

    def test_unknown_template_rejected(self):
        page = make_page("nonexistent", slots=[])
        errors = validate_page(page)
        assert len(errors) >= 1
        assert any("existiert" in e.lower() or "unknown" in e.lower() for e in errors)

    def test_missing_mandatory_slot_rejected(self):
        page = make_page("split_dominant", slots=[
            {"slot_id": "primary", "image_index": 0}
        ])
        errors = validate_page(page)
        assert len(errors) >= 1
        assert any("secondary" in e.lower() or "slot" in e.lower() for e in errors)

    def test_negative_image_index_rejected(self):
        page = make_page("hero_single", slots=[
            {"slot_id": "main", "image_index": -1, "caption": "Bad index"}
        ])
        errors = validate_page(page)
        assert len(errors) >= 1

    def test_empty_slots_for_partial_grid_passes(self):
        page = make_page("grid_2x2", slots=[
            {"slot_id": "tl", "image_index": 0},
            {"slot_id": "tr", "image_index": 1},
            {"slot_id": "bl", "image_index": 2},
        ])
        errors = validate_page(page)
        assert errors == []
