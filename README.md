# Geospatial File Measurement API

Backend service (FastAPI) that accepts a geospatial file (zipped Shapefile or KML),
extracts its features, and returns measurements — area for polygons, length for
lines — computed in a proper projected CRS (never in degrees).

## 1. Setup — run locally

**Requirements:** Python 3.10+ (tested on 3.10/3.11), pip.

**Easiest (Windows):** double-click **`start.bat`** — it creates a virtual
environment, installs dependencies, starts the server, and opens the API docs
in your browser. The manual steps below do the same thing by hand.

```bash
# 1. Clone (after you push to GitHub) and enter the project
git clone <your-repo-url>
cd internship_project

# 2. Create + activate a virtual environment
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) generate sample files for manual testing
python scripts/make_samples.py   # creates sample_data/sample.kml + sample_shapefile.zip

# 5. Run the server
uvicorn app.main:app --reload
```

Open the interactive docs: **http://127.0.0.1:8000/docs** (Swagger UI).

**Run tests:**

```bash
python -m pytest tests -v
```

**Run with Docker:**

```bash
docker build -t geo-api .
docker run -p 8000:8000 -v ./storage:/code/storage geo-api
```

**Configuration (optional `.env` file, see `.env.example`):**

| Variable | Default | Meaning |
|---|---|---|
| `GEO_DATABASE_URL` | `sqlite:///./geospatial.db` | SQLAlchemy DB URL |
| `GEO_STORAGE_DIR` | `./storage/uploads` | Where uploads are stored |
| `GEO_MAX_UPLOAD_MB` | `50` | Upload size limit |

### Push to GitHub (when ready)

```bash
git init
git add .
git commit -m "Geospatial File Measurement API (FastAPI)"
git branch -M main
git remote add origin <your-repo-url>
git push -u origin main
```

> Note: `geospatial.db` and `storage/uploads/*` are git-ignored, so uploads and the
> local database are never committed.

## 2. API

Base URL: `http://127.0.0.1:8000`

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/files/` | Upload `.zip` (Shapefile) or `.kml`, process it, return file info |
| `GET` | `/api/files/` | List all uploaded files (newest first) — bonus endpoint |
| `GET` | `/api/files/{id}/` | File information (feature count, CRS, status) |
| `GET` | `/api/files/{id}/measurements/` | Per-feature measurements |
| `GET` | `/`, `/health` | Health checks |

### Upload — `POST /api/files/`

Accepts `multipart/form-data` with a single `file` field (`.zip` or `.kml`).

```bash
# KML
curl -X POST http://127.0.0.1:8000/api/files/ \
  -F "file=@sample_data/sample.kml"

# Zipped Shapefile
curl -X POST http://127.0.0.1:8000/api/files/ \
  -F "file=@sample_data/sample_shapefile.zip"
```

**Response `201 Created`:**

```json
{
  "id": "3ced72651e27",
  "filename": "sample.kml",
  "file_type": "kml",
  "feature_count": 3,
  "crs": "EPSG:4326",
  "measurement_epsg": "EPSG:32643",
  "status": "COMPLETED",
  "error_message": null,
  "created_at": "2026-10-08T12:27:53.455113"
}
```

Errors: `400` unsupported extension, `413` file over size limit,
`422`-style `FAILED` status persisted on the record when parsing fails
(e.g. empty zip, no `.shp` inside).

### File information — `GET /api/files/{id}/`

```bash
curl http://127.0.0.1:8000/api/files/3ced72651e27/
```

```json
{
  "id": "3ced72651e27",
  "filename": "survey.kml",
  "feature_count": 120,
  "crs": "EPSG:4326",
  "status": "COMPLETED"
}
```

(`404` if the id is unknown.)

### Measurements — `GET /api/files/{id}/measurements/`

```bash
curl http://127.0.0.1:8000/api/files/3ced72651e27/measurements/
```

```json
{
  "file_id": "3ced72651e27",
  "crs": "EPSG:4326",
  "measurement_epsg": "EPSG:32643",
  "length_unit": "metre",
  "area_unit": "square_metre",
  "count": 3,
  "features": [
    {
      "feature_index": 0,
      "geometry_type": "Polygon",
      "geometry": {"type": "Polygon", "coordinates": [[[77.59, 12.97], [77.60, 12.97], [77.60, 12.98], [77.59, 12.98], [77.59, 12.97]]]},
      "crs": "EPSG:4326",
      "properties": {"name": "square"},
      "area_sq_m": 1201683.91,
      "length_m": null,
      "note": null
    },
    {
      "feature_index": 1,
      "geometry_type": "LineString",
      "geometry": {"type": "LineString", "coordinates": [[77.59, 12.97], [77.61, 12.99]]},
      "crs": "EPSG:4326",
      "properties": {"name": "road"},
      "area_sq_m": null,
      "length_m": 3108.45,
      "note": null
    }
  ]
}
```

Measurement rules: `Polygon`/`MultiPolygon` → `area_sq_m`, `LineString`/
`MultiLineString` → `length_m`, `Point`/`MultiPoint` → no measurement (`null`),
anything else → `null` plus an explanatory `note` (never a crash).

Status codes: `404` unknown id, `409` still processing, `422` processing failed
(the `detail` carries the reason).

## 3. Architecture

```
app/
  main.py              # FastAPI factory, lifespan, CORS, router wiring
  config.py            # pydantic-settings (env: GEO_*)
  database.py          # SQLAlchemy engine/session (SQLite by default)
  models.py            # FileRecord + FeatureRecord tables
  schemas.py           # Pydantic response models
  api/files.py         # POST /api/files/, GET info, GET measurements
  services/
    file_store.py      # id generation, safe upload streaming, size limit
    geo_processor.py   # detect/read .zip(Shapefile) + .kml via GeoPandas
    crs.py             # CRS normalisation + projected-CRS selection
    measurements.py    # per-geometry area/length, graceful degradation
tests/                 # test_api.py (end-to-end) + unit tests
scripts/make_samples.py# generates sample_data for manual testing
storage/uploads/       # uploaded files on disk (git-ignored)
```

### File-processing flow

1. `POST /api/files/` validates the extension (`.zip` → Shapefile, `.kml` → KML)
   and streams the upload to `storage/uploads/{id}/{filename}` with a size cap.
2. A `FileRecord` row is created with status `PROCESSING`.
3. `read_geodataframe()` parses the file:
   - **zip:** extracted to a temp dir with Zip-Slip protection, the `.shp` is
     located (most complete layer wins if several), read with GeoPandas.
   - **KML:** read with GeoPandas (`pyogrio` engine, GDAL KML driver fallback).
   - Missing CRS is assumed to be `EPSG:4326` (standard for KML/Shapefiles
     without `.prj`).
4. Features are persisted as `FeatureRecord` rows (GeoJSON geometry + JSON
   properties + measurements); the file row flips to `COMPLETED` (or `FAILED`
   with `error_message` — the API never crashes on bad input).

### Measurement-calculation flow

1. Choose one projected CRS for the whole file (`choose_projected_crs`).
2. Reproject a copy of the GeoDataFrame there; geometry at index `i` in the
   projected frame corresponds to feature `i`.
3. Per feature, `measure_geometry()` applies the type dispatch
   (area / length / none / unsupported-note) with empty-geometry guards and a
   broad try/except so one bad geometry can't fail the file.

### CRS handling

Never measure in degrees. The rule (`app/services/crs.py`):

1. Source CRS already projected **in metres** → measure in it directly.
2. Otherwise (geographic like `EPSG:4326`, missing, or non-metre) → reproject to
   a locally accurate CRS derived from the data centroid in WGS84:
   - `|lat| > 84°` (polar, outside UTM validity) → `EPSG:6933` (global equal-area),
   - else the containing **UTM zone** (`326xx` north / `327xx` south).
3. Fallbacks: centroid failure → zone of lon 0; reprojection failure →
   `EPSG:3857`. The chosen CRS is stored as `measurement_epsg` and returned by
   the API for transparency/reproducibility.

## 4. Design decisions

| Decision | Choice | Alternatives considered |
|---|---|---|
| **FastAPI over Django+DRF** | Less boilerplate for a file-measurement service; auto OpenAPI docs; `UploadFile` + Pydantic v2 fit the spec's schemas directly | Django+DRF: better if the project needed admin/auth/ORM migrations, but overkill here |
| **GeoPandas + pyogrio + Shapely + pyProj** | One well-tested stack reads both Shapefile and KML and handles reprojection; wheels install cleanly on Windows/Linux | Raw `fiona`/`pyshp` + manual KML XML parsing: more code, more edge cases |
| **SQLite + SQLAlchemy** | Zero-ops persistence, file-backed, trivially reviewable; easy swap to Postgres via `GEO_DATABASE_URL` | In-memory dict: loses data on restart; Postgres/PostGIS: most powerful but requires infra the task doesn't need |
| **Centroid-based UTM** | Standard, explainable, metre-accurate for typical survey-scale files; recorded in response | Per-feature UTM (accurate but inconsistent units), global equal-area for everything (simple but distorted locally), Web-Mercator everywhere (easy but inaccurate) |
| **Synchronous processing on upload** | Simple and deterministic for the expected file sizes; status field (`PROCESSING/COMPLETED/FAILED`) already models async later | Celery/RQ + BackgroundTasks: right move if files grow large; endpoint + status design supports it without changes |
| **Graceful degradation** | Unsupported/empty geometries yield `null` + `note`; bad files yield `FAILED` + `error_message` instead of 500s | Strict fail-fast: simpler but violates the "handle gracefully" requirement |
| **Geometry returned in source CRS** | Preserves fidelity of the original data; measurements annotated with `measurement_epsg` | Returning reprojected geometry: mixes concerns and surprises clients |

### Known limitations / next steps

- Processing is synchronous — files near the 50 MB cap block the request;
  move `_process_file` to a background worker for production scale.
- One projected CRS per file: files spanning many UTM zones lose some accuracy;
  per-feature CRS or equal-area global CRS would fix that.
- No auth/rate-limiting/pagination on measurements — add before public deployment.
