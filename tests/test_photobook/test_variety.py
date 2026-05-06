"""Tests fuer Variety-Enforcement im Validator."""
from app.photobook.validator import check_variety
from app.state import PageDescription


def make_page(preset_id: str) -> PageDescription:
    return PageDescription(template_id=preset_id, page_type="single", slots=[])


class TestVariety:
    def test_cover_hero_forced_on_first_page(self):
        pages = [
            make_page("single_full"),
            make_page("double_stacked"),
        ]
        result = check_variety(pages)
        assert result[0].template_id == "cover_hero"

    def test_no_back_to_back_same_preset(self):
        pages = [
            make_page("cover_hero"),
            make_page("double_stacked"),
            make_page("double_stacked"),
        ]
        result = check_variety(pages)
        assert result[2].template_id != "double_stacked"

    def test_max_3_no_text_pages_in_a_row(self):
        pages = [
            make_page("cover_hero"),
            make_page("single_full"),
            make_page("double_stacked"),
            make_page("triple_stacked"),
            make_page("quad_grid"),
        ]
        result = check_variety(pages)
        no_text_count = 0
        for i in range(1, len(result)):
            from app.photobook.preset_loader import load_preset
            preset = load_preset(result[i].template_id)
            if not preset.has_text:
                no_text_count += 1
            else:
                break
        assert no_text_count <= 3, f"{no_text_count} No-Text-Seiten in Folge"

    def test_empty_pages_list(self):
        result = check_variety([])
        assert result == []
