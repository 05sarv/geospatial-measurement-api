"""Read Shapefile (.zip) and KML files into a GeoDataFrame."""
import json
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd

from app.services.crs import FALLBACK_GEOGRAPHIC


class UnsupportedFileError(ValueError):
    pass


def detect_file_type(filename: str) -> str:
    name = filename.lower()
    if name.endswith(".zip"):
        return "shapefile"
    if name.endswith(".kml"):
        return "kml"
    raise UnsupportedFileError("Only .zip (Shapefile) and .kml files are supported.")


def _safe_extract(zip_path: Path, dest: Path) -> None:
    """Extract guarding against Zip Slip."""
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            target = (dest / member).resolve()
            if not str(target).startswith(str(dest.resolve())):
                raise UnsupportedFileError("Unsafe paths inside zip archive.")
        zf.extractall(dest)


def _find_shapefile(extracted: Path) -> Path:
    candidates = list(extracted.rglob("*.shp"))
    if not candidates:
        raise UnsupportedFileError("No .shp found inside the zip archive.")
    # If several, prefer the one with the most sibling files (most complete).
    candidates.sort(key=lambda p: len(list(p.parent.glob(p.stem + ".*"))), reverse=True)
    return candidates[0]


def read_geodataframe(saved_path: Path, file_type: str) -> gpd.GeoDataFrame:
    """Read geospatial file -> GeoDataFrame. Raises UnsupportedFileError on failure."""
    try:
        if file_type == "shapefile":
            with tempfile.TemporaryDirectory() as tmp:
                _safe_extract(saved_path, Path(tmp))
                shp = _find_shapefile(Path(tmp))
                gdf = gpd.read_file(shp)
        elif file_type == "kml":
            # pyogrio engine handles KML reliably when GDAL KML driver is present.
            try:
                gdf = gpd.read_file(saved_path, engine="pyogrio")
            except Exception:
                gdf = gpd.read_file(saved_path)
        else:
            raise UnsupportedFileError(f"Unknown file type: {file_type}")
    except UnsupportedFileError:
        raise
    except Exception as exc:
        raise UnsupportedFileError(f"Could not parse geospatial file: {exc}") from exc

    if gdf is None or gdf.empty:
        raise UnsupportedFileError("File contains no features.")
    if "geometry" not in gdf.columns:
        raise UnsupportedFileError("File contains no geometry column.")

    # KML / files without CRS are lon/lat on WGS84.
    if gdf.crs is None:
        gdf = gdf.set_crs(FALLBACK_GEOGRAPHIC)
    return gdf


def geometry_geojson(geom) -> dict:
    if geom is None or getattr(geom, "is_empty", False):
        return {"type": "GeometryCollection", "coordinates": None, "geometries": []}
    try:
        return json.loads(gpd.GeoSeries([geom]).to_json())["features"][0]["geometry"]
    except Exception:
        return {"type": "Unknown", "wkt": str(geom)}
