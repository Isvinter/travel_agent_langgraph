"""Tests fuer Fotobuch Graph-Nodes."""
import json
from unittest.mock import patch, MagicMock
from app.state import AppState, ImageData, OutputConfig, PageDescription
from app.nodes.select_photobook_images_node import select_photobook_images_node
from app.nodes.plan_photobook_node import plan_photobook_node
from app.nodes.generate_photobook_node import generate_photobook_node
from app.nodes.render_photobook_node import render_photobook_node

MOCK_SELECTION = {"message": {"content": json.dumps({"selected_indices": list(range(12))})}}
MOCK_PLAN = {"message": {"content": json.dumps({"pages": [{"position": 0, "page_type": "cover", "template_category": "hero", "image_indices": [0], "purpose": "Cover"}], "dramatic_arc": "test"})}}
MOCK_GENERATE = {"message": {"content": json.dumps([{"template_id": "hero_single", "page_type": "single", "slots": [{"slot_id": "main", "image_index": 0, "caption": "Test"}]}])}}


def make_state(n_images=20):
    return AppState(images=[ImageData(path=f"/tmp/img_{i}.jpg") for i in range(n_images)], model="test-model", output_config=OutputConfig())


class TestPhotobookNodes:
    @patch("app.photobook.image_selector.requests.post")
    def test_select_images_node(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_SELECTION
        mock_post.return_value = mock_resp
        state = make_state()
        result = select_photobook_images_node(state)
        assert len(result.photobook_images) == 12

    @patch("app.photobook.plan.requests.post")
    def test_plan_node(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_PLAN
        mock_post.return_value = mock_resp
        state = make_state()
        state.photobook_images = state.images[:12]
        result = plan_photobook_node(state)
        assert result.photobook_plan is not None
        assert len(result.photobook_plan["pages"]) == 1

    @patch("app.photobook.generate.requests.post")
    def test_generate_node(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_GENERATE
        mock_post.return_value = mock_resp
        state = make_state()
        state.photobook_images = state.images[:12]
        state.photobook_plan = json.loads(MOCK_PLAN["message"]["content"])
        result = generate_photobook_node(state)
        assert len(result.photobook_pages) == 1

    def test_render_node(self):
        state = make_state()
        state.photobook_pages = [PageDescription(template_id="hero_single", page_type="single", slots=[{"slot_id": "main", "image_index": 0, "caption": "Test"}])]
        state.photobook_images = state.images[:1]
        result = render_photobook_node(state)
        assert result.photobook_html is not None
        assert "layout-hero-single" in result.photobook_html
