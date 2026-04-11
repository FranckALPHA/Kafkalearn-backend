"""
utils/security.py
=================
Helpers de sécurité : Argon2, JWT, fingerprint.
"""
import os
import hashlib
import secrets
from datetime import datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash
from jose import jwt, JWTError
from fastapi import HTTPException

from app.core.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

# ─── Argon2id ─────────────────────────────────────────────────────
argon2 = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Hash un mot de passe avec Argon2id."""
    return argon2.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Vérifie un mot de passe contre son hash Argon2."""
    try:
        argon2.verify(password_hash, password)
        return True
    except (VerifyMismatchError, InvalidHash):
        return False


def needs_rehash(password_hash: str) -> bool:
    """Vérifie si le hash doit être mis à jour."""
    return argon2.check_needs_rehash(password_hash)


# ─── JWT ──────────────────────────────────────────────────────────
def create_access_token(
    user_id: str, role: str, expires_delta: timedelta = None
) -> str:
    """Crée un JWT access token."""
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": user_id,
        "role": role,
        "type": "access",
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(
    user_id: str, fingerprint: str, expires_delta: timedelta = None
) -> str:
    """Crée un JWT refresh token avec fingerprint device."""
    expire = datetime.utcnow() + (
        expires_delta or timedelta(days=30)
    )
    payload = {
        "sub": user_id,
        "fingerprint": fingerprint,
        "type": "refresh",
        "exp": expire,
        "iat": datetime.utcnow(),
        "jti": secrets.token_urlsafe(16),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str, expected_type: str) -> dict:
    """Décode et valide un JWT."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != expected_type:
            raise JWTError("Invalid token type")
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail="INVALID_TOKEN")


# ─── Fingerprint ──────────────────────────────────────────────────
def generate_fingerprint(ip: str, user_agent: str) -> str:
    """
    Génère un hash unique pour identifier un device.
    Utilisé pour lier un refresh token à un appareil.
    """
    raw = f"{ip}:{user_agent}"
    return hashlib.sha256(raw.encode()).hexdigest()


# ─── OTP ──────────────────────────────────────────────────────────
def generate_otp(length: int = 6) -> str:
    """Génère un code OTP numérique aléatoire."""
    return "".join(secrets.choice("0123456789") for _ in range(length))
