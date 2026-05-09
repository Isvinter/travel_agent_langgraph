"""Integrationstest: Vollstaendiger Fotobuch-Graph-Durchlauf mit Mock-LLM."""
import json
from unittest.mock import patch, MagicMock
from app.state import AppState, ImageData, OutputConfig, EnrichmentContext
from app.graph import build_graph

MOCK_SELECTION_CONTENT = "0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11"
MOCK_PLAN_CONTENT = json.dumps({
    "pages": [
        {"position": 0, "preset_id": "cover_hero", "image_indices": [0], "purpose": "Cover"},
        {"position": 1, "preset_id": "double_stacked", "image_indices": [1, 2], "purpose": "Split"},
        {"position": 2, "preset_id": "quad_grid", "image_indices": [3, 4, 5, 6], "purpose": "Grid"},
    ],
    "dramatic_arc": "test"
})
MOCK_GENERATE_CONTENT = json.dumps([
    {"preset_id": "cover_hero", "slots": [{"slot_id": "main", "image_index": 0}]},
    {"preset_id": "double_stacked", "slots": [
        {"slot_id": "top", "image_index": 1}, {"slot_id": "bottom", "image_index": 2},
    ]},
    {"preset_id": "quad_grid", "slots": [
        {"slot_id": "tl", "image_index": 3}, {"slot_id": "tr", "image_index": 4},
        {"slot_id": "bl", "image_index": 5}, {"slot_id": "br", "image_index": 6},
    ]},
])

# Mock-Rueckgabe fuer den Blog-Bildselektor
def _mock_blog_select(images, target_count=8, model=None, base_url=None):
    return images[:target_count]

# Mock-Rueckgabe fuer den Content-Reviewer
def _mock_review_enrichment(weather=None, poi_list=None, selected_images=None,
                            gpx_stats=None, notes=None, model=None):
    return EnrichmentContext(coherence_score=5, filtered_images=selected_images or [])


def make_state(n_images=20):
    return AppState(
        images=[ImageData(path=f"/tmp/img_{i}.jpg", latitude=47.0 + i * 0.001, longitude=8.0 + i * 0.001) for i in range(n_images)],
        output_config=OutputConfig(mode="photobook"),
        model="test-model",
    )


def test_full_photobook_pipeline():
    """Durchlauf des gesamten Fotobuch-Pfads mit gemocktem LLM."""

    with patch("app.nodes.extract_metadata.enrich_images_with_metadata", return_value=None), \
         patch("app.nodes.select_images_node.select_images_for_blog", side_effect=_mock_blog_select), \
         patch("app.nodes.review_content_node.review_enrichment", side_effect=_mock_review_enrichment), \
         patch("app.photobook.image_selector.encode_image_base64", return_value="bW9jay1iYXNlNjQ="):

        with patch("app.photobook.image_selector.call_ollama") as mock_sel:
            mock_sel.return_value = MOCK_SELECTION_CONTENT

            with patch("app.photobook.plan.call_ollama") as mock_plan:
                mock_plan.return_value = MOCK_PLAN_CONTENT

                with patch("app.photobook.generate.call_ollama") as mock_gen:
                    mock_gen.return_value = MOCK_GENERATE_CONTENT

                    state = make_state()
                    graph = build_graph()
                    result = graph.invoke(state)

                    assert result["photobook_pdf_path"] is not None
                    assert len(result["photobook_pages"]) == 3
                    assert result["photobook_html"] is not None
                    assert "preset-cover-hero" in result["photobook_html"]
                    assert result["photobook_plan"] is not None


class TestPresetPipeline:
    """Integrationstest: Plan → Generate → Validate → Render mit Presets."""

    def test_full_pipeline_with_presets(self):
        """Die komplette Pipeline mit Presets muss ein gueltiges HTML liefern."""
        from app.photobook.plan import plan_photobook_layout
        from app.photobook.generate import generate_photobook_pages
        from app.photobook.validator import validate_all_pages
        from app.photobook.renderer import render_photobook

        images = [ImageData(path=f"/tmp/img_{i}.jpg") for i in range(8)]

        mock_plan_content = json.dumps({
            "pages": [
                {"position": 0, "preset_id": "cover_hero", "image_indices": [0]},
                {"position": 1, "preset_id": "double_stacked", "image_indices": [1, 2]},
                {"position": 2, "preset_id": "triple_stacked", "image_indices": [3, 4, 5]},
                {"position": 3, "preset_id": "single_text_left", "image_indices": [6]},
                {"position": 4, "preset_id": "single_text_below", "image_indices": [7]},
            ],
            "dramatic_arc": "cover → buildup → highlight → closing"
        })

        mock_gen_content = json.dumps([
            {"preset_id": "cover_hero", "slots": [
                {"slot_id": "main", "image_index": 0},
                {"slot_id": "title", "text": "Bergtour 2026"},
            ]},
            {"preset_id": "double_stacked", "slots": [
                {"slot_id": "top", "image_index": 1},
                {"slot_id": "bottom", "image_index": 2},
            ]},
            {"preset_id": "triple_stacked", "slots": [
                {"slot_id": "top", "image_index": 3},
                {"slot_id": "middle", "image_index": 4},
                {"slot_id": "bottom", "image_index": 5},
            ]},
            {"preset_id": "single_text_left", "slots": [
                {"slot_id": "main", "image_index": 6},
                {"slot_id": "text", "text": "Rast am See"},
            ]},
            {"preset_id": "single_text_below", "slots": [
                {"slot_id": "main", "image_index": 7},
                {"slot_id": "caption", "text": "Gipfelblick"},
            ]},
        ])

        with patch("app.photobook.plan.call_ollama") as mock_plan_post:
            mock_plan_post.return_value = mock_plan_content

            plan = plan_photobook_layout(images, None, None, None, [], model="test")
            assert len(plan.pages) == 5
            assert plan.pages[0].preset_id == "cover_hero"

            with patch("app.photobook.generate.call_ollama") as mock_gen_post:
                mock_gen_post.return_value = mock_gen_content

                pages = generate_photobook_pages(plan, images, None, None, model="test")
                assert len(pages) == 5

                validated, warnings = validate_all_pages(pages)
                assert len(validated) == 5
                assert validated[0].template_id == "cover_hero"

                html = render_photobook(validated, images)
                assert "preset-cover-hero" in html
                assert "Bergtour 2026" in html
                assert "Gipfelblick" in html
                assert "<html" in html
                assert "</html>" in html
