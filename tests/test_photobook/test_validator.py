"""Tests fuer den deterministischen Validator (angepasst an Presets)."""
from app.photobook.validator import validate_page
from app.state import PageDescription


def make_page(template_id, slots=None):
    return PageDescription(template_id=template_id, page_type="single", slots=slots or [])


class TestValidator:
    def test_valid_cover_hero_passes(self):
        page = make_page("cover_hero", slots=[
            {"slot_id": "main", "image_index": 0},
            {"slot_id": "title", "text": "Cover"},
        ])
        errors = validate_page(page)
        assert errors == []

    def test_overfill_rejected(self):
        page = make_page("cover_hero", slots=[
            {"slot_id": "main", "image_index": 0},
            {"slot_id": "main", "image_index": 1},
        ])
        errors = validate_page(page)
        assert len(errors) >= 1

    def test_unknown_preset_rejected(self):
        page = make_page("nonexistent", slots=[])
        errors = validate_page(page)
        assert len(errors) >= 1
        assert any("existiert" in e.lower() for e in errors)

    def test_missing_mandatory_image_rejected(self):
        page = make_page("double_dominant", slots=[
            {"slot_id": "main", "image_index": 0}
        ])
        errors = validate_page(page)
        assert len(errors) >= 1

    def test_negative_image_index_rejected(self):
        page = make_page("cover_hero", slots=[
            {"slot_id": "main", "image_index": -1},
        ])
        errors = validate_page(page)
        assert len(errors) >= 1

    def test_valid_quad_grid_passes(self):
        page = make_page("quad_grid", slots=[
            {"slot_id": "tl", "image_index": 0},
            {"slot_id": "tr", "image_index": 1},
            {"slot_id": "bl", "image_index": 2},
            {"slot_id": "br", "image_index": 3},
        ])
        errors = validate_page(page)
        assert not any("Bilder" in e for e in errors)


class TestEnforceFallback:
    def test_unknown_preset_fallback_by_count(self):
        from app.photobook.validator import enforce_fallback
        from app.state import PageDescription

        page = PageDescription(
            template_id="nonexistent",
            page_type="single",
            slots=[
                {"slot_id": "bad", "image_index": 5},
                {"slot_id": "bad2", "image_index": 10},
            ],
        )
        result = enforce_fallback(page)
        assert result.template_id != "nonexistent"
        from app.photobook.preset_loader import load_preset
        preset = load_preset(result.template_id)
        assert preset.image_count == 2

    def test_truncates_at_preset_image_count(self):
        from app.photobook.validator import enforce_fallback
        from app.state import PageDescription

        page = PageDescription(
            template_id="quad_grid",
            page_type="single",
            slots=[{"slot_id": "x", "image_index": i} for i in range(10)],
        )
        result = enforce_fallback(page)
        assert len(result.slots) <= 4

    def test_handles_empty_slots(self):
        from app.photobook.validator import enforce_fallback
        from app.state import PageDescription

        page = PageDescription(template_id="quad_grid", page_type="single", slots=[])
        result = enforce_fallback(page)
        assert result.template_id == "quad_grid"
        assert result.slots == []

    def test_handles_negative_indices(self):
        from app.photobook.validator import enforce_fallback
        from app.state import PageDescription

        page = PageDescription(
            template_id="quad_grid",
            page_type="single",
            slots=[
                {"slot_id": "x", "image_index": -1},
                {"slot_id": "y", "image_index": 3},
            ],
        )
        result = enforce_fallback(page)
        assert len(result.slots) == 1
        assert result.slots[0]["image_index"] == 3

    def test_enforce_fallback_truncates_long_text(self):
        from app.photobook.validator import enforce_fallback
        from app.state import PageDescription

        long_text = "X" * 200
        page = PageDescription(
            template_id="cover_hero",
            page_type="single",
            slots=[
                {"slot_id": "main", "image_index": 0},
                {"slot_id": "title", "text": long_text},
            ],
        )
        result = enforce_fallback(page)
        title_slot = next((s for s in result.slots if s.get("slot_id") == "title"), None)
        if title_slot:
            assert len(title_slot.get("text", "")) <= 60


class TestValidateAllPages:
    def test_returns_valid_pages_and_warnings(self):
        from app.photobook.validator import validate_all_pages
        from app.state import PageDescription

        pages = [
            PageDescription(template_id="cover_hero", page_type="single",
                          slots=[{"slot_id": "main", "image_index": 0}]),
            PageDescription(template_id="nonexistent", page_type="single", slots=[]),
            PageDescription(template_id="double_dominant", page_type="single",
                          slots=[
                              {"slot_id": "main", "image_index": 1},
                              {"slot_id": "secondary", "image_index": 2},
                          ]),
        ]
        validated, warnings = validate_all_pages(pages)
        assert len(validated) == 3
        assert len(warnings) >= 1

    def test_no_warnings_when_all_valid(self):
        from app.photobook.validator import validate_all_pages
        from app.state import PageDescription

        pages = [
            PageDescription(template_id="cover_hero", page_type="single",
                          slots=[{"slot_id": "main", "image_index": 0}]),
        ]
        validated, warnings = validate_all_pages(pages)
        assert len(warnings) == 0
