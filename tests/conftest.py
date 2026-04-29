"""Shared pytest fixtures for the travel agent test suite."""

import os
from pathlib import Path
from typing import List

import pytest

from app.state import AppState, ImageData
from app.services.gpx_analytics import GPXStats, analyze_track

FIXTURES_DIR = Path(__file__).parent / "fixtures"
GPX_PATH = str(FIXTURES_DIR / "gpx" / "tour.gpx")
IMAGES_DIR = str(FIXTURES_DIR / "images")
NOTES_DIR = str(FIXTURES_DIR / "notes")


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture(scope="session")
def sample_gpx_path() -> str:
    return GPX_PATH


@pytest.fixture(scope="session")
def sample_gpx_stats() -> GPXStats:
    stats, pauses = analyze_track(GPX_PATH)
    return stats


@pytest.fixture(scope="session")
def sample_gpx_pauses() -> List[dict]:
    stats, pauses = analyze_track(GPX_PATH)
    return pauses


@pytest.fixture
def sample_images() -> List[ImageData]:
    return [
        ImageData(
            path=str(FIXTURES_DIR / "images" / "photo_a.jpg"),
            timestamp=None,
            latitude=None,
            longitude=None,
        ),
        ImageData(
            path=str(FIXTURES_DIR / "images" / "photo_b.jpg"),
            timestamp=None,
            latitude=None,
            longitude=None,
        ),
        ImageData(
            path=str(FIXTURES_DIR / "images" / "photo_c.jpg"),
            timestamp=None,
            latitude=None,
            longitude=None,
        ),
    ]


@pytest.fixture
def sample_state(sample_gpx_path, sample_images) -> AppState:
    return AppState(
        gpx_file=sample_gpx_path,
        images=sample_images,
        model="gemma4:26b-ctx128k",
    )


@pytest.fixture
def notes_dir_path() -> str:
    return str(NOTES_DIR)


def pytest_configure(config):
    config.addinivalue_line("markers", "unit: Fast tests with no external dependencies")
    config.addinivalue_line("markers", "integration: Tests using real filesystem and fixtures, mocked network/browser")
    config.addinivalue_line("markers", "e2e: Full pipeline tests requiring Ollama and Chrome")
