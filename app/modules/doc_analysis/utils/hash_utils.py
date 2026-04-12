import hashlib

class HashUtils:
    @staticmethod
    def hash_document_text(text: str) -> str:
        if not text:
            return ""
        normalized = text.strip().lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def hashes_match(hash1: str, hash2: str) -> bool:
        if not hash1 or not hash2:
            return False
        return hashlib.compare_digest(hash1, hash2)
