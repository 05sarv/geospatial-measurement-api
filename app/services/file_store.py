"""Disk storage helpers for uploaded files."""
import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.config import get_settings


def new_file_id() -> str:
    return uuid.uuid4().hex[:12]


def storage_dir_for(file_id: str) -> Path:
    base = Path(get_settings().storage_dir)
    target = base / file_id
    target.mkdir(parents=True, exist_ok=True)
    return target


async def save_upload(upload: UploadFile, dest: Path, max_bytes: int) -> int:
    """Stream upload to disk enforcing a size limit. Returns bytes written."""
    size = 0
    with dest.open("wb") as fh:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                fh.close()
                dest.unlink(missing_ok=True)
                raise ValueError(f"File exceeds {max_bytes // (1024 * 1024)} MB limit.")
            fh.write(chunk)
    await upload.close()
    return size


def copy_to_storage(src: Path, file_id: str, filename: str) -> Path:
    dest_dir = storage_dir_for(file_id)
    dest = dest_dir / filename
    # Avoid collisions / path traversal: keep only the basename.
    dest = dest_dir / Path(filename).name
    if src.resolve() != dest.resolve():
        shutil.copyfile(src, dest)
    return dest
