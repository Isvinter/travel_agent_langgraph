"""Minimal test to verify conftest.py fixtures work before building full test suite."""
import pytest
from pathlib import Path


def test_sample_gpx_path_returns_fixture(sample_gpx_path):
    path = Path(sample_gpx_path)
    assert path.exists(), f"Fixture GPX not found at {sample_gpx_path}"
    assert path.name == "tour.gpx"


def test_sample_images_returns_three_images(sample_images):
    assert len(sample_images) == 3
    assert sample_images[0].path.endswith("photo_a.jpg")
    assert sample_images[1].path.endswith("photo_b.jpg")
    assert sample_images[2].path.endswith("photo_c.jpg")


def test_sample_gpx_stats_has_points(sample_gpx_stats):
    from app.services.gpx_analytics import GPXStats
    assert isinstance(sample_gpx_stats, GPXStats)
    assert len(sample_gpx_stats.points) == 15
    assert sample_gpx_stats.total_distance_m > 0


def test_fixtures_directory_is_committed():
    """Sanity: fixtures dir must exist since they are committed."""
    fixtures = Path(__file__).parent / "fixtures"
    assert fixtures.is_dir()
    assert (fixtures / "gpx" / "tour.gpx").is_file()
    assert (fixtures / "images" / "photo_a.jpg").is_file()
    assert (fixtures / "notes" / "notes.txt").is_file()
