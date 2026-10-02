import base64
import json
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken  # noqa: F401  (InvalidToken re-exported)
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from omnidoc.core.config import get_settings


def _master_key() -> bytes:
    raw = get_settings().vault_key
    if not raw:
        raise RuntimeError("VAULT_KEY is not set in .env")
    try:
        key = base64.urlsafe_b64decode(raw)
    except Exception:
        key = b""
    if len(key) != 32:
        raise RuntimeError(
            "VAULT_KEY is invalid; generate it with Fernet.generate_key()")
    return key


@lru_cache(maxsize=1024)
def _fernet_for(user_id: int) -> Fernet:
    """A different key for every user, derived from the master key."""
    derived = HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                   info=f"omnidoc-user-{int(user_id)}".encode()).derive(_master_key())
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_bytes(user_id: int, data: bytes) -> bytes:
    return _fernet_for(user_id).encrypt(data)


def decrypt_bytes(user_id: int, token: bytes) -> bytes:
    return _fernet_for(user_id).decrypt(token)


def encrypt_text(user_id: int, text: str) -> str:
    return encrypt_bytes(user_id, text.encode()).decode()


def decrypt_text(user_id: int, token: str) -> str:
    return decrypt_bytes(user_id, token.encode()).decode()


def encrypt_json(user_id: int, obj) -> str:
    return encrypt_text(user_id, json.dumps(obj))


def decrypt_json(user_id: int, token: str):
    return json.loads(decrypt_text(user_id, token))
