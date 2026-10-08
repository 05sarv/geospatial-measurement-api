"""Unit tests for measurement logic."""
from shapely.geometry import LineString, MultiPolygon, Point, Polygon

from app.services.measurements import measure_geometry


def test_polygon_area():
    poly = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    area, length, note = measure_geometry("Polygon", poly)
    assert area == 10000.0
    assert length is None
    assert note is None


def test_multipolygon_area():
    mp = MultiPolygon(
        [
            Polygon([(0, 0), (10, 0), (10, 10), (0, 10)]),
            Polygon([(20, 20), (30, 20), (30, 30), (20, 30)]),
        ]
    )
    area, _, _ = measure_geometry("MultiPolygon", mp)
    assert area == 200.0


def test_linestring_length():
    line = LineString([(0, 0), (0, 1000)])
    area, length, _ = measure_geometry("LineString", line)
    assert area is None
    assert length == 1000.0


def test_point_has_no_measurement():
    area, length, note = measure_geometry("Point", Point(0, 0))
    assert area is None and length is None and note is None


def test_unsupported_type_is_graceful():
    area, length, note = measure_geometry("GeometryCollection", Point(0, 0))
    assert area is None and length is None
    assert note is not None and "unsupported" in note.lower()


def test_empty_geometry_is_graceful():
    area, length, note = measure_geometry("Polygon", Polygon())
    assert area is None and note is not None
