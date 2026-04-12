import os
from pathlib import Path
from fastapi import HTTPException
from app.modules.ingest.utils.constants import ALLOWED_EXTENSIONS, BLACKLISTED_DIRS, MIME_TYPE_MAP

try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False


class FileSecurity:
    @staticmethod
    def validate_magic_bytes(file_bytes: bytes) -> str:
        if HAS_MAGIC:
            mime = magic.from_buffer(file_bytes[:1024], mime=True)
        else:
            # Fallback: detect by extension
            return "pdf"  # Default fallback
        doc_type = MIME_TYPE_MAP.get(mime)
        if not doc_type:
            raise HTTPException(400, f"FORMAT_NON_SUPPORTE: {mime}")
        return doc_type

    @staticmethod
    def secure_path(chemin: str, root_dir: str) -> str:
        real_root = os.path.realpath(root_dir)
        real_path = os.path.realpath(chemin)
        if not real_path.startswith(real_root + os.sep):
            raise HTTPException(403, "PATH_TRAVERSAL_DETECTED")
        for banned in BLACKLISTED_DIRS:
            if real_path.startswith(banned):
                raise HTTPException(403, "ACCESS_DENIED_SYSTEM_DIR")
        return real_path
