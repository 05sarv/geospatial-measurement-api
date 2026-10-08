"""API integration tests using in-memory SQLite + generated KML/Shapefile samples."""
import io
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import LineString, Point, Polygon
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database as db_module
from app.database import Base, get_db
from app.main import create_app

# --- isolated test DB ---
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app = create_app()
app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def _make_kml_bytes() -> bytes:
    gdf = gpd.GeoDataFrame(
        {"name": ["square", "road", "spot"]},
        geometry=[
            Polygon([(77.59, 12.97), (77.60, 12.97), (77.60, 12.98), (77.59, 12.98)]),
            LineString([(77.59, 12.97), (77.61, 12.99)]),
            Point(77.60, 12.975),
        ],
        crs="EPSG:4326",
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "sample.kml"
        gdf.to_file(path, driver="KML")
        return path.read_bytes()


def _make_shapefile_zip_bytes() -> bytes:
    gdf = gpd.GeoDataFrame(
        {"name": ["plot"]},
        geometry=[Polygon([(77.59, 12.97), (77.61, 12.97), (77.61, 12.99), (77.59, 12.99)])],
        crs="EPSG:4326",
    )
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        gdf.to_file(tmp_path / "sample.shp")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in tmp_path.glob("sample.*"):
                zf.write(f, arcname=f.name)
        return buf.getvalue()


def test_upload_kml_and_measurements():
    resp = client.post("/api/files/", files={"file": ("sample.kml", _make_kml_bytes(), "application/xml")})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "COMPLETED"
    assert body["feature_count"] == 3
    assert body["crs"] == "EPSG:4326"

    info = client.get(f"/api/files/{body['id']}/")
    assert info.status_code == 200
    assert info.json()["feature_count"] == 3

    meas = client.get(f"/api/files/{body['id']}/measurements/")
    assert meas.status_code == 200
    payload = meas.json()
    assert payload["count"] == 3
    by_type = {f["geometry_type"]: f for f in payload["features"]}
    assert by_type["Polygon"]["area_sq_m"] > 0
    assert by_type["LineString"]["length_m"] > 0
    assert by_type["Point"]["area_sq_m"] is None
    # sanity: every feature exposes required fields
    for f in payload["features"]:
        assert {"feature_index", "geometry_type", "geometry", "crs", "properties"} <= set(f.keys())


def test_upload_shapefile_zip():
    resp = client.post(
        "/api/files/",
        files={"file": ("sample.zip", _make_shapefile_zip_bytes(), "application/zip")},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "COMPLETED"
    assert resp.json()["feature_count"] == 1


def test_reject_unsupported_extension():
    resp = client.post("/api/files/", files={"file": ("evil.txt", b"hello", "text/plain")})
    assert resp.status_code == 400


def test_404_for_unknown_id():
    assert client.get("/api/files/doesnotexist/").status_code == 404
    assert client.get("/api/files/doesnotexist/measurements/").status_code == 404


def test_crs_is_projected_for_measurement():
    resp = client.post("/api/files/", files={"file": ("sample.kml", _make_kml_bytes(), "application/xml")})
    payload = client.get(f"/api/files/{resp.json()['id']}/measurements/").json()
    assert payload["measurement_epsg"] != "EPSG:4326"
