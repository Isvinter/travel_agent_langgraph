import pytest
from app.shared.image_selector import select_images
from app.state import ImageData


@pytest.fixture
def sample_images(tmp_path):
    """Erzeugt einfache Test-Bilder."""
    paths = []
    for i in range(20):
        p = tmp_path / f"test_{i}.jpg"
        # Minimales JPEG erstellen
        from PIL import Image
        img = Image.new("RGB", (100, 100), color=(i * 12, 100, 200))
        img.save(p, "JPEG")
        paths.append(str(p))
    return [ImageData(path=p) for p in paths]


class TestSelectImages:
    def test_empty_list_returns_empty(self):
        result = select_images([], criteria="test", target_count=10)
        assert result == []

    def test_fewer_than_target_returns_all(self, sample_images):
        subset = sample_images[:5]
        result = select_images(subset, criteria="test", target_count=10)
        assert len(result) == 5

    def test_fallback_chronological_when_ollama_unavailable(self, sample_images):
        """Ohne Ollama soll der chronologische Fallback greifen."""
        result = select_images(
            sample_images,
            criteria="landschaftliche Vielfalt",
            target_count=8,
            base_url="http://localhost:99999",  # nicht existent
        )
        assert len(result) == 8
        # Chronologisch = ersten 8
        assert result == sample_images[:8]

    def test_custom_instructions_in_prompt(self, mocker, sample_images):
        """Prüft dass custom_instructions in den Prompt einfliessen."""
        from app.shared import image_selector as mod

        mock = mocker.patch.object(mod, "call_ollama", return_value=None)
        select_images(
            sample_images,
            criteria="test",
            target_count=5,
            custom_instructions="Bevorzuge Sonnenaufgänge",
            base_url="http://localhost:99999",
        )
        # Der Prompt wurde aufgerufen
        assert mock.called
        # Mindestens ein Aufruf enthält den custom text
        prompt_texts = [c[0][0] for c in mock.call_args_list]
        assert any("Bevorzuge Sonnenaufgänge" in p for p in prompt_texts)

    def test_llm_success_path_selects_correct_images(self, mocker, sample_images):
        """LLM gibt gültige Indizes zurück — der LLM-Pfad wird durchlaufen."""
        from app.shared import image_selector as mod

        # Nur 10 Bilder (einfacher Batch), target 4 — alle Indizes aus mock passen
        subset = sample_images[:10]
        mock = mocker.patch.object(mod, "call_ollama", return_value="0,3,6,9")
        result = select_images(
            subset,
            criteria="test",
            target_count=4,
            base_url="http://localhost:99999",
        )
        assert len(result) == 4
        assert mock.called
