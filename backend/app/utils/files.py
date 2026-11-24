from __future__ import annotations

import io
import uuid
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from app.core.config import get_settings
from app.core.errors import AppError

PHOTO_DIR = "photos"
DOCUMENT_DIR = "documents"
_DOC_SIGNATURES = {
    b"%PDF-": ("application/pdf", ".pdf"),
    b"\x89PNG\r\n\x1a\n": ("image/png", ".png"),
    b"\xff\xd8\xff": ("image/jpeg", ".jpg"),
}


def upload_root() -> Path:
    root = get_settings().upload_dir
    (root / PHOTO_DIR).mkdir(parents=True, exist_ok=True)
    (root / DOCUMENT_DIR).mkdir(parents=True, exist_ok=True)
    return root


def _read_limited(upload: UploadFile, limit: int) -> bytes:
    data = upload.file.read(limit + 1)
    if len(data) > limit:
        raise AppError(f"File is too large. Maximum size is {limit // (1024 * 1024)} MB.", status_code=413, code="file_too_large")
    if not data:
        raise AppError("The uploaded file is empty.", code="file_empty")
    return data


def save_photo(upload: UploadFile) -> str:
    data = _read_limited(upload, get_settings().max_photo_bytes)
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()
        with Image.open(io.BytesIO(data)) as img:
            if img.format not in ("JPEG", "PNG", "WEBP"):
                raise AppError("Photo must be a JPEG, PNG or WEBP image.", code="invalid_file_type")
            img = img.convert("RGB")
            img.thumbnail((600, 600))
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=88)
    except (UnidentifiedImageError, OSError):
        raise AppError("Photo must be a valid JPEG, PNG or WEBP image.", code="invalid_file_type") from None
    rel = f"{PHOTO_DIR}/{uuid.uuid4().hex}.jpg"
    (upload_root() / rel).write_bytes(out.getvalue())
    return rel


def save_document(upload: UploadFile) -> tuple[str, str, int]:
    data = _read_limited(upload, get_settings().max_document_bytes)
    for signature, (content_type, ext) in _DOC_SIGNATURES.items():
        if data.startswith(signature):
            rel = f"{DOCUMENT_DIR}/{uuid.uuid4().hex}{ext}"
            (upload_root() / rel).write_bytes(data)
            return rel, content_type, len(data)
    raise AppError("Supporting document must be a PDF, JPEG or PNG file.", code="invalid_file_type")


def resolve(rel_path: str | None) -> Path | None:
    if not rel_path:
        return None
    root = upload_root().resolve()
    path = (root / rel_path).resolve()
    if root not in path.parents or not path.is_file():
        return None
    return path


def _version(photo_path: str | None) -> str:
    import hashlib

    return hashlib.sha1((photo_path or "none").encode()).hexdigest()[:10]


def student_photo_url(student) -> str:
    """The ?v= part changes whenever a new photo is stored, so browsers never show a stale cached image."""
    return f"/api/files/students/{student.id}/photo?v={_version(student.photo_path)}"


def teacher_photo_url(teacher) -> str:
    return f"/api/files/teachers/{teacher.id}/photo?v={_version(teacher.photo_path)}"


def safe_filename(name: str | None) -> str:
    name = Path(name or "document").name
    return "".join(c for c in name if c.isalnum() or c in "._- ")[:120] or "document"
