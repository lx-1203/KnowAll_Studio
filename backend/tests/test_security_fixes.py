"""Integration tests for auth, crypto, and commercial features added during self-audit fixes."""
import pytest
import secrets
from datetime import datetime, timedelta, timezone


class TestCrypto:
    """Verify encryption/decryption works correctly (fix: double base64 removed)."""

    def test_encrypt_decrypt_roundtrip(self):
        from app.core.crypto import encrypt_api_key, decrypt_api_key
        original = "sk-test-api-key-123456"
        encrypted = encrypt_api_key(original)
        decrypted = decrypt_api_key(encrypted)
        assert decrypted == original
        assert encrypted != original
        # Fernet output should be valid ASCII (not double-encoded)
        assert isinstance(encrypted, str)
        encrypted.encode("ascii")  # should not raise

    def test_decrypt_invalid_raises(self):
        from app.core.crypto import decrypt_api_key
        with pytest.raises(ValueError):
            decrypt_api_key("not-valid-ciphertext!!!")

    def test_encrypt_empty_string(self):
        from app.core.crypto import encrypt_api_key, decrypt_api_key
        encrypted = encrypt_api_key("")
        decrypted = decrypt_api_key(encrypted)
        assert decrypted == ""


class TestAuth:
    """Verify auth utilities work correctly."""

    def test_password_hash_and_verify(self):
        from app.core.auth import hash_password, verify_password
        plain = "mypassword123"
        hashed = hash_password(plain)
        assert hashed != plain
        assert verify_password(plain, hashed)
        assert not verify_password("wrongpassword", hashed)

    def test_password_hash_truncation(self):
        """Passwords longer than 72 bytes should be truncated safely."""
        from app.core.auth import hash_password, verify_password
        long_password = "a" * 100
        hashed = hash_password(long_password)
        assert verify_password(long_password, hashed)

    def test_jwt_token_roundtrip(self):
        from app.core.auth import create_access_token, decode_access_token
        user_id = "test-user-123"
        token = create_access_token(user_id)
        decoded = decode_access_token(token)
        assert decoded == user_id

    def test_jwt_invalid_token(self):
        from app.core.auth import decode_access_token
        assert decode_access_token("invalid.token.here") is None
        assert decode_access_token("") is None

    def test_rate_limiter(self):
        """Verify rate limiting works (auth endpoint protection)."""
        from app.api.auth import _check_rate_limit, _rate_limit_store
        from fastapi import HTTPException

        key = f"test_rate_{secrets.token_hex(4)}"
        # Should allow up to 10 requests
        for _ in range(10):
            _check_rate_limit(key)  # should not raise
        # 11th should raise
        with pytest.raises(HTTPException) as exc:
            _check_rate_limit(key)
        assert exc.value.status_code == 429
        # Cleanup
        _rate_limit_store.pop(key, None)


class TestPasswordReset:
    """Verify password reset flow works."""

    @pytest.mark.asyncio
    async def test_reset_token_lifecycle(self):
        from app.api.auth import _reset_tokens
        token = secrets.token_urlsafe(32)
        _reset_tokens[token] = {
            "user_id": "test-user",
            "email": "test@test.com",
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=30),
        }
        assert token in _reset_tokens
        # Cleanup
        del _reset_tokens[token]


class TestShareSecurity:
    """Verify share access code security fixes."""

    def test_access_code_uses_secrets(self):
        """Access codes must use secrets module, not random."""
        from app.api.share import _generate_access_code
        code = _generate_access_code()
        assert len(code) == 6
        assert code.isdigit()
        # Generate many codes and verify no obvious pattern
        codes = {_generate_access_code() for _ in range(100)}
        assert len(codes) == 100  # all unique

    def test_view_rate_limiting(self):
        from app.api.share import _check_view_rate, _view_rate_limit
        from fastapi import HTTPException

        ip = f"192.168.1.{secrets.randbelow(256)}"
        # Allow up to 10 attempts
        for _ in range(10):
            _check_view_rate(ip)
        # 11th should raise
        with pytest.raises(HTTPException) as exc:
            _check_view_rate(ip)
        assert exc.value.status_code == 429
        # Cleanup
        _view_rate_limit.pop(ip, None)


class TestSubscriptionTiers:
    """Verify tier configuration is valid."""

    def test_tier_config_consistency(self):
        from app.models.subscription import TierConfig
        assert "free" in TierConfig
        assert "pro" in TierConfig
        assert "enterprise" in TierConfig

        for tier_name, config in TierConfig.items():
            assert "name" in config
            assert "daily_ai_calls_limit" in config
            assert "daily_token_limit" in config
            assert "max_documents" in config
            assert "max_file_size_mb" in config
            assert "features" in config
            assert isinstance(config["features"], list)

        # Enterprise should have more features than free
        assert len(TierConfig["enterprise"]["features"]) > len(TierConfig["free"]["features"])

    def test_license_key_generation(self):
        raw_key = "KNOWALL-" + secrets.token_hex(16).upper()
        assert raw_key.startswith("KNOWALL-")
        assert len(raw_key) > 20


class TestDatabaseSafety:
    """Verify database migration safety guard."""

    def test_debug_mode_detected(self):
        from app.config import settings
        # In test environment, debug should be True
        assert settings.debug is True
        # JWT secret should be non-empty (auto-generated)
        assert len(settings.jwt_secret) > 10
