"""
utils/storage.py
================
Abstraction stockage local (extensible S3).
"""
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class StorageService:
    """Service de stockage pour les fichiers documents."""

    def __init__(self, base_dir: str = "data/epreuves"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_file_sync(self, file_bytes: bytes, relative_path: str, mimetype: str = "application/pdf") -> str:
        """Sauvegarde un fichier de manière synchrone et retourne le chemin final."""
        full_path = self.base_dir / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(file_bytes)
        return str(full_path)

    async def save_file(self, file_bytes: bytes, relative_path: str, mimetype: str = "application/pdf") -> str:
        """Sauvegarde un fichier et retourne le chemin final."""
        return self.save_file_sync(file_bytes, relative_path, mimetype)

    def file_exists(self, relative_path: str) -> bool:
        """Vérifie l'existence physique d'un fichier."""
        return (self.base_dir / relative_path).exists()

    def get_file_bytes(self, relative_path: str) -> Optional[bytes]:
        """Lit le contenu d'un fichier."""
        full_path = self.base_dir / relative_path
        if full_path.exists():
            return full_path.read_bytes()
        return None

    def delete_file(self, relative_path: str) -> bool:
        """Supprime un fichier physique."""
        full_path = self.base_dir / relative_path
        if full_path.exists():
            full_path.unlink()
            return True
        return False

    def stream_file(self, relative_path: str, filename: str):
        """Retourne un tuple pour le streaming de fichier (FastAPI FileResponse-like)."""
        full_path = self.base_dir / relative_path
        if not full_path.exists():
            return None
        return {
            "path": str(full_path),
            "filename": filename,
            "media_type": "application/pdf",
        }
