"""File upload / info / measurements endpoints."""
import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import FeatureRecord, FileRecord
from app.schemas import FeatureMeasurement, FileInfoResponse, MeasurementsResponse
from app.services.crs import choose_projected_crs, crs_string, normalize_crs, to_projected
from app.services.file_store import copy_to_storage, new_file_id, save_upload, storage_dir_for
from app.services.geo_processor import (
    UnsupportedFileError,
    detect_file_type,
    geometry_geojson,
    read_geodataframe,
)
from app.services.measurements import measure_geometry, serialise_properties

router = APIRouter(prefix="/api/files", tags=["files"])


def _to_file_info(record: FileRecord) -> FileInfoResponse:
    return FileInfoResponse(
        id=record.id,
        filename=record.filename,
        file_type=record.file_type,
        feature_count=record.feature_count,
        crs=record.crs,
        measurement_epsg=record.measurement_epsg,
        status=record.status,
        error_message=record.error_message,
        created_at=record.created_at,
    )


def _process_file(db: Session, record: FileRecord, saved_path: Path) -> None:
    """Parse features, compute measurements, persist rows. Never leaks exceptions."""
    try:
        gdf = read_geodataframe(saved_path, record.file_type)
        source_crs = crs_string(gdf.crs)
        measurement_epsg = choose_projected_crs(gdf)
        try:
            projected = to_projected(gdf, measurement_epsg)
        except Exception:
            measurement_epsg = "EPSG:3857"  # last-resort global metric CRS
            projected = to_projected(gdf, measurement_epsg)

        rows: list[FeatureRecord] = []
        for idx, (_, row) in enumerate(gdf.iterrows()):
            geom = row.geometry
            geom_type = getattr(geom, "geom_type", "Unknown") if geom is not None else "Unknown"
            area, length, note = measure_geometry(geom_type, projected.geometry.iloc[idx])
            props = {k: v for k, v in row.items() if k != "geometry"}
            rows.append(
                FeatureRecord(
                    file_id=record.id,
                    feature_index=idx,
                    geometry_type=str(geom_type),
                    geometry_json=json.dumps(geometry_geojson(geom)),
                    properties_json=json.dumps(serialise_properties(props)),
                    area_sq_m=area,
                    length_m=length,
                    note=note,
                )
            )
        db.query(FeatureRecord).filter(FeatureRecord.file_id == record.id).delete()
        db.add_all(rows)
        record.feature_count = len(rows)
        record.crs = source_crs
        record.measurement_epsg = measurement_epsg
        record.status = "COMPLETED"
        record.error_message = None
        db.commit()
    except UnsupportedFileError as exc:
        db.rollback()
        record.status = "FAILED"
        record.error_message = str(exc)
        db.commit()
    except Exception as exc:  # graceful failure, keeps API alive
        db.rollback()
        record.status = "FAILED"
        record.error_message = f"Processing failed: {exc}"
        db.commit()


@router.post("/", response_model=FileInfoResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    settings = get_settings()
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")
    try:
        file_type = detect_file_type(file.filename)
    except UnsupportedFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    file_id = new_file_id()
    dest_dir = storage_dir_for(file_id)
    safe_name = Path(file.filename).name
    dest = dest_dir / safe_name
    try:
        await save_upload(file, dest, settings.max_upload_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc))

    record = FileRecord(
        id=file_id,
        filename=safe_name,
        file_type=file_type,
        status="PROCESSING",
        storage_path=str(dest),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    copy_to_storage(dest, file_id, safe_name)  # normalises location
    _process_file(db, record, dest)
    db.refresh(record)
    return _to_file_info(record)


@router.get("/", response_model=list[FileInfoResponse])
def list_files(db: Session = Depends(get_db)):
    records = db.query(FileRecord).order_by(FileRecord.created_at.desc()).all()
    return [_to_file_info(r) for r in records]


@router.get("/{file_id}/", response_model=FileInfoResponse)
def get_file(file_id: str, db: Session = Depends(get_db)):
    record = db.query(FileRecord).filter(FileRecord.id == file_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="File not found.")
    return _to_file_info(record)


@router.get("/{file_id}/measurements/", response_model=MeasurementsResponse)
def get_measurements(file_id: str, db: Session = Depends(get_db)):
    record = db.query(FileRecord).filter(FileRecord.id == file_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="File not found.")
    if record.status == "FAILED":
        raise HTTPException(status_code=422, detail=record.error_message or "File processing failed.")
    if record.status != "COMPLETED":
        raise HTTPException(status_code=409, detail=f"File is {record.status}, try again shortly.")

    rows = (
        db.query(FeatureRecord)
        .filter(FeatureRecord.file_id == file_id)
        .order_by(FeatureRecord.feature_index)
        .all()
    )
    features = [
        FeatureMeasurement(
            feature_index=r.feature_index,
            geometry_type=r.geometry_type,
            geometry=json.loads(r.geometry_json),
            crs=record.crs,
            properties=json.loads(r.properties_json or "{}"),
            area_sq_m=r.area_sq_m,
            length_m=r.length_m,
            note=r.note,
        )
        for r in rows
    ]
    _ = normalize_crs  # (kept import meaningful for future extensions)
    return MeasurementsResponse(
        file_id=file_id,
        crs=record.crs,
        measurement_epsg=record.measurement_epsg,
        count=len(features),
        features=features,
    )
