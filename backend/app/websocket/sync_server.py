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
_last_heartbeat: dict[int, float] = {}  # id(ws) → last_ping_time
HEARTBEAT_INTERVAL = 15      # 客户端心跳间隔（秒）
HEARTBEAT_TIMEOUT = 30       # 超时断连（秒）
HEARTBEAT_CHECK_PERIOD = 10  # 服务端检查周期（秒）

MAX_OP_LOG = 100
MAX_OFFLINE_MSGS = 200


async def _heartbeat_checker() -> None:
    """Background task: disconnect clients that haven't sent heartbeat in HEARTBEAT_TIMEOUT seconds."""
    while True:
        await asyncio.sleep(HEARTBEAT_CHECK_PERIOD)
        now = time.time()
        stale: list[tuple[WebSocket, str, str, str]] = []  # (ws, uid, uname, room_id)
        for room_id, members in list(_rooms.items()):
            for ws, uid, uname in list(members):
                last = _last_heartbeat.get(id(ws), 0)
                # last==0 means no heartbeat received yet (just connected),
                # give a grace period of HEARTBEAT_TIMEOUT from connection time
                if last == 0:
                    continue
                if now - last > HEARTBEAT_TIMEOUT:
                    stale.append((ws, uid, uname, room_id))
        for ws, uid, uname, room_id in stale:
            logger.warning("心跳超时，断开: user=%s(%s) room=%s", uid, uname, room_id)
            try:
                await ws.close(code=4002, reason="心跳超时")
            except Exception:
                pass
            _rooms.get(room_id, set()).discard((ws, uid, uname))
            _last_heartbeat.pop(id(ws), None)
        # 广播 presence 更新给受影响的房间
        affected = set(room_id for _, _, _, room_id in stale)
        for room_id in affected:
            await _broadcast_presence(room_id)


# 启动心跳检查后台任务
_background_tasks: set[asyncio.Task] = set()


def start_background_tasks() -> None:
    """Start sync server background tasks (heartbeat checker).
    Called from FastAPI lifespan startup."""
    if not any(t.get_name() == "heartbeat_checker" for t in _background_tasks):
        task = asyncio.create_task(_heartbeat_checker(), name="heartbeat_checker")
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        logger.info("后台心跳检查任务已启动")


async def stop_background_tasks() -> None:
    """Cancel all background tasks on shutdown."""
    for task in list(_background_tasks):
        task.cancel()
    await asyncio.gather(*_background_tasks, return_exceptions=True)
    _background_tasks.clear()
    logger.info("后台任务已停止")


def _verify_token(token: str) -> dict | None:
    """Verify JWT token and return payload or None."""
    if not token or not settings.jwt_secret:
        return None
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return payload
    except JWTError:
        return None


async def _room_op_log_append(room_id: str, op: dict) -> None:
    """Append to operation log (persisted via sync_store)."""
    await sync_store.append_op_log(
        room_id=room_id,
        version=op.get("version", 0),
        user_id=op.get("user_id", ""),
        operation=op.get("op", ""),
        data=op.get("data", {}),
    )


async def _offline_msg_append(user_id: str, msg: dict) -> None:
    """Save offline message (persisted via sync_store)."""
    await sync_store.save_offline_message(
        user_id=user_id,
        msg_type=msg.get("type", ""),
        msg_data=msg.get("data", {}),
        room_id=msg.get("room_id", ""),
        version=msg.get("version", 0),
    )


async def _broadcast(room_id: str, message: dict, exclude: WebSocket | None = None) -> None:
    """广播消息给房间内所有人（可排除发送者）"""
    if room_id not in _rooms:
        return
    dead: list = []
    raw = json.dumps(message, ensure_ascii=False)
    # Snapshot iteration to avoid "Set changed size during iteration"
    # when _rooms[room_id] is modified by concurrent connection/disconnection
    for ws, _uid, _uname in list(_rooms[room_id]):
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
    # JWT token 验证
    if token:
        payload = _verify_token(token)
        if payload is None:
            await ws.accept()
            await ws.send_text(json.dumps({
                "type": "error",
                "data": {"code": "AUTH_FAILED", "msg": "Token 验证失败"},
            }))
            await ws.close(code=4001)
            return
    else:
        # 允许本地开发模式下无 token 连接
        logger.debug("WebSocket 连接无 token（允许本地模式）")

    await ws.accept()
    logger.info("WebSocket 连接: doc=%s user=%s(%s)", doc_id, user_id, user_name)

    # ── 记录心跳时间 ──
    _last_heartbeat[id(ws)] = time.time()

    # ── 加入房间 ──
    if doc_id not in _rooms:
        _rooms[doc_id] = set()
    _rooms[doc_id].add((ws, user_id, user_name))

    # ── 初始化房间版本（从持久化存储恢复） ──
    if doc_id not in _room_versions:
        _room_versions[doc_id] = await sync_store.get_room_version(doc_id)

    # ── 推送离线消息（从持久化存储弹出） ──
    # 按规范 6.2 节：客户端连接后发送 reconnect 消息来驱动同步
    offline = await sync_store.pop_offline_messages(user_id)
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
                # 心跳：更新时间戳，回复 ack
                _last_heartbeat[id(ws)] = time.time()
                await ws.send_text(json.dumps({"type": "heartbeat_ack", "data": {}}))

            elif msg_type == "reconnect":
                # 重连：比对版本，决定增量/全量同步
                local_version = msg.get("local_version", 0)
                server_version = _room_versions.get(doc_id, 0)
                if local_version == server_version:
                    await ws.send_text(json.dumps({
                        "type": "ack", "data": {"new_version": server_version},
                    }))
                elif server_version - local_version <= 50:
                    diff_ops = await sync_store.get_ops_since(doc_id, local_version)
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

                # ── 版本严重分叉检测 ──
                if server_version - client_version > 100:
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "data": {
                            "code": "VERSION_CONFLICT",
                            "msg": f"版本差距过大 (client={client_version}, server={server_version})，请请求全量同步",
                        },
                    }))
                    continue

                # ── OT 变换 ──
                transformed_data = dict(msg_data)
                if client_version < server_version:
                    ops_since = await sync_store.get_ops_since(doc_id, client_version)
                    for applied_op in ops_since:
                        transformed_data, _ = _ot_transform(
                            {"operation": msg_data.get("operation", ""),
                             "position": msg_data.get("position", 0),
                             "value": msg_data.get("value", ""),
                             "path": msg_data.get("path", [])},
                            applied_op.get("data", applied_op),
                        )
                        msg_data.update(transformed_data)

                # ── 应用操作：版本号 +1 ──
                _room_versions[doc_id] = server_version + 1
                new_version = _room_versions[doc_id]

                # ── 记录操作日志（持久化） ──
                log_entry = {
                    "version": new_version,
                    "op": msg_data.get("operation"),
                    "position": msg_data.get("position"),
                    "value": msg_data.get("value"),
                    "path": msg_data.get("path", []),
                    "user_id": user_id,
                }
                await _room_op_log_append(doc_id, {
                    "version": new_version,
                    "user_id": user_id,
                    "op": msg_data.get("operation", ""),
                    "data": msg_data,
                })

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
                broadcast_msg = {
                    "type": "chat_message",
                    "data": {**msg_data, "from_user_id": user_id, "from_user_name": user_name,
                             "timestamp": int(time.time() * 1000)},
                }
                await _broadcast(doc_id, broadcast_msg)
                # 保存离线消息给不在线的用户
                await _offline_msg_append("all", broadcast_msg)

            elif msg_type == "upload_progress":
                await _broadcast(doc_id, {
                    "type": "upload_progress",
                    "data": {**msg_data, "user_id": user_id, "user_name": user_name},
                }, exclude=ws)

            elif msg_type == "system_notify":
                # 系统通知（管理员操作、权限变更等）— 按规范 4.2 节
                notify_msg = {
                    "type": "system_notify",
                    "room_id": doc_id,
                    "data": {
                        **msg_data,
                        "timestamp": msg_data.get("timestamp", int(time.time() * 1000)),
                    },
                }
                await _broadcast(doc_id, notify_msg)
                await _offline_msg_append("all", notify_msg)

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
        _last_heartbeat.pop(id(ws), None)
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


# ── SSE 备选通道（按规范 4.1 节：WebSocket 不可用时使用 SSE） ────────

from fastapi.responses import StreamingResponse


@router.get("/sse/{room_id}")
async def sse_events(room_id: str, user_id: str = ""):
    """SSE 端点：单向推送房间事件（备选通道）"""
    import asyncio

    async def event_stream():
        last_version = _room_versions.get(room_id, 0)
        # 先推送当前版本
        yield f"data: {json.dumps({'type': 'sync_full', 'data': {'version': last_version, 'content': None}}, ensure_ascii=False)}\n\n"
        while True:
            await asyncio.sleep(2)  # 每 2 秒轮询
            current = _room_versions.get(room_id, 0)
            if current > last_version:
                diff_ops = await sync_store.get_ops_since(room_id, last_version)
                if diff_ops:
                    yield f"data: {json.dumps({'type': 'sync_diff', 'data': {'ops': diff_ops, 'version': current}}, ensure_ascii=False)}\n\n"
                last_version = current
            # 发送心跳注释保持连接
            yield f": heartbeat\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
