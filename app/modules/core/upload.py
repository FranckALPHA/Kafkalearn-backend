"""
modules/core/upload.py
======================
Validation fichiers, Sanitization, Magic Bytes.
"""
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.modules.core.config import settings

ALLOWED_EXTENSIONS = {".pdf", ".docx"}


async def validate_upload(file: UploadFile) -> dict:
    """Valide un fichier uploadé."""
    ext = Path(file.filename).suffix.lower() if file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"INVALID_EXTENSION: {ext} not allowed")

    file_bytes = await file.read()
    size_bytes = len(file_bytes)

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if size_bytes > max_bytes:
        raise HTTPException(413, f"FILE_TOO_LARGE: max {settings.MAX_UPLOAD_SIZE_MB}MB")

    safe_filename = f"{uuid.uuid4().hex}{ext}"

    return {
        "mimetype": file.content_type or "application/pdf",
        "size_bytes": size_bytes,
        "safe_filename": safe_filename,
        "file_bytes": file_bytes,
        "original_filename": file.filename,
    }
