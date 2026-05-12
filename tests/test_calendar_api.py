import pytest


class TestCalendarAPI:
    @pytest.mark.unit
    def test_generate_requires_images(self, test_client):
        resp = test_client.post("/api/calendar/generate", json={
            "preset": "mixed",
            "year": 2026,
            "image_files": [],
        })
        assert resp.status_code == 422

    @pytest.mark.unit
    def test_generate_rejects_invalid_model(self, test_client):
        resp = test_client.post("/api/calendar/generate", json={
            "preset": "mixed",
            "year": 2026,
            "model": "nonexistent",
            "image_files": ["/tmp/test.jpg"],
        })
        assert resp.status_code == 422

    @pytest.mark.unit
    def test_list_calendars(self, test_client):
        resp = test_client.get("/api/calendars")
        assert resp.status_code == 200
        assert "calendars" in resp.json()

    @pytest.mark.unit
    def test_get_nonexistent_calendar(self, test_client):
        resp = test_client.get("/api/calendars/99999")
        assert resp.status_code == 404
