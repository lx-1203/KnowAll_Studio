"""API Key secure storage using AES encryption"""
import os
import base64
import hashlib
import logging
from cryptography.fernet import Fernet, InvalidToken
from app.config import BASE_DIR

logger = logging.getLogger("knowall.crypto")

_KEY_FILE = BASE_DIR / "data" / ".secret_key"


def _get_or_create_key() -> bytes:
    """Get or create the encryption key."""
    if _KEY_FILE.exists():
        try:
            return _KEY_FILE.read_bytes()
        except Exception as e:
            logger.error("Failed to read encryption key file: %s", e)
            raise RuntimeError(f"无法读取加密密钥，数据可能已损坏: {e}")

    key = Fernet.generate_key()
    try:
        _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        _KEY_FILE.write_bytes(key)
    except Exception as e:
        logger.error("Failed to write encryption key file: %s", e)
        raise RuntimeError(f"无法创建加密密钥文件，请检查磁盘空间和权限: {e}")

    # Restrict permissions (Unix only; gracefully handled on Windows)
    try:
        os.chmod(_KEY_FILE, 0o600)
    except Exception:
        logger.warning("Could not set restrictive permissions on key file (expected on Windows)")

    return key


def encrypt_api_key(plaintext: str) -> str:
    """Encrypt an API key. Returns Fernet token (already base64-encoded)."""
    try:
        fernet = Fernet(_get_or_create_key())
    except Exception as e:
        raise RuntimeError(f"加密模块初始化失败: {e}")
    encrypted = fernet.encrypt(plaintext.encode("utf-8"))
    # Fernet.encrypt already returns base64-encoded bytes; decode to string
    return encrypted.decode("ascii")


def decrypt_api_key(ciphertext: str) -> str:
    """Decrypt an API key. Returns the original plaintext."""
    try:
        fernet = Fernet(_get_or_create_key())
    except Exception as e:
        raise ValueError(f"加密模块初始化失败: {e}")
    try:
        # New format: Fernet token directly (starts with 'gAAAAAB')
        if ciphertext.startswith("gAAAAAB"):
            return fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        # Old format: double base64-encoded (Fernet token wrapped in base64)
        try:
            encrypted = base64.b64decode(ciphertext.encode("ascii"))
        except Exception:
            # Assume new format without the gAAAAAB prefix
            pass
        else:
            try:
                return fernet.decrypt(encrypted).decode("utf-8")
            except InvalidToken:
                pass
        # Last resort: treat as direct Fernet token
        return fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken:
        raise ValueError("API 密钥解密失败，密钥文件可能已损坏或被替换")
    except Exception as e:
        raise ValueError(f"API 密钥解密失败: {e}")
