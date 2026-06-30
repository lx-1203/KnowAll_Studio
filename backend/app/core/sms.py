"""SMS Service - Abstract provider interface for phone verification.

Supported providers (implement your own by subclassing BaseSMSProvider):
  - aliyun: Alibaba Cloud SMS (阿里云短信)
  - tencent: Tencent Cloud SMS (腾讯云短信)
  - custom:  Custom HTTP API

Usage:
  from app.core.sms import sms_service
  await sms_service.send_verification_code(phone_number)
  is_valid = sms_service.verify_code(phone_number, code)
"""

import secrets
import time
import hashlib
import hmac
import logging
import urllib.parse
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from app.config import settings

logger = logging.getLogger("knowall.sms")

# ── In-memory code store (use Redis in production) ──
_code_store: dict[str, dict] = {}
_phone_send_log: dict[str, list[float]] = {}  # phone -> [timestamps]


class BaseSMSProvider(ABC):
    """Abstract SMS provider. Implement this to add a new SMS gateway."""

    @abstractmethod
    async def send(self, phone: str, code: str) -> bool:
        """Send verification code to phone. Return True on success."""
        ...

    @abstractmethod
    def provider_name(self) -> str:
        ...


class ConsoleProvider(BaseSMSProvider):
    """Development provider: logs code to console instead of sending SMS."""

    def provider_name(self) -> str:
        return "console"

    async def send(self, phone: str, code: str) -> bool:
        logger.info("=" * 50)
        logger.info("  SMS Verification Code")
        logger.info("  Phone: %s", phone)
        logger.info("  Code:  %s", code)
        logger.info("  Expires in: %d seconds", settings.sms_code_expire_seconds)
        logger.info("=" * 50)
        return True


class AliyunSMSProvider(BaseSMSProvider):
    """Alibaba Cloud SMS (阿里云短信服务).

    Configuration in .env:
      SMS_PROVIDER=aliyun
      SMS_ACCESS_KEY=LTAI5t...
      SMS_SECRET_KEY=...
      SMS_SIGN_NAME=KnowAll
      SMS_TEMPLATE_CODE=SMS_123456789
    """

    def provider_name(self) -> str:
        return "aliyun"

    async def send(self, phone: str, code: str) -> bool:
        import httpx
        params = {
            "PhoneNumbers": phone,
            "SignName": settings.sms_sign_name,
            "TemplateCode": settings.sms_template_code,
            "TemplateParam": f'{{"code":"{code}"}}',
            "AccessKeyId": settings.sms_access_key,
            "Action": "SendSms",
            "Version": "2017-05-25",
            "SignatureMethod": "HMAC-SHA1",
            "SignatureVersion": "1.0",
            "SignatureNonce": secrets.token_hex(16),
            "Timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "Format": "JSON",
            "RegionId": "cn-hangzhou",
        }
        # Build signature
        sorted_keys = sorted(params.keys())
        canon_query = "&".join(
            f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(str(params[k]), safe='')}"
            for k in sorted_keys
        )
        string_to_sign = f"GET&{urllib.parse.quote('/', safe='')}&{urllib.parse.quote(canon_query, safe='')}"
        key = f"{settings.sms_secret_key}&"
        signature = hmac.new(key.encode(), string_to_sign.encode(), hashlib.sha1).digest()
        # Use base64 encoding from secrets module approach
        import base64
        params["Signature"] = base64.b64encode(signature).decode()

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://dysmsapi.aliyuncs.com/", params=params)
            data = resp.json()
            if data.get("Code") == "OK":
                return True
            logger.error("Aliyun SMS failed: %s", data)
            return False


class TencentSMSProvider(BaseSMSProvider):
    """Tencent Cloud SMS (腾讯云短信服务).

    Configuration in .env:
      SMS_PROVIDER=tencent
      SMS_ACCESS_KEY=AKID...
      SMS_SECRET_KEY=...
      SMS_SIGN_NAME=KnowAll
      SMS_TEMPLATE_CODE=1234567  (template ID, numeric)
    """

    def provider_name(self) -> str:
        return "tencent"

    async def send(self, phone: str, code: str) -> bool:
        import httpx
        import json as json_mod

        payload = {
            "PhoneNumberSet": [f"+86{phone}"],
            "SmsSdkAppId": settings.sms_access_key,
            "SignName": settings.sms_sign_name,
            "TemplateId": settings.sms_template_code,
            "TemplateParamSet": [code],
        }

        # Tencent Cloud API v3 signature
        timestamp = int(time.time())
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        service = "sms"
        host = "sms.tencentcloudapi.com"
        action = "SendSms"

        body = json_mod.dumps(payload)
        canonical_request = f"POST\n/\n\ncontent-type:application/json\nhost:{host}\n\ncontent-type;host\n{hashlib.sha256(body.encode()).hexdigest()}"
        credential_scope = f"{date}/{service}/tc3_request"
        string_to_sign = f"TC3-HMAC-SHA256\n{timestamp}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode()).hexdigest()}"

        def _sign(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode(), hashlib.sha256).digest()

        secret_date = _sign(f"TC3{settings.sms_secret_key}".encode(), date)
        secret_service = _sign(secret_date, service)
        secret_signing = _sign(secret_service, "tc3_request")
        signature = hmac.new(secret_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()

        authorization = (
            f"TC3-HMAC-SHA256 Credential={settings.sms_access_key}/{credential_scope}, "
            f"SignedHeaders=content-type;host, Signature={signature}"
        )

        headers = {
            "Content-Type": "application/json",
            "Host": host,
            "X-TC-Action": action,
            "X-TC-Timestamp": str(timestamp),
            "X-TC-Version": "2021-01-11",
            "X-TC-Region": "ap-guangzhou",
            "Authorization": authorization,
        }

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"https://{host}", content=body, headers=headers)
            data = resp.json()
            if "Error" not in data.get("Response", {}):
                return True
            logger.error("Tencent SMS failed: %s", data)
            return False


class CustomSMSProvider(BaseSMSProvider):
    """Custom HTTP API provider for self-hosted SMS gateways.

    Configuration in .env:
      SMS_PROVIDER=custom
      SMS_ACCESS_KEY=your_custom_key
      SMS_SECRET_KEY=your_custom_secret
      SMS_SIGN_NAME=KnowAll
      SMS_TEMPLATE_CODE=your_template

    Override the send() method or configure your API endpoint in the implementation.
    """

    def provider_name(self) -> str:
        return "custom"

    async def send(self, phone: str, code: str) -> bool:
        import httpx
        # Placeholder: implement your custom SMS gateway HTTP call here
        # Example:
        # async with httpx.AsyncClient(timeout=10) as client:
        #     resp = await client.post("https://your-sms-api.com/send", json={
        #         "key": settings.sms_access_key,
        #         "secret": settings.sms_secret_key,
        #         "phone": phone,
        #         "message": f"您的验证码是：{code}，{settings.sms_code_expire_seconds // 60}分钟内有效。",
        #     })
        #     return resp.status_code == 200
        logger.warning("CustomSMSProvider.send() is not implemented. Phone=%s Code=%s", phone, code)
        return False


# ── Provider Factory ──

def _create_provider() -> BaseSMSProvider:
    provider_map = {
        "aliyun": AliyunSMSProvider,
        "tencent": TencentSMSProvider,
        "custom": CustomSMSProvider,
    }
    provider_name = settings.sms_provider.lower().strip()
    if provider_name in provider_map:
        return provider_map[provider_name]()
    if provider_name:
        logger.warning("Unknown SMS provider '%s', falling back to console", provider_name)
    return ConsoleProvider()


class SMSService:
    """High-level SMS service with rate limiting and code management."""

    def __init__(self):
        self._provider = _create_provider()

    @property
    def provider(self) -> BaseSMSProvider:
        return self._provider

    def _check_rate_limit(self, phone: str) -> None:
        """Check per-phone send rate limit."""
        now = time.time()
        window_start = now - 3600  # 1 hour window
        if phone not in _phone_send_log:
            _phone_send_log[phone] = []
        _phone_send_log[phone] = [t for t in _phone_send_log[phone] if t > window_start]
        if len(_phone_send_log[phone]) >= settings.sms_send_limit_per_hour:
            from fastapi import HTTPException
            raise HTTPException(429, f"短信发送过于频繁，每小时最多{settings.sms_send_limit_per_hour}条，请稍后再试")

    async def send_verification_code(self, phone: str) -> dict:
        """Send a verification code to the phone. Returns status info."""
        # Validate phone format (Chinese mobile)
        import re
        if not re.match(r"^1[3-9]\d{9}$", phone):
            from fastapi import HTTPException
            raise HTTPException(400, "手机号格式不正确")

        self._check_rate_limit(phone)

        code = "".join(secrets.choice("0123456789") for _ in range(settings.sms_code_length))
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.sms_code_expire_seconds)

        # Store code (in production: use Redis with TTL)
        _code_store[phone] = {
            "code": code,
            "expires_at": expires_at,
            "attempts": 0,
        }
        _phone_send_log.setdefault(phone, []).append(time.time())

        success = await self._provider.send(phone, code)
        if not success and self._provider.provider_name() == "console":
            # Console provider always succeeds (just logs)
            success = True

        return {
            "sent": success,
            "phone": phone[:3] + "****" + phone[-4:],
            "expires_in_seconds": settings.sms_code_expire_seconds,
        }

    def verify_code(self, phone: str, code: str) -> bool:
        """Verify a code against the stored code. Raises on invalid/expired."""
        from fastapi import HTTPException

        stored = _code_store.get(phone)
        if not stored:
            raise HTTPException(400, "请先获取验证码")

        if stored["attempts"] >= 5:
            _code_store.pop(phone, None)
            raise HTTPException(400, "验证码尝试次数过多，请重新获取")

        stored["attempts"] += 1

        if datetime.now(timezone.utc) > stored["expires_at"]:
            _code_store.pop(phone, None)
            raise HTTPException(400, "验证码已过期，请重新获取")

        if code != stored["code"]:
            return False

        # Code verified — clean up
        _code_store.pop(phone, None)
        return True


# Singleton instance
sms_service = SMSService()
