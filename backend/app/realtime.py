"""Permission-filtered ticket invalidations, delivered only after database commit."""
import asyncio
import json
import logging
import time
from contextlib import suppress

import psycopg
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import event, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal, engine
from app.models import Activity, Attachment, BrowserSession, Comment, Label, Project, ProjectMember, User, WorkItem
from app.permissions import visible_item, visible_project
from app.security import token_hash

router = APIRouter()
CHANNEL = "tracker_tickets"
subscribers: set[asyncio.Queue] = set()
logger = logging.getLogger(__name__)


@event.listens_for(Session, "after_flush")
def notify_changes(db, flush_context):
    if db.bind.dialect.name != "postgresql":
        return
    messages = set()
    # Defaults (notably new ticket IDs) have been assigned, but commit is still pending.
    for row in set(db.new) | set(db.dirty) | set(db.deleted):
        if row in db.dirty and not db.is_modified(row, include_collections=False):
            continue
        if isinstance(row, WorkItem) and row.id:
            messages.add(("item", row.id))
        elif isinstance(row, (Comment, Activity)):
            messages.add(("item", row.item_id))
        elif isinstance(row, Attachment) and not row.pending and row.item_id:
            messages.add(("item", row.item_id))
        elif isinstance(row, (Project, ProjectMember, Label)):
            messages.add(("project", row.id if isinstance(row, Project) else row.project_id))
        elif isinstance(row, User):
            messages.add(("resync", None))
    for kind, identifier in messages:
        # PostgreSQL delivers NOTIFY at commit and discards it on rollback.
        db.execute(text("SELECT pg_notify(:channel, :payload)"),
                   {"channel": CHANNEL, "payload": json.dumps([kind, identifier])})


def broadcast(message):
    for queue in tuple(subscribers):
        if queue.full():
            while not queue.empty():
                queue.get_nowait()
            queue.put_nowait(["resync", None])
        else:
            queue.put_nowait(message)


async def listen():
    dsn = engine.url.set(drivername="postgresql").render_as_string(hide_password=False)
    while True:
        try:
            async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as connection:
                await connection.execute(f"LISTEN {CHANNEL}")
                # A listener interruption may have lost events; refresh all active views.
                broadcast(["resync", None])
                async for notification in connection.notifies():
                    broadcast(json.loads(notification.payload))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Ticket event listener disconnected")
            await asyncio.sleep(2)


def snapshot(session_hash, project_id):
    """Fresh, short-lived transaction; never retain permissions on a live socket."""
    with SessionLocal() as db:
        session = db.get(BrowserSession, session_hash)
        if not session or session.expires_at <= int(time.time()):
            return None
        user = db.get(User, session.data.get("user_id", ""))
        if (not user or not user.active or user.is_bot or not user.role
                or session.data.get("auth_version", 0) != user.auth_version):
            return None
        project = db.scalar(select(Project).where(Project.id == project_id, visible_project(user)))
        if not project:
            return (user.id, False, frozenset())
        ids = frozenset(db.scalars(select(WorkItem.id).join(Project).where(
            Project.id == project_id, visible_item(user))))
        member = db.get(ProjectMember, (project_id, user.id))
        permission = (user.role, project.default_access, project.restrict_ticket_visibility,
                      member.role if member else None)
        return (user.id, permission, ids)


@router.websocket("/api/v1/tickets/live")
async def tickets_live(socket: WebSocket):
    settings = get_settings()
    if (socket.headers.get("origin") not in {settings.app_base_url, settings.api_base_url}
            or "authorization" in socket.headers):
        await socket.close(code=1008)
        return
    secret = socket.cookies.get(settings.session_cookie, "")
    project_id = socket.query_params.get("project", "")
    if not secret or not project_id or len(project_id) > 36:
        await socket.close(code=1008)
        return
    session_hash = token_hash(secret)
    queue = asyncio.Queue(maxsize=128)
    subscribers.add(queue)
    receiver = None
    try:
        previous = await asyncio.to_thread(snapshot, session_hash, project_id)
        if previous is None:
            await socket.close(code=1008)
            return
        await socket.accept()
        await socket.send_json({"type": "refresh"})
        receiver = asyncio.create_task(socket.receive_text())
        while True:
            waiter = asyncio.create_task(queue.get())
            try:
                done, _ = await asyncio.wait({waiter, receiver}, timeout=15,
                                             return_when=asyncio.FIRST_COMPLETED)
                if receiver in done:
                    receiver.result()
                    await socket.close(code=1008)
                    return
                message = waiter.result() if waiter in done else None
            finally:
                waiter.cancel()
                with suppress(asyncio.CancelledError):
                    await waiter
            current = await asyncio.to_thread(snapshot, session_hash, project_id)
            if current is None or current[0] != previous[0]:
                await socket.close(code=1008)
                return
            changed = current != previous
            if message:
                kind, identifier = message
                changed |= (kind == "item" and identifier in (current[2] | previous[2])
                            or bool(current[1] or previous[1]) and (
                                kind == "project" and identifier in {None, project_id}
                                or kind == "resync"))
            if changed:
                # No protected IDs, titles, comments or authors travel over this channel.
                await socket.send_json({"type": "refresh"})
            else:
                await socket.send_json({"type": "ping"})
            previous = current
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        subscribers.discard(queue)
        if receiver:
            receiver.cancel()
            with suppress(asyncio.CancelledError, WebSocketDisconnect):
                await receiver
