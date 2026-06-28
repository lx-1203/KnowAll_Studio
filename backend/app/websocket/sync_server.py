"""WebSocket 实时同步服务器 — 房间管理 + 消息路由 + OT 操作转换"""
from __future__ import annotations
import asyncio
import json
import logging
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from jose import jwt, JWTError

from app.config import settings
from app.core.sync import sync_store

logger = logging.getLogger("knowall.sync")

router = APIRouter(prefix="/ws", tags=["sync"])

# ── 房间管理（进程内，通过 sync_store 持久化消息和日志） ──────────
_rooms: dict[str, set[tuple[WebSocket, str, str]]] = {}
_room_versions: dict[str, int] = {}

MAX_OP_LOG = 100
MAX_OFFLINE_MSGS = 200


def _verify_token(token: str) -> dict | None:
    """Verify JWT token and return payload or None."""
    if not token or not settings.jwt_secret:
        return None
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return payload
    except JWTError:
        return None


def _room_op_log_append(room_id: str, op: dict) -> None:
    if room_id not in _room_op_log:
        _room_op_log[room_id] = []
    _room_op_log[room_id].append(op)
    if len(_room_op_log[room_id]) > MAX_OP_LOG:
        _room_op_log[room_id] = _room_op_log[room_id][-MAX_OP_LOG:]


def _offline_msg_append(user_id: str, msg: dict) -> None:
    if user_id not in _offline_msgs:
        _offline_msgs[user_id] = []
    _offline_msgs[user_id].append(msg)
    if len(_offline_msgs[user_id]) > MAX_OFFLINE_MSGS:
        _offline_msgs[user_id] = _offline_msgs[user_id][-MAX_OFFLINE_MSGS:]


async def _broadcast(room_id: str, message: dict, exclude: WebSocket | None = None) -> None:
    """广播消息给房间内所有人（可排除发送者）"""
    if room_id not in _rooms:
        return
    dead: list = []
    raw = json.dumps(message, ensure_ascii=False)
    for ws, _uid, _uname in _rooms[room_id]:
        if ws == exclude:
            continue
        try:
            await ws.send_text(raw)
        except Exception:
            dead.append((ws, _uid, _uname))
    # 清理断连
    for item in dead:
        _rooms[room_id].discard(item)


def _get_room_members(room_id: str) -> list[dict]:
    """获取房间在线成员列表"""
    if room_id not in _rooms:
        return []
    return [
        {"user_id": uid, "user_name": uname}
        for _ws, uid, uname in _rooms[room_id]
    ]


async def _broadcast_presence(room_id: str) -> None:
    """广播在线状态"""
    members = _get_room_members(room_id)
    await _broadcast(room_id, {
        "type": "presence",
        "room_id": room_id,
        "data": {
            "online_users": members,
            "total_online": len(members),
        },
    })


# ── 简易 OT 变换 ──────────────────────────────────────────────────────

def _ot_transform_insert_insert(op_a: dict, op_b: dict) -> tuple[dict, dict]:
    """两个 insert 操作的 OT 变换"""
    pos_a = op_a.get("position", 0)
    pos_b = op_b.get("position", 0)
    len_a = len(op_a.get("value", ""))
    len_b = len(op_b.get("value", ""))

    a_new = dict(op_a)
    b_new = dict(op_b)
    if pos_a < pos_b or (pos_a == pos_b):
        # a 在前面，b 的位置需要偏移
        b_new["position"] = pos_b + len_a
    else:
        a_new["position"] = pos_a + len_b
    return a_new, b_new


def _ot_transform(op_new: dict, op_existing: dict) -> tuple[dict, dict]:
    """对两个操作做 OT 双向变换。"""
    op_type = op_new.get("operation", "")
    exist_type = op_existing.get("operation", "")

    if op_type == "insert" and exist_type == "insert":
        return _ot_transform_insert_insert(op_new, op_existing)

    # 其他组合暂做简单处理：位置偏移
    return op_new, op_existing


def _op_path_key(op: dict) -> str:
    """操作的路径标识，用于判断是否可以合并"""
    return ".".join(str(x) for x in op.get("path", []))


# ── WebSocket 端点 ────────────────────────────────────────────────────

@router.websocket("/sync")
async def sync_websocket(
    ws: WebSocket,
    doc_id: str = Query(...),
    user_id: str = Query(...),
    user_name: str = Query(""),
    token: str = Query(""),
):
    """实时同步 WebSocket 端点。query 参数: doc_id, user_id, user_name, token"""
    # TODO: token 验证
    await ws.accept()
    logger.info("WebSocket 连接: doc=%s user=%s(%s)", doc_id, user_id, user_name)

    # ── 加入房间 ──
    if doc_id not in _rooms:
        _rooms[doc_id] = set()
    _rooms[doc_id].add((ws, user_id, user_name))
    if doc_id not in _room_versions:
        _room_versions[doc_id] = 0

    # ── 发送全量同步（首次连接） ──
    await ws.send_text(json.dumps({
        "type": "sync_full",
        "doc_id": doc_id,
        "data": {
            "version": _room_versions[doc_id],
            "content": None,  # 由业务层填充
        },
    }, ensure_ascii=False))

    # ── 推送离线消息 ──
    offline = _offline_msgs.pop(user_id, [])
    for msg in offline:
        try:
            await ws.send_text(json.dumps(msg, ensure_ascii=False))
        except Exception:
            pass

    # ── 广播在线状态 ──
    await _broadcast_presence(doc_id)

    # ── 消息循环 ──
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg: dict = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_text(json.dumps({
                    "type": "error",
                    "data": {"code": "INVALID_JSON", "msg": "消息格式错误"},
                }))
                continue

            msg_type = msg.get("type", "")
            msg_data = msg.get("data", {})

            if msg_type == "heartbeat":
                # 心跳回复
                await ws.send_text(json.dumps({"type": "heartbeat_ack", "data": {}}))

            elif msg_type == "reconnect":
                # 重连：比对版本，决定增量/全量同步
                local_version = msg.get("local_version", 0)
                server_version = _room_versions.get(doc_id, 0)
                if local_version == server_version:
                    await ws.send_text(json.dumps({
                        "type": "ack", "data": {"new_version": server_version},
                    }))
                elif server_version - local_version <= 50 and doc_id in _room_op_log:
                    diff_ops = _room_op_log[doc_id][local_version:]
                    await ws.send_text(json.dumps({
                        "type": "sync_diff",
                        "data": {"ops": diff_ops, "version": server_version},
                    }, ensure_ascii=False))
                else:
                    await ws.send_text(json.dumps({
                        "type": "sync_full",
                        "data": {"version": server_version, "content": None},
                    }))

            elif msg_type == "operation":
                client_version = msg.get("version", 0)
                server_version = _room_versions.get(doc_id, 0)

                # ── OT 变换 ──
                transformed_data = dict(msg_data)
                if client_version < server_version and doc_id in _room_op_log:
                    ops_since = _room_op_log[doc_id][client_version:]
                    for applied_op in ops_since:
                        transformed_data, _ = _ot_transform(
                            {"operation": msg_data.get("operation", ""),
                             "position": msg_data.get("position", 0),
                             "value": msg_data.get("value", ""),
                             "path": msg_data.get("path", [])},
                            applied_op,
                        )
                        # 合并回 msg_data 格式
                        msg_data.update(transformed_data)

                # ── 应用操作：版本号 +1 ──
                _room_versions[doc_id] = server_version + 1
                new_version = _room_versions[doc_id]

                # ── 记录操作日志 ──
                log_entry = {
                    "version": new_version,
                    "op": msg_data.get("operation"),
                    "position": msg_data.get("position"),
                    "value": msg_data.get("value"),
                    "path": msg_data.get("path", []),
                    "user_id": user_id,
                }
                _room_op_log_append(doc_id, log_entry)

                # ── ACK 发送者 ──
                await ws.send_text(json.dumps({
                    "type": "ack",
                    "data": {"new_version": new_version},
                }))

                # ── 广播给其他人 ──
                await _broadcast(doc_id, {
                    "type": "operation",
                    "doc_id": doc_id,
                    "user_id": user_id,
                    "user_name": user_name,
                    "version": new_version,
                    "timestamp": int(time.time() * 1000),
                    "data": msg_data,
                }, exclude=ws)

            elif msg_type == "cursor":
                await _broadcast(doc_id, {
                    "type": "cursor",
                    "doc_id": doc_id,
                    "user_id": user_id,
                    "user_name": user_name,
                    "data": msg_data,
                }, exclude=ws)

            elif msg_type == "file_uploaded":
                await _broadcast(doc_id, {
                    "type": "file_uploaded",
                    "data": {**msg_data, "uploaded_by": user_id, "uploaded_by_name": user_name,
                             "timestamp": int(time.time() * 1000)},
                })

            elif msg_type == "file_deleted":
                await _broadcast(doc_id, {
                    "type": "file_deleted",
                    "data": {**msg_data, "deleted_by": user_id, "deleted_by_name": user_name,
                             "timestamp": int(time.time() * 1000)},
                })

            elif msg_type == "file_updated":
                await _broadcast(doc_id, {
                    "type": "file_updated",
                    "data": {**msg_data, "updated_by": user_id, "updated_by_name": user_name,
                             "timestamp": int(time.time() * 1000)},
                })

            elif msg_type == "chat_message":
                await _broadcast(doc_id, {
                    "type": "chat_message",
                    "data": {**msg_data, "from_user_id": user_id, "from_user_name": user_name,
                             "timestamp": int(time.time() * 1000)},
                })

            elif msg_type == "upload_progress":
                await _broadcast(doc_id, {
                    "type": "upload_progress",
                    "data": {**msg_data, "user_id": user_id, "user_name": user_name},
                }, exclude=ws)

            else:
                await ws.send_text(json.dumps({
                    "type": "error",
                    "data": {"code": "UNKNOWN_TYPE", "msg": f"未知消息类型: {msg_type}"},
                }))

    except WebSocketDisconnect:
        logger.info("WebSocket 断开: doc=%s user=%s(%s)", doc_id, user_id, user_name)
    except Exception:
        logger.exception("WebSocket 异常: doc=%s user=%s", doc_id, user_id)
    finally:
        # ── 离开房间 ──
        if doc_id in _rooms:
            _rooms[doc_id].discard((ws, user_id, user_name))
            if not _rooms[doc_id]:
                del _rooms[doc_id]
        await _broadcast_presence(doc_id)


# ── HTTP 辅助端点 ─────────────────────────────────────────────────────

@router.get("/rooms")
async def list_rooms():
    """列出所有活跃房间（调试用）"""
    return {
        "rooms": [
            {"room_id": rid, "members": len(members)}
            for rid, members in _rooms.items()
        ]
    }


@router.get("/rooms/{room_id}/members")
async def room_members(room_id: str):
    """获取房间成员"""
    return {"members": _get_room_members(room_id)}
