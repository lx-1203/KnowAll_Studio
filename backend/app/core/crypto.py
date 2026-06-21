"""API Key secure storage using AES encryption"""
import os
import base64
import hashlib
from cryptography.fernet import Fernet
from app.config import BASE_DIR

_KEY_FILE = BASE_DIR / "data" / ".secret_key"


def _get_or_create_key() -> bytes:
    """Get or create the encryption key."""
    if _KEY_FILE.exists():
        return _KEY_FILE.read_bytes()
    key = Fernet.generate_key()
    _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    _KEY_FILE.write_bytes(key)
    # Restrict permissions (Unix only)
    try:
        os.chmod(_KEY_FILE, 0o600)
    except Exception:
        pass
    return key


def encrypt_api_key(plaintext: str) -> str:
    """Encrypt an API key. Returns base64-encoded ciphertext."""
    fernet = Fernet(_get_or_create_key())
    encrypted = fernet.encrypt(plaintext.encode("utf-8"))
    return base64.b64encode(encrypted).decode("ascii")


def decrypt_api_key(ciphertext: str) -> str:
    """Decrypt an API key. Returns the original plaintext."""
    fernet = Fernet(_get_or_create_key())
    encrypted = base64.b64decode(ciphertext.encode("ascii"))
    return fernet.decrypt(encrypted).decode("utf-8")
