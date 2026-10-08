"""Unit tests for CRS selection."""
import geopandas as gpd
from shapely.geometry import Point

from app.services.crs import choose_projected_crs, normalize_crs, utm_epsg_for_lonlat


def test_normalize_missing_crs_defaults_to_wgs84():
    assert normalize_crs(None).to_string() == "EPSG:4326"


def test_utm_zone_selection():
    # Bangalore, India (lon ~77.6E) -> zone 43N -> EPSG:32643
    assert utm_epsg_for_lonlat(77.6, 13.0) == "EPSG:32643"
    # Sydney (151E, 33S) -> zone 56S -> EPSG:32756
    assert utm_epsg_for_lonlat(151.2, -33.8) == "EPSG:32756"


def test_geographic_data_gets_utm():
    gdf = gpd.GeoDataFrame({"name": ["a"]}, geometry=[Point(77.6, 13.0)], crs="EPSG:4326")
    assert choose_projected_crs(gdf) == "EPSG:32643"


def test_projected_metre_crs_is_kept():
    gdf = gpd.GeoDataFrame({"name": ["a"]}, geometry=[Point(500000, 1500000)], crs="EPSG:32643")
    assert choose_projected_crs(gdf) == "EPSG:32643"
