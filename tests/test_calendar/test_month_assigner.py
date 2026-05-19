import pytest
from app.calendar.month_assigner import (
    _build_assignment_prompt,
    _parse_assignment_response,
    _fallback_assignment,
    _parse_exif_date,
)
from app.state import ImageData


class TestParseExifDate:
    @pytest.mark.unit
    def test_parse_exif_date_string(self):
        dt = _parse_exif_date("2024:07:15 10:30:00")
        assert dt is not None
        assert dt.month == 7

    @pytest.mark.unit
    def test_invalid_date_returns_none(self):
        assert _parse_exif_date("invalid") is None
        assert _parse_exif_date(None) is None

    @pytest.mark.unit
    def test_missing_timestamp_returns_none(self):
        img = ImageData(path="/tmp/test.jpg", timestamp=None)
        assert _parse_exif_date(img.timestamp) is None


class TestBuildAssignmentPrompt:
    @pytest.mark.unit
    def test_contains_criteria(self):
        prompt = _build_assignment_prompt(
            selected_photos=[("test_1.jpg", "2024-06-15"), ("test_2.jpg", "2024-01-10")],
            year=2026,
            preset_criteria="landschaftliche Vielfalt",
            custom_instructions="Nur Sonnenaufgänge",
        )
        assert "landschaftliche Vielfalt" in prompt
        assert "Nur Sonnenaufgänge" in prompt
        assert "Januar" in prompt
        assert "Dezember" in prompt
        assert "test_1.jpg" in prompt

    @pytest.mark.unit
    def test_no_custom_instructions(self):
        prompt = _build_assignment_prompt(
            selected_photos=[("test_1.jpg", "2024-06-15")],
            year=2026,
            preset_criteria="landschaftlich",
            custom_instructions=None,
        )
        assert "Zusätzliche Anweisungen" not in prompt


class TestFallbackAssignment:
    @pytest.mark.unit
    def test_fills_all_slots(self):
        photos = [
            ImageData(path=f"/tmp/test_{i}.jpg", timestamp=f"2024:0{i % 12 + 1}:15 10:00:00")
            for i in range(40)
        ]
        pages = _fallback_assignment(photos, 2026)
        assert len(pages) == 13
        assert pages[0].month == 0

    @pytest.mark.unit
    def test_fallback_with_fewer_photos_reuses(self):
        photos = [ImageData(path="/tmp/test_0.jpg", timestamp="2024:06:15 10:00:00")]
        pages = _fallback_assignment(photos, 2026)
        assert len(pages) == 13
        for page in pages:
            for slot in page.slots:
                assert slot.image_index == 0


class TestBuildAssignmentPromptWithOrientations:
    @pytest.mark.unit
    def test_prompt_includes_orientation_tags(self):
        prompt = _build_assignment_prompt(
            selected_photos=[("test_1.jpg", "2024-06-15"), ("test_2.jpg", "2024-01-10")],
            year=2026,
            preset_criteria="landschaftliche Vielfalt",
            orientations=["landscape", "portrait"],
        )
        assert "(LANDSCAPE)" in prompt
        assert "(PORTRAIT)" in prompt

    @pytest.mark.unit
    def test_prompt_includes_orientation_instructions(self):
        prompt = _build_assignment_prompt(
            selected_photos=[("test_1.jpg", "2024-06-15")],
            year=2026,
            preset_criteria="test",
            orientations=["landscape"],
        )
        assert "Slot-Orientierungen beachten" in prompt
        assert "Querformat bevorzugen" in prompt or "wide" in prompt.lower()

    @pytest.mark.unit
    def test_prompt_without_orientations_no_tags(self):
        prompt = _build_assignment_prompt(
            selected_photos=[("test_1.jpg", "2024-06-15")],
            year=2026,
            preset_criteria="test",
            orientations=None,
        )
        assert "(LANDSCAPE)" not in prompt
        assert "(PORTRAIT)" not in prompt


class TestFallbackAssignmentWithOrientations:
    @pytest.mark.unit
    def test_landscapes_assigned_to_wide_slots(self):
        """Querformat-Fotos landen in Breitslots."""
        from PIL import Image
        import tempfile
        photos = []
        tmpdir = tempfile.mkdtemp()
        for i in range(30):
            p = f"{tmpdir}/landscape_{i}.jpg"
            img = Image.new("RGB", (800, 600))
            img.save(p, "JPEG")
            photos.append(ImageData(path=p, timestamp=f"2024:0{(i % 12) + 1}:15 10:00:00"))
        for i in range(5):
            p = f"{tmpdir}/portrait_{i}.jpg"
            img = Image.new("RGB", (600, 800))
            img.save(p, "JPEG")
            photos.append(ImageData(path=p, timestamp="2024:06:15 10:00:00"))

        orientations = []
        for img in photos:
            from PIL import Image as PILImg
            i = PILImg.open(img.path)
            orientations.append("landscape" if i.size[0] > i.size[1] else "portrait")

        pages = _fallback_assignment(photos, 2026, orientations=orientations)
        assert len(pages) == 13

        june_page = [p for p in pages if p.month_name == "Juni"][0]
        june_orientations = []
        for slot in june_page.slots:
            june_orientations.append(orientations[slot.image_index])
        assert "landscape" in june_orientations

    @pytest.mark.unit
    def test_fallback_without_orientations_still_works(self):
        """Ohne Orientierungen: bestehendes Verhalten bleibt erhalten."""
        photos = [
            ImageData(path=f"/tmp/test_{i}.jpg", timestamp=f"2024:0{(i % 12) + 1}:15 10:00:00")
            for i in range(40)
        ]
        pages = _fallback_assignment(photos, 2026)
        assert len(pages) == 13
        for page in pages:
            assert len(page.slots) > 0


class TestParseAssignmentResponse:
    @pytest.mark.unit
    def test_valid_response(self):
        response = """# Januar
  img: 5, img2: 3
# Februar
  left: 0, right: 2"""
        result = _parse_assignment_response(response)
        assert "Januar" in result
        assert len(result["Januar"]) == 1

    @pytest.mark.unit
    def test_empty_response_returns_empty(self):
        assert _parse_assignment_response("") == {}
        assert _parse_assignment_response(None) == {}
