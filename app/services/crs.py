"""CRS handling: never measure directly in degrees.

Strategy (documented in README):
1. If the source CRS is already projected with metre units -> measure in it.
2. Else (geographic like EPSG:4326, or missing/unknown) -> reproject to a
   locally-accurate projected CRS derived from the data centroid:
   - polar regions (|lat| > 84): EPSG:6933 (NSIDC EASE-Grid 2.0 global)
   - otherwise: the UTM zone containing the centroid
     (EPSG:326xx northern hemisphere, EPSG:327xx southern hemisphere).
"""
import geopandas as gpd
from pyproj import CRS

POLAR_THRESHOLD = 84
FALLBACK_GEOGRAPHIC = "EPSG:4326"
POLAR_CRS = "EPSG:6933"


def normalize_crs(crs) -> CRS:
    """Return a pyproj CRS, defaulting to EPSG:4326 when missing/invalid."""
    if crs is None:
        return CRS.from_string(FALLBACK_GEOGRAPHIC)
    try:
        return CRS.from_user_input(crs)
    except Exception:
        return CRS.from_string(FALLBACK_GEOGRAPHIC)


def crs_string(crs) -> str:
    try:
        return normalize_crs(crs).to_string()
    except Exception:
        return FALLBACK_GEOGRAPHIC


def is_projected_metre(crs: CRS) -> bool:
    try:
        return bool(crs.is_projected) and "metre" in (crs.axis_info[0].unit_name or "").lower()
    except Exception:
        return False


def utm_epsg_for_lonlat(lon: float, lat: float) -> str:
    zone = int((lon + 180) // 6) + 1
    zone = min(max(zone, 1), 60)
    if lat >= 0:
        return f"EPSG:{32600 + zone}"
    return f"EPSG:{32700 + zone}"


def choose_projected_crs(gdf: gpd.GeoDataFrame) -> str:
    """Pick the EPSG string measurements should be computed in."""
    source = normalize_crs(gdf.crs)
    if is_projected_metre(source):
        return source.to_string()

    # Work out centroid in lon/lat.
    try:
        wgs84 = gdf.to_crs(FALLBACK_GEOGRAPHIC)
        centroid = wgs84.geometry.union_all().centroid
        lon, lat = float(centroid.x), float(centroid.y)
    except Exception:
        return utm_epsg_for_lonlat(0.0, 0.0)

    if abs(lat) > POLAR_THRESHOLD:
        return POLAR_CRS
    return utm_epsg_for_lonlat(lon, lat)


def to_projected(gdf: gpd.GeoDataFrame, target_epsg: str) -> gpd.GeoDataFrame:
    if normalize_crs(gdf.crs).to_string() == CRS.from_string(target_epsg).to_string():
        return gdf
    return gdf.to_crs(target_epsg)
