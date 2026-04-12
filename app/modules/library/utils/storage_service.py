import uuid
import logging
from pathlib import Path
from typing import Optional, BinaryIO

logger = logging.getLogger(__name__)


class StorageService:
    def __init__(self, base_path: str = "data/assets"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save_file(self, file_content: bytes, filename: str, content_type: str, folder: str = "assets") -> str:
        ext = Path(filename).suffix.lower()
        if ext not in [".pdf", ".png", ".jpg", ".jpeg"]:
            ext = ".bin"
        unique_name = f"{uuid.uuid4().hex}{ext}"
        relative_path = f"{folder}/{unique_name}"
        file_path = self.base_path / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(file_content)
        return f"/storage/{relative_path}"

    def get_file(self, relative_path: str) -> Optional[BinaryIO]:
        file_path = self.base_path / relative_path
        if file_path.exists():
            return open(file_path, "rb")
        return None

    def file_exists(self, relative_path: str) -> bool:
        return (self.base_path / relative_path).exists()

    def delete_file(self, relative_path: str) -> bool:
        file_path = self.base_path / relative_path
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def get_file_size(self, relative_path: str) -> Optional[int]:
        file_path = self.base_path / relative_path
        if file_path.exists():
            return file_path.stat().st_size
        return None
