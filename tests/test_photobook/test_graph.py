"""Tests fuer Fotobuch Graph-Nodes."""
import json
from unittest.mock import patch, MagicMock
from app.state import AppState, ImageData, OutputConfig, PageDescription, PhotobookPlan, PagePlan
from app.nodes.select_photobook_images_node import select_photobook_images_node
from app.nodes.plan_photobook_node import plan_photobook_node
from app.nodes.generate_photobook_node import generate_photobook_node
from app.nodes.render_photobook_node import render_photobook_node

MOCK_SELECTION_INDICES = "0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15"
MOCK_PLAN = json.dumps({
    "pages": [
        {"position": 0, "preset_id": "cover_hero", "image_indices": [0], "purpose": "Cover"},
        {"position": 1, "preset_id": "single_full", "image_indices": [1], "purpose": "Start"},
        {"position": 2, "preset_id": "single_full", "image_indices": [2], "purpose": "Weg"},
        {"position": 3, "preset_id": "single_full", "image_indices": [3], "purpose": "Weg"},
        {"position": 4, "preset_id": "single_full", "image_indices": [4], "purpose": "Weg"},
        {"position": 5, "preset_id": "single_full", "image_indices": [5], "purpose": "Weg"},
        {"position": 6, "preset_id": "double_stacked", "image_indices": [6, 7], "purpose": "Aufbau"},
        {"position": 7, "preset_id": "single_full", "image_indices": [8], "purpose": "Hoehepunkt"},
        {"position": 8, "preset_id": "single_full", "image_indices": [9], "purpose": "Hoehepunkt"},
        {"position": 9, "preset_id": "single_full", "image_indices": [10], "purpose": "Ausklang"},
        {"position": 10, "preset_id": "single_full", "image_indices": [11], "purpose": "Ende"},
    ],
    "dramatic_arc": "intro -> buildup -> climax -> outro"
})
MOCK_GENERATE = json.dumps([{"preset_id": "cover_hero", "slots": [{"slot_id": "main", "image_index": 0}]}])


def make_state(n_images=20):
    return AppState(images=[ImageData(path=f"/tmp/img_{i}.jpg") for i in range(n_images)], model="test-model", output_config=OutputConfig())


class TestPhotobookNodes:
    @patch("app.photobook.image_selector.encode_image_base64")
    @patch("app.photobook.image_selector.call_ollama")
    def test_select_images_node(self, mock_call, mock_encode):
        mock_encode.return_value = "bW9jay1iYXNlNjQ="  # dummy base64
        mock_call.return_value = MOCK_SELECTION_INDICES
        state = make_state(n_images=30)
        result = select_photobook_images_node(state)
        assert len(result.photobook_images) == 20  # photo_count default = 20

    @patch("app.photobook.plan.call_ollama")
    def test_plan_node(self, mock_call):
        mock_call.return_value = MOCK_PLAN
        state = make_state()
        state.photobook_images = state.images[:12]
        result = plan_photobook_node(state)
        assert result.photobook_plan is not None
        assert len(result.photobook_plan.pages) == 11  # 12 Bilder: cover + 10 weitere Seiten

    @patch("app.photobook.generate.call_ollama")
    def test_generate_node(self, mock_call):
        mock_call.return_value = MOCK_GENERATE
        state = make_state()
        state.photobook_images = state.images[:12]
        plan_dict = json.loads(MOCK_PLAN)
        state.photobook_plan = PhotobookPlan(pages=[PagePlan(**p) for p in plan_dict["pages"]])
        result = generate_photobook_node(state)
        assert len(result.photobook_pages) == 1

    def test_render_node(self):
        state = make_state()
        state.photobook_pages = [PageDescription(template_id="cover_hero", page_type="single", slots=[{"slot_id": "main", "image_index": 0}])]
        state.photobook_images = state.images[:1]
        result = render_photobook_node(state)
        assert result.photobook_html is not None
        assert "preset-cover-hero" in result.photobook_html
