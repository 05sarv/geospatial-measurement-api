"""Generate small sample files for manual testing (KML + zipped Shapefile)."""
from pathlib import Path
import zipfile

import geopandas as gpd
from shapely.geometry import LineString, Point, Polygon

OUT = Path(__file__).resolve().parent.parent / "sample_data"
OUT.mkdir(exist_ok=True)


def main() -> None:
    gdf = gpd.GeoDataFrame(
        {"name": ["square", "road", "spot"], "note": ["park", "main road", "landmark"]},
        geometry=[
            Polygon([(77.59, 12.97), (77.60, 12.97), (77.60, 12.98), (77.59, 12.98)]),
            LineString([(77.59, 12.97), (77.61, 12.99)]),
            Point(77.60, 12.975),
        ],
        crs="EPSG:4326",
    )
    kml_path = OUT / "sample.kml"
    gdf.to_file(kml_path, driver="KML")
    print(f"wrote {kml_path}")

    shp_dir = OUT / "shapefile"
    shp_dir.mkdir(exist_ok=True)
    # NOTE: ESRI Shapefiles require a single geometry type per layer,
    # so the shapefile sample keeps polygons only (KML above mixes types).
    poly_only = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    poly_only.to_file(shp_dir / "sample.shp")
    zip_path = OUT / "sample_shapefile.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in shp_dir.glob("sample.*"):
            zf.write(f, arcname=f.name)
    print(f"wrote {zip_path}")


if __name__ == "__main__":
    main()
