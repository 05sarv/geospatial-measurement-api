"""Pydantic response schemas."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class FileInfoResponse(BaseModel):
    id: str
    filename: str
    file_type: Optional[str] = None
    feature_count: int = 0
    crs: Optional[str] = None
    measurement_epsg: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class FeatureMeasurement(BaseModel):
    feature_index: int = Field(description="Zero-based feature ID/index within the file")
    geometry_type: str
    geometry: dict[str, Any] = Field(description="GeoJSON geometry (in source CRS)")
    crs: Optional[str] = None
    properties: dict[str, Any] = Field(default_factory=dict)
    area_sq_m: Optional[float] = Field(default=None, description="Polygon area in square metres")
    length_m: Optional[float] = Field(default=None, description="LineString length in metres")
    note: Optional[str] = None


class MeasurementsResponse(BaseModel):
    file_id: str
    crs: Optional[str] = None
    measurement_epsg: Optional[str] = None
    length_unit: str = "metre"
    area_unit: str = "square_metre"
    count: int = 0
    features: list[FeatureMeasurement] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    detail: str
