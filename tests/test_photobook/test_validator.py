"""Tests fuer den deterministischen Validator."""
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


class TestEnforceFallback:
    def test_converts_to_grid_2x2(self):
        """enforce_fallback wandelt in grid_2x2 mit korrekten Slot-IDs um."""
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
        assert result.template_id == "grid_2x2"
        assert result.page_type == "single"
        assert result.slots[0]["slot_id"] == "tl"
        assert result.slots[0]["image_index"] == 5
        assert result.slots[1]["slot_id"] == "tr"
        assert result.slots[1]["image_index"] == 10

    def test_truncates_at_4_images(self):
        """enforce_fallback kappt bei maximal 4 Bildern."""
        from app.photobook.validator import enforce_fallback
        from app.state import PageDescription

        page = PageDescription(
            template_id="bad",
            page_type="single",
            slots=[
                {"slot_id": "x", "image_index": i} for i in range(10)
            ],
        )
        result = enforce_fallback(page)
        assert len(result.slots) == 4

    def test_handles_empty_slots(self):
        """enforce_fallback vertraegt leere Slot-Liste."""
        from app.photobook.validator import enforce_fallback
        from app.state import PageDescription

        page = PageDescription(template_id="bad", page_type="single", slots=[])
        result = enforce_fallback(page)
        assert result.template_id == "grid_2x2"
        assert result.slots == []

    def test_handles_negative_indices(self):
        """enforce_fallback filtert negative Indizes heraus."""
        from app.photobook.validator import enforce_fallback
        from app.state import PageDescription

        page = PageDescription(
            template_id="bad",
            page_type="single",
            slots=[
                {"slot_id": "x", "image_index": -1},
                {"slot_id": "y", "image_index": 3},
            ],
        )
        result = enforce_fallback(page)
        assert len(result.slots) == 1
        assert result.slots[0]["image_index"] == 3

    def test_enforce_fallback_preserves_captions(self):
        """Captions aus der Original-Seite muessen im Fallback erhalten bleiben."""
        from app.photobook.validator import enforce_fallback
        from app.state import PageDescription

        page = PageDescription(
            template_id="hero_single",
            page_type="single",
            slots=[
                {"slot_id": "main", "image_index": 0, "caption": "Schöne Aussicht"},
                {"slot_id": "wrong_slot", "image_index": 1},
            ],
        )
        result = enforce_fallback(page)
        captions = [s.get("caption", "") for s in result.slots]
        assert "Schöne Aussicht" in captions

    def test_enforce_fallback_preserves_template_when_possible(self):
        """Wenn nur ein Slot-Name falsch ist, soll das Template erhalten bleiben."""
        from app.photobook.validator import enforce_fallback
        from app.state import PageDescription

        page = PageDescription(
            template_id="split_equal",
            page_type="spread",
            slots=[
                {"slot_id": "left_", "image_index": 0},
                {"slot_id": "right", "image_index": 1},
            ],
        )
        result = enforce_fallback(page)
        assert result.template_id == "split_equal"
        slot_ids = [s.get("slot_id", "") for s in result.slots]
        assert "left" in slot_ids


class TestValidateAllPages:
    def test_returns_valid_pages_and_warnings(self):
        """validate_all_pages trennt gueltige und fehlerhafte Seiten."""
        from app.photobook.validator import validate_all_pages
        from app.state import PageDescription

        pages = [
            PageDescription(template_id="hero_single", page_type="single",
                          slots=[{"slot_id": "main", "image_index": 0}]),
            PageDescription(template_id="nonexistent", page_type="single", slots=[]),
            PageDescription(template_id="split_dominant", page_type="spread",
                          slots=[
                              {"slot_id": "primary", "image_index": 1},
                              {"slot_id": "secondary", "image_index": 2},
                          ]),
        ]
        validated, warnings = validate_all_pages(pages)
        assert len(validated) == 3
        assert len(warnings) == 1
        assert "Seite 1" in warnings[0]
        # Die fehlerhafte Seite wurde in grid_2x2 umgewandelt
        assert validated[1].template_id == "grid_2x2"

    def test_no_warnings_when_all_valid(self):
        """validate_all_pages produziert keine Warnungen bei gueltigen Seiten."""
        from app.photobook.validator import validate_all_pages
        from app.state import PageDescription

        pages = [
            PageDescription(template_id="hero_single", page_type="single",
                          slots=[{"slot_id": "main", "image_index": 0}]),
        ]
        validated, warnings = validate_all_pages(pages)
        assert len(warnings) == 0
        assert validated[0].template_id == "hero_single"
