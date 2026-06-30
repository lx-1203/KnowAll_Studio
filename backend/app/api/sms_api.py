"""SMS verification API - send verification code, verify phone, bind phone"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.core.auth import get_current_user, get_optional_user
from app.core.sms import sms_service

router = APIRouter(prefix="/api/v1/sms", tags=["sms"])


class SendCodeRequest(BaseModel):
    phone: str


class VerifyCodeRequest(BaseModel):
    phone: str
    code: str


class BindPhoneRequest(BaseModel):
    phone: str
    code: str


@router.post("/send-code")
async def send_verification_code(req: SendCodeRequest):
    """Send SMS verification code to a phone number.

    Rate limited: max 5 codes per phone per hour.
    Code expires after 5 minutes (configurable).
    """
    result = await sms_service.send_verification_code(req.phone)
    return {"detail": "验证码已发送" if result["sent"] else "发送失败，请稍后重试", **result}


@router.post("/verify-code")
async def verify_code(req: VerifyCodeRequest):
    """Verify an SMS code without binding (e.g., for login).

    Returns verified=True if the code matches and hasn't expired.
    """
    is_valid = sms_service.verify_code(req.phone, req.code)
    return {"verified": is_valid, "phone": req.phone[:3] + "****" + req.phone[-4:]}


@router.post("/bind-phone")
async def bind_phone(
    req: BindPhoneRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Bind and verify a phone number to the current user's account.

    Requires the correct SMS verification code.
    """
    # Verify the code first
    if not sms_service.verify_code(req.phone, req.code):
        raise HTTPException(400, "验证码错误")

    # Check if phone is already bound to another account
    existing = await db.execute(
        select(User).where(User.phone == req.phone, User.phone_verified == True)
    )
    other_user = existing.scalar_one_or_none()
    if other_user and other_user.id != current_user.id:
        raise HTTPException(409, "该手机号已绑定到其他账户")

    # Bind phone
    current_user.phone = req.phone
    current_user.phone_verified = True
    await db.commit()

    return {"detail": "手机号绑定成功", "phone": req.phone[:3] + "****" + req.phone[-4:]}


@router.post("/unbind-phone")
async def unbind_phone(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unbind the phone number from the current user's account."""
    if not current_user.phone:
        raise HTTPException(400, "没有绑定手机号")

    current_user.phone = ""
    current_user.phone_verified = False
    await db.commit()

    return {"detail": "手机号已解绑"}


@router.get("/phone-status")
async def phone_status(current_user: User = Depends(get_current_user)):
    """Get the current user's phone binding status."""
    return {
        "has_phone": bool(current_user.phone),
        "phone_masked": current_user.phone[:3] + "****" + current_user.phone[-4:] if current_user.phone else None,
        "phone_verified": bool(current_user.phone_verified),
    }
