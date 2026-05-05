# tests/test_photobook/test_template_loader.py
import pytest
from app.photobook.template_loader import (
    load_template,
    load_all_templates,
)


class TestTemplateLoader:
    def test_load_hero_single(self):
        template = load_template("hero_single")
        assert template.id == "hero_single"
        assert template.page_type == "single"
        assert template.min_images == 1
        assert template.max_images == 1
        assert len(template.slots) >= 1
        main_slot = [s for s in template.slots if s.priority == "primary"]
        assert len(main_slot) == 1

    def test_load_split_dominant(self):
        template = load_template("split_dominant")
        assert template.id == "split_dominant"
        assert template.page_type == "spread"
        assert template.max_images == 2
        slot_ids = [s.id for s in template.slots]
        assert "primary" in slot_ids
        assert "secondary" in slot_ids

    def test_load_all_templates_returns_dict(self):
        templates = load_all_templates()
        assert isinstance(templates, dict)
        assert len(templates) >= 8
        assert "hero_single" in templates
        assert "grid_2x2" in templates
        assert "panorama" in templates

    def test_unknown_template_raises(self):
        with pytest.raises(FileNotFoundError):
            load_template("nonexistent_layout")

    def test_all_templates_have_valid_slots(self):
        templates = load_all_templates()
        for tid, tmpl in templates.items():
            for slot in tmpl.slots:
                assert slot.type in ("image", "text", "caption"), (
                    f"{tid}: slot {slot.id} has invalid type {slot.type}"
                )
                assert slot.css_area, f"{tid}: slot {slot.id} has no css_area"
