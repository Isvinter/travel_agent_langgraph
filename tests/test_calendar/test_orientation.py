"""Layer 3: Orientierungserkennung."""
import pytest
from PIL import Image
from app.calendar.orientation import get_orientation, get_orientations


@pytest.fixture
def landscape_img(tmp_path):
    p = tmp_path / "landscape.jpg"
    img = Image.new("RGB", (800, 600), color=(100, 150, 200))
    img.save(p, "JPEG")
    return str(p)


@pytest.fixture
def portrait_img(tmp_path):
    p = tmp_path / "portrait.jpg"
    img = Image.new("RGB", (600, 800), color=(200, 100, 150))
    img.save(p, "JPEG")
    return str(p)


@pytest.fixture
def square_img(tmp_path):
    p = tmp_path / "square.jpg"
    img = Image.new("RGB", (500, 500), color=(150, 200, 100))
    img.save(p, "JPEG")
    return str(p)


class TestGetOrientation:
    @pytest.mark.unit
    def test_landscape_image(self, landscape_img):
        assert get_orientation(landscape_img) == "landscape"

    @pytest.mark.unit
    def test_portrait_image(self, portrait_img):
        assert get_orientation(portrait_img) == "portrait"

    @pytest.mark.unit
    def test_square_image(self, square_img):
        assert get_orientation(square_img) == "square"

    @pytest.mark.unit
    def test_nonexistent_path_returns_landscape(self):
        assert get_orientation("/tmp/nicht_existent_12345.jpg") == "landscape"

    @pytest.mark.unit
    def test_corrupt_file_returns_landscape(self, tmp_path):
        p = tmp_path / "corrupt.jpg"
        p.write_text("not an image")
        assert get_orientation(str(p)) == "landscape"


class TestGetOrientations:
    @pytest.mark.unit
    def test_multiple_orientations(self, landscape_img, portrait_img, square_img):
        paths = [landscape_img, portrait_img, square_img]
        result = get_orientations(paths)
        assert result == ["landscape", "portrait", "square"]

    @pytest.mark.unit
    def test_empty_list(self):
        assert get_orientations([]) == []
