"""Tests fuer LLM Pass 1: Preset-Auswahl."""
import json
from unittest.mock import patch, MagicMock
from app.state import ImageData
from app.photobook.plan import plan_photobook_layout

SAMPLE_IMAGES = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(16)]

MOCK_PLAN_CONTENT = json.dumps({
    "pages": [
        {"position": 0, "preset_id": "cover_hero", "image_indices": [3], "purpose": "Cover"},
        {"position": 1, "preset_id": "double_stacked", "image_indices": [7, 12], "purpose": "Aufstieg"},
        {"position": 2, "preset_id": "single_full", "image_indices": [0], "purpose": "Start"},
        {"position": 3, "preset_id": "single_full", "image_indices": [1], "purpose": "Weg"},
        {"position": 4, "preset_id": "single_full", "image_indices": [2], "purpose": "Weg"},
        {"position": 5, "preset_id": "single_full", "image_indices": [4], "purpose": "Weg"},
        {"position": 6, "preset_id": "single_full", "image_indices": [5], "purpose": "Weg"},
        {"position": 7, "preset_id": "double_stacked", "image_indices": [6, 8], "purpose": "Aufbau"},
        {"position": 8, "preset_id": "single_full", "image_indices": [9], "purpose": "Hoehepunkt"},
        {"position": 9, "preset_id": "single_full", "image_indices": [10], "purpose": "Hoehepunkt"},
        {"position": 10, "preset_id": "single_full", "image_indices": [11], "purpose": "Hoehepunkt"},
        {"position": 11, "preset_id": "single_full", "image_indices": [13], "purpose": "Ausklang"},
        {"position": 12, "preset_id": "single_full", "image_indices": [14], "purpose": "Ausklang"},
        {"position": 13, "preset_id": "single_full", "image_indices": [15], "purpose": "Ende"},
    ],
    "dramatic_arc": "intro -> buildup -> variation -> climax -> outro"
})


class TestPlan:
    @patch("app.photobook.plan.call_ollama")
    def test_plan_returns_valid_structure(self, mock_call):
        mock_call.return_value = MOCK_PLAN_CONTENT
        result = plan_photobook_layout(
            images=SAMPLE_IMAGES,
            gpx_stats={"total_distance_m": 8000},
            tour_summary="Eine schoene Wanderung im Schwarzwald.",
            model="test-model",
        )
        assert len(result.pages) > 0
        assert len(result.pages) == 14
        page0 = result.pages[0]
        assert page0.position == 0
        assert page0.preset_id == "cover_hero"
        assert isinstance(page0.image_indices, list)

    @patch("app.photobook.plan.call_ollama")
    def test_fallback_on_llm_error(self, mock_call):
        mock_call.return_value = None
        result = plan_photobook_layout(
            images=SAMPLE_IMAGES[:4],
            gpx_stats={},
            tour_summary=None,
            model="test-model",
        )
        assert len(result.pages) > 0
        assert len(result.pages) > 0
        assert result.pages[0].preset_id == "cover_hero"

    def test_fallback_plan_uses_presets(self):
        """Fallback-Planung muss preset_id (nicht template_category) produzieren."""
        result = plan_photobook_layout(
            images=SAMPLE_IMAGES[:6],
            gpx_stats={},
            tour_summary=None,
            model="test-model",
            base_url="http://invalid:99999",
        )
        for page in result.pages:
            assert page.preset_id, f"Seite {page.position} hat kein preset_id"
            assert page.preset_id != "", f"Seite {page.position} hat leeres preset_id"
