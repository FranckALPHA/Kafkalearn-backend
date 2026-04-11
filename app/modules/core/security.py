"""
modules/core/security.py
========================
JWT, Argon2, Fingerprinting.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.modules.core.config import settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")


def create_refresh_token(user_id: str, fingerprint: str) -> tuple:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    jti = secrets.token_urlsafe(16)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "fingerprint": fingerprint,
        "exp": expire,
        "jti": jti,
    }
    return jwt.encode(payload, settings.REFRESH_SECRET_KEY, algorithm="HS256"), jti


def decode_token(token: str, secret: str = None, expected_type: str = "access") -> dict:
    secret = secret or settings.SECRET_KEY
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        if payload.get("type") != expected_type:
            raise JWTError("Invalid token type")
        return payload
    except JWTError:
        raise


def generate_fingerprint(ip_address: str, user_agent: str) -> str:
    """Génère un hash unique pour identifier un device sans stocker l'IP complète."""
    if ":" in ip_address:
        ip_prefix = ip_address[:ip_address.rfind(":")]
    else:
        parts = ip_address.split(".")
        ip_prefix = ".".join(parts[:3]) + ".0" if len(parts) == 4 else ip_address

    raw = f"{ip_prefix}:{user_agent}"
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_otp(length: int = 6) -> str:
    return str(secrets.randbelow(10**length)).zfill(length)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
