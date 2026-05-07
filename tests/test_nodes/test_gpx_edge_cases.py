"""Edge-Case-Tests für GPX-Analyse: malformed, empty, invalid."""
import os
import tempfile

import pytest

from app.services.gpx_analytics import parse_gpx, analyze_track
from app.nodes.process_gpx import process_gpx_node
from app.state import AppState


class TestParseGpxEdgeCases:
    def test_empty_gpx_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".gpx", delete=False) as f:
            f.write("")
            f.flush()
            path = f.name
        try:
            with pytest.raises(Exception):
                parse_gpx(path)
        finally:
            os.unlink(path)

    def test_malformed_gpx_not_xml(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".gpx", delete=False) as f:
            f.write("Dies ist keine gültige GPX-Datei, sondern nur Text.")
            f.flush()
            path = f.name
        try:
            with pytest.raises(Exception):
                parse_gpx(path)
        finally:
            os.unlink(path)

    def test_gpx_without_track_segments(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test">
  <metadata><name>Leere Tour</name></metadata>
</gpx>"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".gpx", delete=False) as f:
            f.write(xml)
            f.flush()
            path = f.name
        try:
            stats, pauses = analyze_track(path)
            assert stats.total_distance_m == 0
            assert len(stats.points) == 0
            assert len(pauses) == 0
        finally:
            os.unlink(path)

    def test_gpx_with_zero_points(self):
        """GPX mit <trkseg> aber ohne <trkpt>."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test">
  <trk>
    <trkseg>
    </trkseg>
  </trk>
</gpx>"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".gpx", delete=False) as f:
            f.write(xml)
            f.flush()
            path = f.name
        try:
            stats, pauses = analyze_track(path)
            assert stats.total_distance_m == 0
            assert len(pauses) == 0
        finally:
            os.unlink(path)

    def test_gpx_with_single_point(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test">
  <trk>
    <trkseg>
      <trkpt lat="47.0" lon="8.0"><ele>500</ele><time>2024-07-15T10:00:00Z</time></trkpt>
    </trkseg>
  </trk>
</gpx>"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".gpx", delete=False) as f:
            f.write(xml)
            f.flush()
            path = f.name
        try:
            stats, pauses = analyze_track(path)
            assert stats.total_distance_m == 0
            assert len(stats.points) == 1
        finally:
            os.unlink(path)

    def test_gpx_missing_elevation(self):
        """GPX ohne elevation und time → distance=0 weil gpxpy mit elevation=None fehlschlägt."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test">
  <trk>
    <trkseg>
      <trkpt lat="47.0" lon="8.0"><time>2024-07-15T10:00:00Z</time></trkpt>
      <trkpt lat="47.1" lon="8.1"><time>2024-07-15T11:00:00Z</time></trkpt>
    </trkseg>
  </trk>
</gpx>"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".gpx", delete=False) as f:
            f.write(xml)
            f.flush()
            path = f.name
        try:
            stats, pauses = analyze_track(path)
            assert len(stats.points) == 2
            assert stats.elevation_gain_m == 0
        finally:
            os.unlink(path)

    def test_process_gpx_node_with_empty_gpx(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test">
  <trk><trkseg></trkseg></trk>
</gpx>"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".gpx", delete=False) as f:
            f.write(xml)
            f.flush()
            path = f.name
        try:
            state = AppState(gpx_file=path)
            result = process_gpx_node(state)
            assert result.gpx_stats is not None
            assert result.gpx_stats.total_distance_m == 0
        finally:
            os.unlink(path)
