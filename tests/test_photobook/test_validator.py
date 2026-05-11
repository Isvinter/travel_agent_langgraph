"""Tests fuer den deterministischen Validator (angepasst an Presets)."""
from app.photobook.validator import validate_page
from app.state import PageDescription


def make_page(template_id, slots=None):
    return PageDescription(template_id=template_id, page_type="single", slots=slots or [])


class TestValidator:
    def test_valid_cover_hero_passes(self):
        """cover_hero hat keinen Text-Slot mehr — nur Bild, Titel via page-header."""
        page = make_page("cover_hero", slots=[
            {"slot_id": "main", "image_index": 0},
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
        page = make_page("double_stacked", slots=[
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
        assert len(result.slots) == 5  # 4 Bilder + 1 Titel

    def test_handles_empty_slots(self):
        from app.photobook.validator import enforce_fallback
        from app.state import PageDescription

        page = PageDescription(template_id="quad_grid", page_type="single", slots=[])
        result = enforce_fallback(page)
        assert result.template_id == "quad_grid"
        # quad_grid hat keine Text-Slots → nur title
        assert result.slots == [] or all(s.slot_id == "title" for s in result.slots)

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
        assert result.slots[0].image_index == 3  # 1 gültiges Bild
        assert len(result.slots) >= 1

    def test_enforce_fallback_truncates_long_text(self):
        from app.photobook.validator import enforce_fallback
        from app.state import PageDescription

        long_text = "X" * 200
        page = PageDescription(
            template_id="single_text_below",
            page_type="single",
            slots=[
                {"slot_id": "main", "image_index": 0},
                {"slot_id": "caption", "text": long_text},
            ],
        )
        result = enforce_fallback(page)
        caption_slot = next((s for s in result.slots if s.slot_id == "caption"), None)
        if caption_slot:
            assert len(caption_slot.text or "") <= 500


class TestValidateAllPages:
    def test_returns_valid_pages_and_warnings(self):
        from app.photobook.validator import validate_all_pages
        from app.state import PageDescription

        pages = [
            PageDescription(template_id="cover_hero", page_type="single",
                          slots=[{"slot_id": "main", "image_index": 0}]),
            PageDescription(template_id="nonexistent", page_type="single", slots=[]),
            PageDescription(template_id="double_stacked", page_type="single",
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

    def test_missing_text_slots_filled_with_placeholders(self):
        """Fehlende Text-Slots werden durch enforce_fallback mit Platzhaltern befüllt."""
        from app.photobook.validator import validate_all_pages
        from app.state import PageDescription

        pages = [
            PageDescription(template_id="cover_hero", page_type="single",
                          slots=[{"slot_id": "main", "image_index": 0}]),
        ]
        validated, _ = validate_all_pages(pages)
        assert len(validated) == 1
        title_slot = next((s for s in validated[0].slots if s.slot_id == "title"), None)
        assert title_slot is not None, "Title-Slot muss nach enforce_fallback vorhanden sein"
        assert (title_slot.text or "").strip() != "", "Title-Text darf nicht leer sein"

    def test_text_preserved_when_already_present(self):
        """Vorhandener LLM-Text bleibt durch enforce_fallback erhalten."""
        from app.photobook.validator import validate_all_pages
        from app.state import PageDescription

        # Zwei Seiten: cover_hero (page 0) + single_text_below (page 1)
        # Regel 1 erfordert cover_hero auf Seite 0
        pages = [
            PageDescription(template_id="cover_hero", page_type="single",
                          slots=[
                              {"slot_id": "main", "image_index": 0},
                          ]),
            PageDescription(template_id="single_text_below", page_type="single",
                          slots=[
                              {"slot_id": "main", "image_index": 1},
                              {"slot_id": "caption", "text": "Gipfelblick 2026"},
                          ]),
        ]
        validated, _ = validate_all_pages(pages)
        caption_slot = next((s for s in validated[1].slots if s.slot_id == "caption"), None)
        assert caption_slot is not None
        assert caption_slot.text == "Gipfelblick 2026"

    def test_replace_preset_fills_text_slots(self):
        """_replace_preset befüllt Text-Slots im neuen Preset mit Platzhaltern."""
        from app.photobook.validator import _replace_preset
        from app.state import PageDescription

        # simuliert: single_full (kein Text) wird durch single_text_below (mit Text) ersetzt
        page = PageDescription(
            template_id="single_full",
            page_type="single",
            slots=[{"slot_id": "main", "image_index": 0}],
        )
        result = _replace_preset(page, "single_text_below")
        caption_slot = next((s for s in result.slots if s.slot_id == "caption"), None)
        assert caption_slot is not None, "Caption-Slot muss nach Ersetzung vorhanden sein"
        assert (caption_slot.text or "").strip() != "", "Caption-Text darf nicht leer sein"
        # Bild muss erhalten bleiben
        assert any(s.slot_id == "main" for s in result.slots)

    def test_enforce_fallback_deduplicates_duplicate_slots(self):
        """Doppelte slot_ids (z.B. LLM generiert 2x caption) werden dedupliziert (last wins)."""
        from app.photobook.validator import enforce_fallback
        from app.state import PageDescription

        page = PageDescription(
            template_id="single_text_below",
            page_type="single",
            slots=[
                {"slot_id": "main", "image_index": 0},
                {"slot_id": "title", "text": "Alpenwiese"},
                {"slot_id": "caption", "text": "Erster Text, der überschrieben wurde"},
                {"slot_id": "caption", "text": "Zweiter Text, der sichtbar sein sollte"},
            ],
        )
        result = enforce_fallback(page)
        caption_slots = [s for s in result.slots if s.slot_id == "caption"]
        assert len(caption_slots) == 1, (
            f"Erwarte genau 1 caption-Slot, aber {len(caption_slots)} gefunden"
        )
        assert caption_slots[0].text == "Zweiter Text, der sichtbar sein sollte"

    def test_enforce_fallback_deduplicates_multiple_duplicates(self):
        """Mehrfache Duplikate unterschiedlicher slot_ids werden alle dedupliziert."""
        from app.photobook.validator import enforce_fallback
        from app.state import PageDescription

        page = PageDescription(
            template_id="image_text_split",
            page_type="single",
            slots=[
                {"slot_id": "image", "image_index": 0},
                {"slot_id": "title", "text": "Kapitel"},
                {"slot_id": "text", "text": "Text A"},
                {"slot_id": "text", "text": "Text B"},
                {"slot_id": "text", "text": "Text C (last wins)"},
            ],
        )
        result = enforce_fallback(page)
        text_slots = [s for s in result.slots if s.slot_id == "text"]
        assert len(text_slots) == 1, (
            f"Erwarte genau 1 text-Slot, aber {len(text_slots)} gefunden"
        )
        assert text_slots[0].text == "Text C (last wins)"

    def test_replace_preset_deduplicates_duplicate_slots(self):
        """_replace_preset dedupliziert doppelte slot_ids beim Preset-Wechsel."""
        from app.photobook.validator import _replace_preset
        from app.state import PageDescription

        page = PageDescription(
            template_id="double_stacked",
            page_type="single",
            slots=[
                {"slot_id": "top", "image_index": 0},
                {"slot_id": "bottom", "image_index": 1},
                {"slot_id": "caption", "text": "Text 1"},
                {"slot_id": "caption", "text": "Text 2 (last wins)"},
            ],
        )
        result = _replace_preset(page, "double_stacked_text")
        caption_slots = [s for s in result.slots if s.slot_id == "caption"]
        assert len(caption_slots) == 1, (
            f"Nach Preset-Wechsel erwarte genau 1 caption-Slot, aber {len(caption_slots)} gefunden"
        )
        assert caption_slots[0].text == "Text 2 (last wins)"

    def test_validate_all_pages_fills_text_for_all_presets_with_text(self):
        """Nach validate_all_pages haben alle text-fähigen Presets Text-Slots."""
        from app.photobook.validator import validate_all_pages
        from app.photobook.preset_loader import load_all_presets
        from app.state import PageDescription

        presets = load_all_presets()
        pages = []
        for pid, preset in presets.items():
            slots = []
            img_idx = 0
            for s in preset.slots:
                if s.type == "image":
                    slots.append({"slot_id": s.id, "image_index": img_idx})
                    img_idx += 1
            pages.append(PageDescription(template_id=pid, page_type="single", slots=slots))

        validated, _ = validate_all_pages(pages)

        for page in validated:
            preset = presets.get(page.template_id)
            if preset and preset.has_text:
                for sd in preset.slots:
                    if sd.type == "text":
                        slot = next((s for s in page.slots if s.slot_id == sd.id), None)
                        assert slot is not None, (
                            f"Text-Slot '{sd.id}' fehlt in Preset '{page.template_id}'"
                        )
                        assert (slot.text or "").strip() != "", (
                            f"Text-Slot '{sd.id}' in Preset '{page.template_id}' ist leer"
                        )


class TestTextMigration:
    """Text-Erhaltung bei verschiedenen Slot-Konstellationen."""

    def test_repair_slots_migrates_text_by_generic_fallback(self):
        """_repair_slots migriert verwaisten Text (slot_id='text') → ersten Text-Slot des neuen Presets."""
        from app.photobook.validator import _repair_slots
        from app.photobook.preset_loader import load_preset
        from app.state import PageSlot

        new_preset = load_preset("single_text_below")
        old_slots = [
            PageSlot(slot_id="main", image_index=0),
            PageSlot(slot_id="title", text="Historische Altstadt"),
            PageSlot(slot_id="text", text="Die verwinkelten Gassen der Altstadt..."),
        ]
        result = _repair_slots(new_preset, old_slots)
        caption_slot = next((s for s in result if s.get("slot_id") == "caption"), None)
        assert caption_slot is not None, "Caption-Slot muss nach Migration existieren"
        assert caption_slot["text"] == "Die verwinkelten Gassen der Altstadt...", (
            f"Text wurde nicht migriert: {caption_slot.get('text')!r}"
        )

    def test_repair_slots_catches_orphaned_text(self):
        """_repair_slots migriert verwaisten Text in den einzigen Text-Slot."""
        from app.photobook.validator import _repair_slots
        from app.photobook.preset_loader import load_preset
        from app.state import PageSlot

        new_preset = load_preset("panorama")
        old_slots = [
            PageSlot(slot_id="main", image_index=0),
            PageSlot(slot_id="title", text="Panoramablick"),
            PageSlot(slot_id="intro", text="Weites Bergpanorama im Abendlicht."),
        ]
        result = _repair_slots(new_preset, old_slots)
        caption_slot = next((s for s in result if s.get("slot_id") == "caption"), None)
        assert caption_slot is not None
        assert caption_slot["text"] == "Weites Bergpanorama im Abendlicht."

    def test_replace_preset_preserves_text_across_different_slot_ids(self):
        """_replace_preset erhält LLM-Text bei Wechsel image_text_split → single_text_below."""
        from app.photobook.validator import _replace_preset
        from app.state import PageDescription

        page = PageDescription(
            template_id="image_text_split",
            page_type="single",
            slots=[
                {"slot_id": "image", "image_index": 0},
                {"slot_id": "title", "text": "Altstadtgassen"},
                {"slot_id": "text", "text": "Fachwerkhäuser säumen den Weg durch das historische Viertel."},
            ],
        )
        result = _replace_preset(page, "single_text_below")
        caption_slot = next((s for s in result.slots if s.slot_id == "caption"), None)
        assert caption_slot is not None, "Caption-Slot muss nach Preset-Wechsel vorhanden sein"
        assert caption_slot.text == "Fachwerkhäuser säumen den Weg durch das historische Viertel.", (
            f"Text verloren: {caption_slot.text!r}"
        )

    def test_validate_all_pages_preserves_text_through_variety_replacement(self):
        """check_variety ersetzt Presets — Text muss ueberleben."""
        from app.photobook.validator import validate_all_pages
        from app.state import PageDescription

        pages = [
            PageDescription(template_id="cover_hero", page_type="single",
                          slots=[{"slot_id": "main", "image_index": 0}]),
            PageDescription(template_id="image_text_split", page_type="single",
                          slots=[
                              {"slot_id": "image", "image_index": 1},
                              {"slot_id": "title", "text": "Erste Gasse"},
                              {"slot_id": "text", "text": "Text der ersten Altstadtseite."},
                          ]),
            PageDescription(template_id="image_text_split", page_type="single",
                          slots=[
                              {"slot_id": "image", "image_index": 2},
                              {"slot_id": "title", "text": "Zweite Gasse"},
                              {"slot_id": "text", "text": "Text der zweiten Altstadtseite."},
                          ]),
            PageDescription(template_id="image_text_split", page_type="single",
                          slots=[
                              {"slot_id": "image", "image_index": 3},
                              {"slot_id": "title", "text": "Dritte Gasse"},
                              {"slot_id": "text", "text": "Text der dritten Altstadtseite."},
                          ]),
        ]
        validated, warnings = validate_all_pages(pages)

        for page in validated:
            text_slots = [
                s for s in page.slots
                if s.text and s.slot_id != "title" and s.text.strip() not in ("Bildbeschreibung", "Einleitungstext")
            ]
            if page.template_id != "cover_hero":
                assert len(text_slots) > 0, (
                    f"Seite '{page.template_id}' hat nur Platzhalter-Text: "
                    f"{[(s.slot_id, s.text) for s in page.slots if s.text]}"
                )

    def test_repair_slots_same_preset_preserves_text(self):
        """_repair_slots erhält Text bei gleichem Preset (Standardfall)."""
        from app.photobook.validator import _repair_slots
        from app.photobook.preset_loader import load_preset
        from app.state import PageSlot

        preset = load_preset("single_text_below")
        old_slots = [
            PageSlot(slot_id="main", image_index=0),
            PageSlot(slot_id="title", text="Alpenwiese"),
            PageSlot(slot_id="caption", text="Ein atemberaubender Weitblick."),
        ]
        result = _repair_slots(preset, old_slots)
        caption_slot = next((s for s in result if s.get("slot_id") == "caption"), None)
        assert caption_slot is not None
        assert caption_slot["text"] == "Ein atemberaubender Weitblick."
