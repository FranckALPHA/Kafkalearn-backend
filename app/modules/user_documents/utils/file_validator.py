import secrets
from pathlib import Path
from fastapi import HTTPException, UploadFile
from app.modules.user_documents.utils.constants import ALLOWED_MIME_TYPES, MAX_FILE_SIZE_MB

class FileValidator:
    MAGIC_BYTES_MAP = {
        "application/pdf": b"%PDF",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": b"PK\x03\x04",
        "application/msword": b"\xD0\xCF\x11\xE0",
        "image/jpeg": b"\xFF\xD8\xFF",
        "image/png": b"\x89PNG",
        "image/gif": b"GIF8",
    }

    ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".jpg", ".jpeg", ".png", ".gif"}

    @staticmethod
    async def validate_upload(file: UploadFile) -> dict:
        file_bytes = await file.read()
        size_bytes = len(file_bytes)
        if size_bytes > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise HTTPException(400, f"FICHIER_TROP_GRAND: max {MAX_FILE_SIZE_MB}MB")
        if size_bytes == 0:
            raise HTTPException(400, "FICHIER_VIDE")

        try:
            import magic
            detected_mime = magic.from_buffer(file_bytes[:1024], mime=True)
        except Exception:
            detected_mime = file.content_type or "application/octet-stream"

        if detected_mime not in ALLOWED_MIME_TYPES:
            raise HTTPException(400, f"EXTENSION_INVALIDE: {detected_mime}")

        ext = Path(file.filename).suffix.lower() if file.filename else ""
        if ext not in FileValidator.ALLOWED_EXTENSIONS:
            mime_to_ext = {
                "application/pdf": ".pdf",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
                "application/msword": ".doc",
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "image/gif": ".gif",
            }
            ext = mime_to_ext.get(detected_mime, ".pdf")

        safe_filename = f"{secrets.token_hex(16)}_{(file.filename or 'doc')[:8]}{ext}"
        return {
            "mimetype": detected_mime,
            "size_bytes": size_bytes,
            "safe_filename": safe_filename,
            "file_bytes": file_bytes,
            "original_filename": file.filename,
        }
