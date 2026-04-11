"""
utils/hash_utils.py
===================
Calcul de hash SHA-256 pour déduplication de documents.
"""
import hashlib


def sha256_bytes(data: bytes) -> str:
    """Calcule le SHA-256 d'un contenu binaire."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(file_bytes: bytes) -> str:
    """Alias pour compatibilité."""
    return sha256_bytes(file_bytes)
