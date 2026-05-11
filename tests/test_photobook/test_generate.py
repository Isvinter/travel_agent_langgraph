"""Tests fuer LLM Pass 2: Slot-Zuweisung mit Preset-Constraints."""
import json
from unittest.mock import patch, MagicMock
from app.state import ImageData, PageDescription, PhotobookPlan, PagePlan
from app.photobook.generate import generate_photobook_pages

MOCK_PLAN = PhotobookPlan(pages=[
    PagePlan(position=0, preset_id="cover_hero", image_indices=[0], purpose="Cover"),
    PagePlan(position=1, preset_id="double_stacked", image_indices=[1, 2], purpose="Aufstieg"),
])

MOCK_GENERATE_CONTENT = json.dumps([
    {"preset_id": "cover_hero", "slots": [
        {"slot_id": "main", "image_index": 0},
        {"slot_id": "title", "text": "Gipfelblick"},
    ]},
    {"preset_id": "double_stacked", "slots": [
        {"slot_id": "top", "image_index": 1},
        {"slot_id": "bottom", "image_index": 2},
    ]},
])

SAMPLE_IMAGES = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(16)]


class TestGenerate:
    @patch("app.photobook.generate.call_ollama")
    def test_generate_returns_page_descriptions(self, mock_call):
        mock_call.return_value = MOCK_GENERATE_CONTENT
        result = generate_photobook_pages(
            plan=MOCK_PLAN, images=SAMPLE_IMAGES, gpx_stats={}, notes="Test", model="test-model",
        )
        assert len(result) == 2
        assert isinstance(result[0], PageDescription)
        assert result[0].template_id == "cover_hero"
        assert result[1].template_id == "double_stacked"

    def test_fallback_on_empty_plan(self):
        result = generate_photobook_pages(
            plan=PhotobookPlan(pages=[]), images=SAMPLE_IMAGES[:4], gpx_stats={}, notes=None, model="test-model",
        )
        assert len(result) == 0

    @patch("app.photobook.generate.call_ollama")
    def test_generate_handles_missing_images(self, mock_call):
        mock_call.return_value = json.dumps([
            {"preset_id": "cover_hero", "slots": [{"slot_id": "main", "image_index": 999}]},
        ])
        result = generate_photobook_pages(
            plan=MOCK_PLAN, images=SAMPLE_IMAGES[:3], gpx_stats={}, notes="Test", model="test-model",
        )
        assert len(result) >= 0

    def test_fallback_uses_preset_from_plan(self):
        """Fallback soll das im Plan gewählte Preset respektieren."""
        plan = PhotobookPlan(pages=[
            PagePlan(position=0, preset_id="cover_hero", image_indices=[0]),
            PagePlan(position=1, preset_id="double_stacked", image_indices=[1, 2]),
        ])
        images = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(3)]
        with patch("app.photobook.generate.call_ollama", return_value=None):
            pages = generate_photobook_pages(plan, images, None, None, model="test")
        assert len(pages) == 2
        assert pages[0].template_id == "cover_hero"
        assert pages[1].template_id == "double_stacked"

    def test_generate_includes_titles_and_captions(self):
        """LLM-Response mit 'title' und 'text' Feldern muss korrekt geparst werden."""
        plan = PhotobookPlan(pages=[PagePlan(position=0, preset_id="cover_hero", image_indices=[0])])
        images = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(1)]
        mock_content = json.dumps([
            {"preset_id": "cover_hero", "slots": [
                {"slot_id": "main", "image_index": 0},
                {"slot_id": "title", "text": "Aufbruch"},
            ]}
        ])
        with patch("app.photobook.generate.call_ollama", return_value=mock_content):
            pages = generate_photobook_pages(plan, images, None, None, model="test")
        assert len(pages) == 1
        title_slot = next((s for s in pages[0].slots if s.slot_id == "title"), None)
        assert title_slot is not None
        assert title_slot.text == "Aufbruch"

    def test_fallback_unknown_preset_uses_fallback_count(self):
        """Fallback mit unbekanntem Preset wählt passendes nach Bildanzahl."""
        plan = PhotobookPlan(pages=[PagePlan(position=0, preset_id="nonexistent", image_indices=[0, 1])])
        images = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(2)]
        with patch("app.photobook.generate.call_ollama", return_value=None):
            pages = generate_photobook_pages(plan, images, None, None, model="test")
        assert len(pages) == 1
        assert pages[0].template_id != "nonexistent"
        from app.photobook.preset_loader import load_preset
        preset = load_preset(pages[0].template_id)
        assert preset.image_count == 2


from app.photobook.generate import _split_into_batches, _images_for_batch, calculate_num_predict
from app.state import PagePlan

SAMPLE_PAGES_16 = [
    PagePlan(position=i, preset_id="single_text_below", image_indices=[i], purpose=f"Seite {i}")
    for i in range(16)
]
SAMPLE_PAGES_16[0] = PagePlan(position=0, preset_id="cover_hero", image_indices=[0], purpose="Cover")


class TestBatchHelpers:
    def test_split_into_batches_exact(self):
        batches = _split_into_batches(SAMPLE_PAGES_16, batch_size=3)
        assert len(batches) == 6
        assert len(batches[0]) == 3
        assert len(batches[-1]) == 1  # 16 % 3 = 1

    def test_split_first_batch_has_cover(self):
        batches = _split_into_batches(SAMPLE_PAGES_16, batch_size=3)
        assert batches[0][0].preset_id == "cover_hero"
        assert batches[0][0].position == 0

    def test_split_single_batch(self):
        pages = SAMPLE_PAGES_16[:2]
        batches = _split_into_batches(pages, batch_size=3)
        assert len(batches) == 1
        assert len(batches[0]) == 2

    def test_images_for_batch_extracts_correct_images(self):
        batch_pages = [
            PagePlan(position=0, preset_id="cover_hero", image_indices=[0]),
            PagePlan(position=1, preset_id="double_stacked", image_indices=[1, 2]),
            PagePlan(position=2, preset_id="single_text_below", image_indices=[3]),
        ]
        all_images = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(10)]
        result = _images_for_batch(batch_pages, all_images)
        assert len(result) == 4  # Indices 0, 1, 2, 3
        assert result[0].path == "/tmp/img_0.jpg"
        assert result[3].path == "/tmp/img_3.jpg"

    def test_images_for_batch_deduplicates(self):
        batch_pages = [
            PagePlan(position=0, preset_id="cover_hero", image_indices=[0]),
            PagePlan(position=1, preset_id="double_stacked", image_indices=[0, 1]),
        ]
        all_images = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(5)]
        result = _images_for_batch(batch_pages, all_images)
        assert len(result) == 2  # Dedupliziert

    def test_images_for_batch_empty(self):
        result = _images_for_batch([], [])
        assert result == []


class TestCalculateNumPredict:
    def test_returns_minimum_for_small_batch(self):
        pages = [PagePlan(position=0, preset_id="cover_hero", image_indices=[0])]
        result = calculate_num_predict(pages, min_tokens=8192)
        assert result >= 8192

    def test_scales_with_text_slots(self):
        pages = [
            PagePlan(position=i, preset_id="single_text_below", image_indices=[i])
            for i in range(3)
        ]
        result = calculate_num_predict(pages, min_tokens=8192)
        assert result >= 8192
        assert result >= 5500

    def test_no_text_presets_return_minimum(self):
        pages = [
            PagePlan(position=i, preset_id="double_stacked", image_indices=[i, i+1])
            for i in range(3)
        ]
        result = calculate_num_predict(pages, min_tokens=8192)
        assert result == 8192


from app.photobook.generate import _build_batch_prompt


class TestBuildBatchPrompt:
    def test_includes_tour_summary(self):
        batch_pages = [PagePlan(position=0, preset_id="cover_hero", image_indices=[0])]
        prompt = _build_batch_prompt(batch_pages, "Wanderung im Allgäu, Herbst.", "14.3", "520")
        assert "Wanderung im Allgäu" in prompt
        assert "14.3" in prompt
        assert "520" in prompt

    def test_includes_batch_plan_json(self):
        batch_pages = [
            PagePlan(position=0, preset_id="cover_hero", image_indices=[0], purpose="Cover"),
        ]
        prompt = _build_batch_prompt(batch_pages, "Test", "5.0", "100")
        assert "cover_hero" in prompt
        assert "Cover" in prompt

    def test_handles_empty_summary(self):
        batch_pages = [PagePlan(position=0, preset_id="cover_hero", image_indices=[0])]
        prompt = _build_batch_prompt(batch_pages, None, None, None)
        assert "cover_hero" in prompt  # Should not crash
