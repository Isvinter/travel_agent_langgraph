"""Tests fuer LLM Pass 1: Preset-Auswahl."""
import json
from unittest.mock import patch, MagicMock
from app.state import ImageData
from app.photobook.plan import plan_photobook_layout

SAMPLE_IMAGES = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(16)]

MOCK_PLAN_RESPONSE = {
    "message": {
        "content": json.dumps({
            "pages": [
                {"position": 0, "preset_id": "cover_hero", "image_indices": [3], "purpose": "Cover"},
                {"position": 1, "preset_id": "double_equal", "image_indices": [7, 12], "purpose": "Aufstieg"},
                {"position": 2, "preset_id": "quad_grid", "image_indices": [0, 2, 5, 8], "purpose": "Sammlung"},
            ],
            "dramatic_arc": "intro -> buildup -> variation"
        })
    }
}


class TestPlan:
    @patch("app.photobook.plan.requests.post")
    def test_plan_returns_valid_structure(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_PLAN_RESPONSE
        mock_post.return_value = mock_resp
        result = plan_photobook_layout(
            images=SAMPLE_IMAGES,
            gpx_stats={"total_distance_m": 8000},
            notes="Test",
            weather=None,
            poi_list=[],
            model="test-model",
        )
        assert "pages" in result
        assert len(result["pages"]) == 3
        assert "dramatic_arc" in result
        page0 = result["pages"][0]
        assert page0["position"] == 0
        assert page0["preset_id"] == "cover_hero"
        assert isinstance(page0["image_indices"], list)

    @patch("app.photobook.plan.requests.post")
    def test_fallback_on_llm_error(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_post.return_value = mock_resp
        result = plan_photobook_layout(
            images=SAMPLE_IMAGES[:4],
            gpx_stats={},
            notes=None,
            weather=None,
            poi_list=[],
            model="test-model",
        )
        assert "pages" in result
        assert len(result["pages"]) > 0
        assert result["pages"][0]["preset_id"] == "cover_hero"

    def test_fallback_plan_uses_presets(self):
        """Fallback-Planung muss preset_id (nicht template_category) produzieren."""
        result = plan_photobook_layout(
            images=SAMPLE_IMAGES[:6],
            gpx_stats={},
            notes=None,
            weather=None,
            poi_list=[],
            model="test-model",
            base_url="http://invalid:99999",
        )
        for page in result["pages"]:
            assert "preset_id" in page, f"Seite {page.get('position')} hat kein preset_id"
            assert page["preset_id"] != "", f"Seite {page.get('position')} hat leeres preset_id"
