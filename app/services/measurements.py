"""Per-feature measurement logic (graceful on unsupported/empty geometries)."""
from typing import Any

AREA_TYPES = {"Polygon", "MultiPolygon"}
LENGTH_TYPES = {"LineString", "MultiLineString"}


def measure_geometry(geometry_type: str, projected_geom) -> tuple[float | None, float | None, str | None]:
    """Return (area_sq_m, length_m, note). Never raises on bad input."""
    try:
        if projected_geom is None or getattr(projected_geom, "is_empty", False):
            return None, None, "empty or missing geometry"
        if geometry_type in AREA_TYPES:
            return float(projected_geom.area), None, None
        if geometry_type in LENGTH_TYPES:
            return None, float(projected_geom.length), None
        if geometry_type in ("Point", "MultiPoint"):
            return None, None, None  # no measurement required
        return None, None, f"unsupported geometry type for measurement: {geometry_type}"
    except Exception as exc:  # graceful degradation, never crash the request
        return None, None, f"measurement failed: {exc}"


def serialise_properties(raw: dict[str, Any]) -> dict[str, Any]:
    """Make a GeoDataFrame row JSON-safe (NaN/NaT/Timestamp handling)."""
    import math

    import pandas as pd

    clean: dict[str, Any] = {}
    for key, value in raw.items():
        try:
            if value is None:
                clean[key] = None
            elif isinstance(value, float) and math.isnan(value):
                clean[key] = None
            elif pd.isna(value):
                clean[key] = None
            elif hasattr(value, "isoformat"):
                clean[key] = value.isoformat()
            else:
                clean[key] = value
        except Exception:
            clean[key] = str(value)
    return clean
