"""
utils/file_validator.py
=======================
Validation sécurisée des fichiers uploadés.
"""
import logging
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.modules.epreuves.utils.constants import ALLOWED_MIMETYPES, MAX_FILE_SIZE_MB, ALLOWED_EXTENSIONS

logger = logging.getLogger(__name__)


class FileValidator:
    """Validation sécurisée des fichiers."""

    @staticmethod
    async def validate_upload(file: UploadFile) -> dict:
        """Valide un fichier uploadé."""
        ext = Path(file.filename).suffix.lower() if file.filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(400, f"INVALID_EXTENSION: {ext} not allowed")

        file_bytes = await file.read()
        size_bytes = len(file_bytes)

        if size_bytes > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise HTTPException(413, f"FILE_TOO_LARGE: max {MAX_FILE_SIZE_MB}MB")

        import uuid
        safe_filename = f"{uuid.uuid4().hex}{ext}"

        return {
            "valid": True,
            "mimetype": file.content_type or "application/pdf",
            "size_bytes": size_bytes,
            "safe_filename": safe_filename,
            "file_bytes": file_bytes,
            "original_filename": file.filename,
        }
