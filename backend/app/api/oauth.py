"""OAuth2 third-party login: QQ, WeChat, GitHub, Google"""
import secrets
import hashlib
import urllib.parse
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import httpx

from app.database import get_db
from app.models.user import User
from app.models.user_bind import UserBind
from app.core.auth import create_access_token, hash_password
from app.config import settings

router = APIRouter(prefix="/api/v1/oauth", tags=["oauth"])
logger = logging.getLogger("knowall.oauth")

# OAuth state tokens (in production: use Redis with TTL)
_oauth_states: dict[str, dict] = {}

# ── Provider configurations ──
# Set these in .env or admin panel. Leave empty to disable a provider.
OAUTH_PROVIDERS = {
    "qq": {
        "name": "QQ",
        "authorize_url": "https://graph.qq.com/oauth2.0/authorize",
        "token_url": "https://graph.qq.com/oauth2.0/token",
        "openid_url": "https://graph.qq.com/oauth2.0/me",
        "userinfo_url": "https://graph.qq.com/user/get_user_info",
        "client_id": settings.oauth_qq_client_id or "",
        "client_secret": settings.oauth_qq_client_secret or "",
        "scope": "get_user_info",
        "icon": "qq",
        "color": "#12B7F5",
    },
    "wechat": {
        "name": "微信",
        "authorize_url": "https://open.weixin.qq.com/connect/qrconnect",
        "token_url": "https://api.weixin.qq.com/sns/oauth2/access_token",
        "userinfo_url": "https://api.weixin.qq.com/sns/userinfo",
        "client_id": settings.oauth_wechat_client_id or "",
        "client_secret": settings.oauth_wechat_client_secret or "",
        "scope": "snsapi_login",
        "icon": "wechat",
        "color": "#07C160",
    },
    "github": {
        "name": "GitHub",
        "authorize_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "userinfo_url": "https://api.github.com/user",
        "client_id": settings.oauth_github_client_id or "",
        "client_secret": settings.oauth_github_client_secret or "",
        "scope": "user:email",
        "icon": "github",
        "color": "#24292e",
    },
    "google": {
        "name": "Google",
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "client_id": settings.oauth_google_client_id or "",
        "client_secret": settings.oauth_google_client_secret or "",
        "scope": "openid profile email",
        "icon": "google",
        "color": "#4285F4",
    },
}


def _get_redirect_uri(request: Request, provider: str) -> str:
    """Build the OAuth callback URL from the request origin."""
    base = str(request.base_url).rstrip("/")
    # In development, use the same origin
    return f"{base}/api/v1/oauth/{provider}/callback"


@router.get("/providers")
async def list_providers():
    """List available OAuth providers (only those with configured credentials)."""
    available = []
    for key, cfg in OAUTH_PROVIDERS.items():
        if cfg["client_id"]:
            available.append({
                "provider": key,
                "name": cfg["name"],
                "icon": cfg["icon"],
                "color": cfg["color"],
            })
    return {"providers": available}


@router.get("/{provider}/login")
async def oauth_login(provider: str, request: Request, redirect_to: str = "/"):
    """Initiate OAuth login flow. Redirects user to provider's authorize page."""
    cfg = OAUTH_PROVIDERS.get(provider)
    if not cfg or not cfg["client_id"]:
        raise HTTPException(400, f"Provider '{provider}' is not configured")

    state = secrets.token_urlsafe(32)
    _oauth_states[state] = {
        "provider": provider,
        "redirect_to": redirect_to,
        "created_at": datetime.now(timezone.utc),
    }

    params = {
        "response_type": "code",
        "client_id": cfg["client_id"],
        "redirect_uri": _get_redirect_uri(request, provider),
        "scope": cfg["scope"],
        "state": state,
    }

    # WeChat uses a different parameter name and appends #wechat_redirect
    if provider == "wechat":
        params["appid"] = params.pop("client_id")
        url = cfg["authorize_url"] + "?" + urllib.parse.urlencode(params) + "#wechat_redirect"
    else:
        url = cfg["authorize_url"] + "?" + urllib.parse.urlencode(params)

    return RedirectResponse(url)


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str,
    state: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle OAuth callback: exchange code for token, fetch user info, login or create user."""
    cfg = OAUTH_PROVIDERS.get(provider)
    if not cfg:
        raise HTTPException(400, f"Unknown provider: {provider}")

    # Verify state to prevent CSRF
    state_data = _oauth_states.pop(state, None)
    if not state_data:
        raise HTTPException(400, "Invalid or expired state parameter")
    if state_data["provider"] != provider:
        raise HTTPException(400, "Provider mismatch in state")

    redirect_to = state_data.get("redirect_to", "/")

    async with httpx.AsyncClient(timeout=15) as client:
        # Step 1: Exchange code for access token
        token_params = {
            "grant_type": "authorization_code",
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "code": code,
            "redirect_uri": _get_redirect_uri(request, provider),
        }
        if provider == "wechat":
            token_params["appid"] = token_params.pop("client_id")
            token_params["secret"] = token_params.pop("client_secret")

        token_resp = await client.post(cfg["token_url"], data=token_params)
        if token_resp.status_code >= 400:
            logger.error("OAuth token exchange failed for %s: %s", provider, token_resp.text)
            raise HTTPException(502, "第三方登录授权失败，请重试")

        # Parse token response
        if provider == "qq":
            # QQ returns text: access_token=XXX&expires_in=XXX
            token_data = dict(urllib.parse.parse_qsl(token_resp.text))
            access_token = token_data.get("access_token")
        elif provider == "wechat":
            token_json = token_resp.json()
            access_token = token_json.get("access_token")
            openid = token_json.get("openid")
            unionid = token_json.get("unionid", openid)
        elif provider == "github":
            # GitHub returns form-encoded or JSON
            try:
                token_data = token_resp.json()
            except Exception:
                token_data = dict(urllib.parse.parse_qsl(token_resp.text))
            access_token = token_data.get("access_token")
        else:
            token_json = token_resp.json()
            access_token = token_json.get("access_token")

        if not access_token:
            logger.error("OAuth no access_token for %s: %s", provider, token_resp.text[:200])
            raise HTTPException(502, "获取第三方授权令牌失败")

        # Step 2: Get user's unique ID
        provider_uid = ""
        if provider == "qq":
            # QQ needs separate call to get openid
            openid_resp = await client.get(
                f"{cfg['openid_url']}?access_token={access_token}&unionid=1"
            )
            # Response: callback( {"client_id":"...", "openid":"..."} );
            raw = openid_resp.text.strip()
            import json
            json_str = raw[raw.index("(") + 1: raw.rindex(")")].strip()
            openid_data = json.loads(json_str)
            provider_uid = openid_data.get("unionid") or openid_data.get("openid", "")
        elif provider == "wechat":
            provider_uid = unionid or openid
        elif provider == "github":
            gh_resp = await client.get(
                cfg["userinfo_url"],
                headers={"Authorization": f"token {access_token}"},
            )
            gh_user = gh_resp.json()
            provider_uid = str(gh_user.get("id", ""))
        elif provider == "google":
            goog_resp = await client.get(
                cfg["userinfo_url"],
                headers={"Authorization": f"Bearer {access_token}"},
            )
            goog_user = goog_resp.json()
            provider_uid = goog_user.get("id", "")

        if not provider_uid:
            raise HTTPException(502, "获取第三方用户ID失败")

        # Step 3: Get user profile info
        nickname = ""
        avatar = ""
        email = ""
        if provider == "qq":
            qq_resp = await client.get(
                f"{cfg['userinfo_url']}?access_token={access_token}&oauth_consumer_key={cfg['client_id']}&openid={provider_uid}"
            )
            qq_user = qq_resp.json()
            nickname = qq_user.get("nickname", "")
            avatar = qq_user.get("figureurl_qq_2") or qq_user.get("figureurl_2", "")
        elif provider == "wechat":
            wx_resp = await client.get(
                f"{cfg['userinfo_url']}?access_token={access_token}&openid=openid"
            )
            wx_user = wx_resp.json()
            nickname = wx_user.get("nickname", "")
            avatar = wx_user.get("headimgurl", "")
        elif provider == "github":
            nickname = gh_user.get("login", "")
            avatar = gh_user.get("avatar_url", "")
            email = gh_user.get("email", "")
        elif provider == "google":
            nickname = goog_user.get("name", "")
            avatar = goog_user.get("picture", "")
            email = goog_user.get("email", "")

    # Step 4: Find or create user
    bind_result = await db.execute(
        select(UserBind).where(
            UserBind.provider == provider,
            UserBind.provider_uid == provider_uid,
            UserBind.is_bound == True,
        )
    )
    existing_bind = bind_result.scalar_one_or_none()

    if existing_bind:
        # Existing user — log them in
        user_result = await db.execute(select(User).where(User.id == existing_bind.user_id))
        user = user_result.scalar_one_or_none()
    else:
        # New user — create account
        username = f"{provider}_{provider_uid[:8]}"
        # Ensure unique username
        existing_user = await db.execute(select(User).where(User.username == username))
        if existing_user.scalar_one_or_none():
            username = f"{provider}_{provider_uid[:12]}_{secrets.token_hex(2)}"

        user = User(
            username=username,
            email=email or f"{provider_uid[:8]}@{provider}.oauth",
            password_hash=hash_password(secrets.token_urlsafe(32)),
            nickname=nickname,
            avatar_url=avatar,
            email_verified=bool(email),
        )
        db.add(user)
        await db.flush()

        # Create bind
        bind = UserBind(
            user_id=user.id,
            provider=provider,
            provider_name=cfg["name"],
            provider_uid=provider_uid,
            is_bound=True,
        )
        db.add(bind)

    await db.commit()
    await db.refresh(user)

    # Generate JWT token
    token = create_access_token(user.id)

    # Redirect back to frontend with token in URL fragment
    frontend_url = str(request.base_url).rstrip("/").replace(":8000", ":5173").replace(":8001", ":5173")
    callback_url = f"{frontend_url}{redirect_to}#oauth_token={token}&user_id={user.id}&username={user.username}&provider={provider}"
    return RedirectResponse(callback_url)
