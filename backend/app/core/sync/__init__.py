"""Sync persistence store — SQLite-backed storage for real-time sync data.

Replaces in-memory dicts with database-persisted storage so that
offline messages, operation logs, file versions, and upload sessions
survive server restarts.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone

from sqlalchemy import select, delete, and_, func

from app.database import async_session
from app.models import SyncOfflineMessage, SyncOpLog, SyncFileVersion

logger = logging.getLogger("knowall.sync_store")

MAX_OFFLINE_MSGS = 200
MAX_OP_LOG = 100
MAX_VERSIONS = 10


class SyncStore:
    """Persistent store for sync-related data."""

    # ── 离线消息 ──────────────────────────────────────────────────

    @staticmethod
    async def save_offline_message(
        user_id: str,
        msg_type: str,
        msg_data: dict,
        room_id: str = "",
        version: int = 0,
    ) -> None:
        async with async_session() as session:
            msg = SyncOfflineMessage(
                user_id=user_id,
                room_id=room_id,
                msg_type=msg_type,
                msg_data=msg_data,
                version=version,
            )
            session.add(msg)

            # Enforce max 200 per user
            stmt = (
                select(SyncOfflineMessage.id)
                .where(SyncOfflineMessage.user_id == user_id)
                .order_by(SyncOfflineMessage.created_at.desc())
                .offset(MAX_OFFLINE_MSGS)
            )
            result = await session.execute(stmt)
            stale_ids = result.scalars().all()
            if stale_ids:
                await session.execute(
                    delete(SyncOfflineMessage).where(
                        SyncOfflineMessage.id.in_(stale_ids)
                    )
                )
            await session.commit()

    @staticmethod
    async def pop_offline_messages(user_id: str) -> list[dict]:
        """Pop and delete all undelivered messages for a user (includes broadcast messages)."""
        from sqlalchemy import or_

        async with async_session() as session:
            stmt = (
                select(SyncOfflineMessage)
                .where(
                    and_(
                        or_(
                            SyncOfflineMessage.user_id == user_id,
                            SyncOfflineMessage.user_id == "all",  # 广播消息
                        ),
                        SyncOfflineMessage.delivered == False,
                    )
                )
                .order_by(SyncOfflineMessage.created_at)
            )
            result = await session.execute(stmt)
            msgs = result.scalars().all()

            payloads = []
            for msg in msgs:
                payloads.append({
                    "type": msg.msg_type,
                    "room_id": msg.room_id,
                    "version": msg.version,
                    "data": msg.msg_data,
                })
                # 广播消息不标记已送达（其他用户也需要看到）
                if msg.user_id != "all":
                    msg.delivered = True

            await session.commit()
            return payloads

    # ── 操作日志 ──────────────────────────────────────────────────

    @staticmethod
    async def append_op_log(room_id: str, version: int, user_id: str, operation: str, data: dict) -> None:
        async with async_session() as session:
            op = SyncOpLog(
                room_id=room_id,
                version=version,
                user_id=user_id,
                operation=operation,
                data=data,
            )
            session.add(op)

            # Enforce max 100 per room
            stmt = (
                select(SyncOpLog.id)
                .where(SyncOpLog.room_id == room_id)
                .order_by(SyncOpLog.version.desc())
                .offset(MAX_OP_LOG)
            )
            result = await session.execute(stmt)
            stale_ids = result.scalars().all()
            if stale_ids:
                await session.execute(
                    delete(SyncOpLog).where(SyncOpLog.id.in_(stale_ids))
                )
            await session.commit()

    @staticmethod
    async def get_ops_since(room_id: str, from_version: int) -> list[dict]:
        """Get operations since a given version (for incremental sync)."""
        async with async_session() as session:
            stmt = (
                select(SyncOpLog)
                .where(
                    and_(
                        SyncOpLog.room_id == room_id,
                        SyncOpLog.version > from_version,
                    )
                )
                .order_by(SyncOpLog.version)
            )
            result = await session.execute(stmt)
            ops = result.scalars().all()
            return [
                {
                    "version": op.version,
                    "op": op.operation,
                    "user_id": op.user_id,
                    "data": op.data,
                }
                for op in ops
            ]

    @staticmethod
    async def get_room_version(room_id: str) -> int:
        """Get the latest version number for a room."""
        async with async_session() as session:
            stmt = (
                select(func.max(SyncOpLog.version))
                .where(SyncOpLog.room_id == room_id)
            )
            result = await session.execute(stmt)
            return result.scalar() or 0

    # ── 文件版本 ──────────────────────────────────────────────────

    @staticmethod
    async def record_file_version(
        file_id: str,
        version: int,
        filename: str,
        file_size: int,
        storage_path: str,
        updated_by: str = "",
    ) -> None:
        async with async_session() as session:
            fv = SyncFileVersion(
                file_id=file_id,
                version=version,
                filename=filename,
                file_size=file_size,
                storage_path=storage_path,
                updated_by=updated_by,
            )
            session.add(fv)

            # Enforce max 10 versions per file
            stmt = (
                select(SyncFileVersion.id)
                .where(SyncFileVersion.file_id == file_id)
                .order_by(SyncFileVersion.version.desc())
                .offset(MAX_VERSIONS)
            )
            result = await session.execute(stmt)
            stale_ids = result.scalars().all()
            if stale_ids:
                await session.execute(
                    delete(SyncFileVersion).where(
                        SyncFileVersion.id.in_(stale_ids)
                    )
                )
            await session.commit()

    @staticmethod
    async def get_file_versions(file_id: str) -> list[dict]:
        async with async_session() as session:
            stmt = (
                select(SyncFileVersion)
                .where(SyncFileVersion.file_id == file_id)
                .order_by(SyncFileVersion.version.desc())
            )
            result = await session.execute(stmt)
            return [
                {
                    "version": v.version,
                    "filename": v.filename,
                    "file_size": v.file_size,
                    "updated_by": v.updated_by,
                    "created_at": v.created_at.isoformat() if v.created_at else None,
                }
                for v in result.scalars().all()
            ]

    @staticmethod
    async def get_current_file_version(file_id: str) -> int:
        async with async_session() as session:
            stmt = (
                select(func.max(SyncFileVersion.version))
                .where(SyncFileVersion.file_id == file_id)
            )
            result = await session.execute(stmt)
            return result.scalar() or 0

    # ── 事件补拉 ──────────────────────────────────────────────────

    @staticmethod
    async def get_events_since(room_id: str, from_seq: int, limit: int = 50) -> tuple[list[dict], int]:
        """Get events since a sequence number for catch-up."""
        async with async_session() as session:
            stmt = (
                select(SyncOpLog)
                .where(
                    and_(
                        SyncOpLog.room_id == room_id,
                        SyncOpLog.id > from_seq,
                    )
                )
                .order_by(SyncOpLog.id)
                .limit(limit)
            )
            result = await session.execute(stmt)
            events = result.scalars().all()
            current_seq = events[-1].id if events else from_seq
            return [
                {
                    "seq": e.id,
                    "type": e.operation,
                    "room_id": e.room_id,
                    "user_id": e.user_id,
                    "version": e.version,
                    "data": e.data,
                    "timestamp": int(e.created_at.timestamp() * 1000) if e.created_at else 0,
                }
                for e in events
            ], current_seq


sync_store = SyncStore()
