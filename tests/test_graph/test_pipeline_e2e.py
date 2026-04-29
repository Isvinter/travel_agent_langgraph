"""End-to-end test for the full pipeline."""
import os
import shutil
from pathlib import Path

import pytest

from app.graph import build_graph
from app.state import AppState


@pytest.mark.e2e
class TestPipelineE2E:
    def test_full_pipeline_produces_blog(self, sample_gpx_path, fixtures_dir):
        import urllib.request
        try:
            req = urllib.request.Request("http://localhost:11434/api/tags")
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pytest.skip("Ollama not reachable at localhost:11434")

        if not (shutil.which("chromium") or shutil.which("google-chrome")):
            pytest.skip("Chrome/Chromium not installed")

        # Setup data/images/ and data/notes/ since nodes read from hardcoded paths
        import app.nodes.load_images as load_images_mod
        project_root = Path(load_images_mod.__file__).parent.parent.parent
        data_images_dir = project_root / "data" / "images"
        os.makedirs(data_images_dir, exist_ok=True)

        fixture_images = list(fixtures_dir.glob("images/photo_*.jpg"))
        for img in fixture_images:
            shutil.copy2(img, data_images_dir / img.name)

        try:
            state = AppState(
                gpx_file=sample_gpx_path,
                model="gemma4:26b-ctx128k",
            )

            graph = build_graph()
            result = graph.invoke(state)

            assert result["blog_post"] is not None
            blog = result["blog_post"]
            assert "markdown" in blog or "html" in blog or "error" in blog
        finally:
            if data_images_dir.exists():
                shutil.rmtree(data_images_dir)
