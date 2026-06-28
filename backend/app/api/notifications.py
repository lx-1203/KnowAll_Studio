"""Notification center API"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update

from app.database import get_db
from app.models.user import User
from app.models.notification import Notification
from app.core.auth import get_current_user
from app.schemas import NotificationItem, NotificationListResponse

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
async def get_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_read: str = Query("", description="Filter: '' = all, '0' = unread, '1' = read"),
    category: str = Query("", description="Filter by category"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated notifications list for current user."""
    base = select(Notification).where(Notification.user_id == current_user.id)
    count_base = select(func.count()).select_from(Notification).where(Notification.user_id == current_user.id)

    if is_read == "0":
        base = base.where(Notification.is_read == False)
        count_base = count_base.where(Notification.is_read == False)
    elif is_read == "1":
        base = base.where(Notification.is_read == True)
        count_base = count_base.where(Notification.is_read == True)

    if category:
        base = base.where(Notification.category == category)
        count_base = count_base.where(Notification.category == category)

    # Get total count
    total_result = await db.execute(count_base)
    total = total_result.scalar() or 0

    # Get unread count (unfiltered)
    unread_result = await db.execute(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
    )
    unread_count = unread_result.scalar() or 0

    # Fetch page
    offset = (page - 1) * page_size
    result = await db.execute(
        base.order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    records = result.scalars().all()

    items = [
        NotificationItem(
            id=r.id,
            title=r.title,
            content=r.content or "",
            category=r.category or "system",
            is_read=bool(r.is_read),
            resource_type=r.resource_type or "",
            resource_id=r.resource_id or "",
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in records
    ]

    return NotificationListResponse(total=total, unread_count=unread_count, items=items)


@router.put("/{notification_id}/read")
async def mark_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a single notification as read."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(status_code=404, detail="通知不存在")

    notification.is_read = True
    await db.commit()

    return {"detail": "已标记为已读"}


@router.put("/read-all")
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark all unread notifications as read."""
    await db.execute(
        update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
        .values(is_read=True)
    )
    await db.commit()

    return {"detail": "全部已标记为已读"}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a single notification."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(status_code=404, detail="通知不存在")

    await db.delete(notification)
    await db.commit()

    return {"detail": "通知已删除"}


@router.delete("")
async def batch_delete_notifications(
    ids: str = Query("", description="Comma-separated list of notification IDs to delete"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Batch delete notifications by IDs (comma-separated)."""
    id_list = [i.strip() for i in ids.split(",") if i.strip()]
    if not id_list:
        raise HTTPException(status_code=400, detail="请提供要删除的通知 ID 列表")

    from sqlalchemy import delete
    result = await db.execute(
        delete(Notification).where(
            Notification.id.in_(id_list),
            Notification.user_id == current_user.id,
        )
    )
    await db.commit()

    return {"detail": f"已删除 {result.rowcount} 条通知"}
