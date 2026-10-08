"""Application configuration."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GEO_", env_file=".env", extra="ignore")

    app_name: str = "Geospatial File Measurement API"
    database_url: str = f"sqlite:///{(BASE_DIR / 'geospatial.db').as_posix()}"
    storage_dir: str = str(BASE_DIR / "storage" / "uploads")
    max_upload_mb: int = 50
    # Allowed extensions (lowercase)
    allowed_extensions: tuple = (".zip", ".kml")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
