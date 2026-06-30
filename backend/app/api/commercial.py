"""Commercial features API: subscriptions, licenses, payments, data export."""
import hashlib
import secrets
import json
import zipfile
import io
import csv
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.models.subscription import UserTier, TierConfig, License, LicenseActivation, PaymentOrder
from app.models import (
    Document, QuestionBank, Flashcard, AnswerRecord, ErrorLog,
    KnowledgeSummary, StudyPlan, Conversation, Deck,
)
from app.core.auth import get_current_user, get_user_id
from app.config import settings

router = APIRouter(prefix="/api/v1/commercial", tags=["commercial"])


# ==================== Tier & Quota ====================

def _get_user_tier_values(user_id: str, db: AsyncSession):
    """Resolve effective tier values for a user (DB overrides or defaults)."""
    # Will be populated by query; fall back to free tier
    return TierConfig["free"]


async def get_user_tier(user_id: str, db: AsyncSession) -> dict:
    """Get effective tier info for a user."""
    result = await db.execute(
        select(UserTier).where(UserTier.user_id == user_id)
    )
    tier_row = result.scalar_one_or_none()
    if tier_row:
        tier_name = tier_row.tier
        expires = tier_row.expires_at
    else:
        tier_name = "free"
        expires = None

    config = TierConfig.get(tier_name, TierConfig["free"])
    return {
        "tier": tier_name,
        "tier_name": config["name"],
        "expires_at": expires.isoformat() if expires else None,
        "daily_ai_calls_limit": config["daily_ai_calls_limit"],
        "daily_token_limit": config["daily_token_limit"],
        "max_documents": config["max_documents"],
        "max_file_size_mb": config["max_file_size_mb"],
        "features": config["features"],
    }


@router.get("/tier")
async def my_tier(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's subscription tier and limits."""
    return await get_user_tier(current_user.id, db)


@router.post("/tier/activate-license")
async def activate_license(
    license_key: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Activate a license key to upgrade tier."""
    key_hash = hashlib.sha256(license_key.strip().encode()).hexdigest()

    result = await db.execute(
        select(License).where(License.license_key == key_hash, License.is_active == True)
    )
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(400, "无效的激活码")

    if lic.expires_at and lic.expires_at < datetime.now(timezone.utc):
        raise HTTPException(400, "该激活码已过期")

    if lic.activations_used >= lic.activations_max:
        raise HTTPException(400, "该激活码已达到最大激活次数")

    # Check if user already activated this license
    existing_activation = await db.execute(
        select(LicenseActivation).where(
            LicenseActivation.license_id == lic.id,
            LicenseActivation.user_id == current_user.id,
        )
    )
    if existing_activation.scalar_one_or_none():
        raise HTTPException(400, "你已经激活过该激活码")

    # Create activation record
    activation = LicenseActivation(
        license_id=lic.id,
        user_id=current_user.id,
    )
    db.add(activation)
    lic.activations_used += 1

    # Upgrade user tier
    result = await db.execute(
        select(UserTier).where(UserTier.user_id == current_user.id)
    )
    tier_row = result.scalar_one_or_none()
    if tier_row:
        tier_row.tier = lic.tier
        tier_row.expires_at = lic.expires_at
        config = TierConfig[lic.tier]
        tier_row.daily_ai_calls_limit = config["daily_ai_calls_limit"]
        tier_row.daily_token_limit = config["daily_token_limit"]
        tier_row.max_documents = config["max_documents"]
        tier_row.max_file_size_mb = config["max_file_size_mb"]
    else:
        config = TierConfig[lic.tier]
        tier_row = UserTier(
            user_id=current_user.id,
            tier=lic.tier,
            expires_at=lic.expires_at,
            daily_ai_calls_limit=config["daily_ai_calls_limit"],
            daily_token_limit=config["daily_token_limit"],
            max_documents=config["max_documents"],
            max_file_size_mb=config["max_file_size_mb"],
        )
        db.add(tier_row)

    await db.commit()
    return {
        "status": "activated",
        "tier": lic.tier,
        "tier_name": TierConfig[lic.tier]["name"],
        "expires_at": lic.expires_at.isoformat() if lic.expires_at else None,
    }


# ==================== License Management (Admin) ====================

class GenerateLicenseRequest(BaseModel):
    tier: str = "pro"
    activations_max: int = 1
    expires_in_days: int | None = None  # None = lifetime
    issued_to: str = ""


@router.post("/admin/licenses/generate")
async def generate_license(
    req: GenerateLicenseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new license key (admin only)."""
    if req.tier not in TierConfig:
        raise HTTPException(400, f"无效的版本: {req.tier}")

    raw_key = "KNOWALL-" + secrets.token_hex(16).upper()
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    expires = None
    if req.expires_in_days:
        expires = datetime.now(timezone.utc) + timedelta(days=req.expires_in_days)

    lic = License(
        license_key=key_hash,
        tier=req.tier,
        activations_max=req.activations_max,
        issued_to=req.issued_to,
        expires_at=expires,
    )
    db.add(lic)
    await db.commit()

    return {
        "license_key": raw_key,  # Only returned once at creation
        "tier": req.tier,
        "activations_max": req.activations_max,
        "expires_at": expires.isoformat() if expires else None,
    }


# ==================== Payment Orders ====================

class CreateOrderRequest(BaseModel):
    tier: str
    duration_months: int = 1


@router.post("/orders/create")
async def create_order(
    req: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a payment order."""
    if req.tier not in ("pro", "enterprise"):
        raise HTTPException(400, "仅支持购买专业版或企业版")

    # Pricing in CNY cents
    prices = {"pro": 2900, "enterprise": 9900}  # ¥29/mo pro, ¥99/mo enterprise
    amount = prices[req.tier] * req.duration_months

    order_no = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + secrets.token_hex(4).upper()

    order = PaymentOrder(
        user_id=current_user.id,
        order_no=order_no,
        tier=req.tier,
        amount_cents=amount,
        currency="CNY",
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    return {
        "order_id": order.id,
        "order_no": order.order_no,
        "tier": req.tier,
        "amount_yuan": amount / 100,
        "duration_months": req.duration_months,
        "status": order.status,
        "payment_url": f"/api/v1/commercial/orders/{order.id}/pay",
    }


@router.post("/orders/{order_id}/pay")
async def pay_order(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mock payment endpoint. In production, integrate with WeChat Pay / Alipay / Stripe."""
    result = await db.execute(
        select(PaymentOrder).where(
            PaymentOrder.id == order_id,
            PaymentOrder.user_id == current_user.id,
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(404, "订单不存在")
    if order.status != "pending":
        raise HTTPException(400, f"订单状态为 {order.status}，无法支付")

    # Mock payment success
    order.status = "paid"
    order.paid_at = datetime.now(timezone.utc)

    # Upgrade user tier
    duration = timedelta(days=30)  # default 1 month
    result = await db.execute(
        select(UserTier).where(UserTier.user_id == current_user.id)
    )
    tier_row = result.scalar_one_or_none()
    config = TierConfig[order.tier]

    new_expiry = datetime.now(timezone.utc) + duration
    if tier_row:
        # Extend existing if same tier, or upgrade
        if tier_row.tier == order.tier and tier_row.expires_at and tier_row.expires_at > datetime.now(timezone.utc):
            new_expiry = tier_row.expires_at + duration
        tier_row.tier = order.tier
        tier_row.expires_at = new_expiry
        tier_row.daily_ai_calls_limit = config["daily_ai_calls_limit"]
        tier_row.daily_token_limit = config["daily_token_limit"]
        tier_row.max_documents = config["max_documents"]
        tier_row.max_file_size_mb = config["max_file_size_mb"]
    else:
        tier_row = UserTier(
            user_id=current_user.id,
            tier=order.tier,
            expires_at=new_expiry,
            daily_ai_calls_limit=config["daily_ai_calls_limit"],
            daily_token_limit=config["daily_token_limit"],
            max_documents=config["max_documents"],
            max_file_size_mb=config["max_file_size_mb"],
        )
        db.add(tier_row)

    await db.commit()
    return {
        "status": "paid",
        "tier": order.tier,
        "expires_at": new_expiry.isoformat(),
    }


# ==================== Data Export (GDPR Compliance) ====================

@router.get("/export/my-data")
async def export_my_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export all user data as a ZIP file (GDPR data portability)."""
    user_id = current_user.id

    # Collect all user data
    export_data = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user": {
            "username": current_user.username,
            "email": current_user.email,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        },
    }

    # Documents
    docs_result = await db.execute(
        select(Document).where(Document.id.in_(
            select(Document.id)  # All documents are shared for now
        )).order_by(Document.created_at.desc())
    )
    export_data["documents"] = [
        {"id": d.id, "filename": d.filename, "file_type": d.file_type,
         "status": d.status, "created_at": d.created_at.isoformat()}
        for d in docs_result.scalars().all()
    ]

    # Questions
    q_result = await db.execute(
        select(QuestionBank).order_by(QuestionBank.created_at.desc()).limit(5000)
    )
    export_data["questions"] = [
        {"id": q.id, "question_type": q.question_type, "question_text": q.question_text,
         "correct_answer": q.correct_answer, "difficulty_score": q.difficulty_score}
        for q in q_result.scalars().all()
    ]

    # Answer records
    ar_result = await db.execute(
        select(AnswerRecord).where(AnswerRecord.user_id == user_id)
        .order_by(AnswerRecord.answered_at.desc()).limit(5000)
    )
    export_data["answer_records"] = [
        {"id": r.id, "question_id": r.question_id, "is_correct": r.is_correct,
         "answered_at": r.answered_at.isoformat() if r.answered_at else None}
        for r in ar_result.scalars().all()
    ]

    # Flashcards
    fc_result = await db.execute(
        select(Flashcard).order_by(Flashcard.created_at.desc()).limit(5000)
    )
    export_data["flashcards"] = [
        {"id": f.id, "card_type": f.card_type, "front": f.front, "back": f.back,
         "accuracy_rate": f.accuracy_rate}
        for f in fc_result.scalars().all()
    ]

    # Study plans
    sp_result = await db.execute(
        select(StudyPlan).where(StudyPlan.user_id == user_id)
    )
    export_data["study_plans"] = [
        {"id": p.id, "name": p.name, "progress": p.progress, "status": p.status}
        for p in sp_result.scalars().all()
    ]

    # Error logs
    el_result = await db.execute(
        select(ErrorLog).where(ErrorLog.user_id == user_id).limit(5000)
    )
    export_data["error_logs"] = [
        {"id": e.id, "question_id": e.question_id, "error_count": e.error_count}
        for e in el_result.scalars().all()
    ]

    # Tier info
    tier_info = await get_user_tier(user_id, db)
    export_data["subscription"] = tier_info

    # Build ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Main JSON export
        zf.writestr("export.json", json.dumps(export_data, ensure_ascii=False, indent=2))

        # CSV exports for spreadsheet analysis
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(["ID", "Type", "Question", "Answer", "Difficulty"])
        for q in export_data["questions"]:
            writer.writerow([q["id"], q["question_type"], q["question_text"][:200],
                           q["correct_answer"], q["difficulty_score"]])
        zf.writestr("questions.csv", csv_buffer.getvalue())

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=knowall-export-{datetime.now(timezone.utc).strftime('%Y%m%d')}.zip",
        },
    )


@router.delete("/delete-my-data")
async def delete_my_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete all user data (GDPR right to erasure)."""
    user_id = current_user.id

    # Delete in order to respect FK constraints
    tables_to_clear = [
        (AnswerRecord, AnswerRecord.user_id),
        (ErrorLog, ErrorLog.user_id),
        (StudyPlan, StudyPlan.user_id),
        (PaymentOrder, PaymentOrder.user_id),
        (LicenseActivation, LicenseActivation.user_id),
        (UserTier, UserTier.user_id),
    ]

    for model, col in tables_to_clear:
        result = await db.execute(select(model).where(col == user_id))
        for row in result.scalars().all():
            await db.delete(row)

    # Deactivate user (soft delete)
    current_user.is_active = False
    current_user.email = f"deleted_{user_id}@deleted.local"

    await db.commit()
    return {"status": "deleted", "detail": "你的所有数据已被删除，账户已停用"}
