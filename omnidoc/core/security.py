from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from omnidoc.core.config import get_settings


def hash_password(password: str) -> str:
    if len(password.encode()) > 72:  # bcrypt's limit
        raise ValueError("Password too long")
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode()[:72], password_hash.encode())


def _secret() -> str:
    secret = get_settings().jwt_secret
    if not secret:  # an empty secret would let anyone forge tokens
        raise RuntimeError("JWT_SECRET is not set in .env")
    return secret


def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": now,
               "exp": now + timedelta(minutes=get_settings().jwt_expire_minutes)}
    return jwt.encode(payload, _secret(), algorithm="HS256")


def decode_access_token(token: str) -> int | None:
    try:
        return int(jwt.decode(token, _secret(), algorithms=["HS256"])["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
