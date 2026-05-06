"""Tests fuer Char-Limit-Truncation im Validator."""
from app.photobook.validator import validate_page, enforce_fallback
from app.state import PageDescription


class TestTextOverflow:
    def test_text_within_limit_passes(self):
        page = PageDescription(
            template_id="single_text_below",
            page_type="single",
            slots=[
                {"slot_id": "main", "image_index": 0},
                {"slot_id": "caption", "text": "Kurzer Titel"},
            ],
        )
        errors = validate_page(page)
        assert errors == []

    def test_text_exceeding_limit_reported(self):
        long_text = "X" * 600
        page = PageDescription(
            template_id="single_text_below",
            page_type="single",
            slots=[
                {"slot_id": "main", "image_index": 0},
                {"slot_id": "caption", "text": long_text},
            ],
        )
        errors = validate_page(page)
        assert len(errors) >= 1
        assert any("Zeichen" in e for e in errors)

    def test_enforce_fallback_truncates_text(self):
        long_text = "A" * 600
        page = PageDescription(
            template_id="single_text_below",
            page_type="single",
            slots=[
                {"slot_id": "main", "image_index": 0},
                {"slot_id": "caption", "text": long_text},
            ],
        )
        result = enforce_fallback(page)
        caption_slot = next((s for s in result.slots if s.get("slot_id") == "caption"), None)
        assert caption_slot is not None
        assert len(caption_slot["text"]) <= 500
