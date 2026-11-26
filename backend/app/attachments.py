import asyncio
import logging
import re
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import Activity, Attachment, utcnow


ATTACHMENT_URL = re.compile(r"/api/v1/attachments/([a-f0-9-]{36})/download")


def confirm_attachments(db, text, item, user, *, previous_text=""):
    """Claim uploads atomically with the content save, serialized against cleanup."""
    ids = set(ATTACHMENT_URL.findall(text))
    if not ids:
        return
    rows = list(db.scalars(select(Attachment).where(Attachment.id.in_(ids)).order_by(Attachment.id).with_for_update()))
    missing = ids - {row.id for row in rows}
    # Keep historical links editable after explicit removal, but reject new
    # references to missing/expired uploads or attachments from another ticket.
    if missing - set(ATTACHMENT_URL.findall(previous_text)):
        raise HTTPException(409, "An attachment has expired or is unavailable. Upload it again.")
    for row in rows:
        if row.pending:
            if (row.uploader_id != user.id or row.project_id != item.project_id
                    or row.item_id not in (None, item.id)):
                raise HTTPException(404, "Attachment not found")
            row.pending = False
            row.item_id = item.id
            db.add(Activity(item_id=item.id, author_id=user.id, message="uploaded " + row.filename))
        elif row.item_id != item.id:
            raise HTTPException(422, "Attachments must belong to this work item")


def cleanup_attachments():
    settings = get_settings()
    cutoff = utcnow() - timedelta(hours=24)
    with SessionLocal() as db:
        rows = list(db.scalars(select(Attachment).where(
            Attachment.pending.is_(True), Attachment.created_at < cutoff
        ).with_for_update(skip_locked=True)))
        for row in rows:
            (settings.attachment_dir / row.id).unlink(missing_ok=True)
            db.delete(row)
        db.commit()
        return len(rows)


async def cleanup_loop():
    while True:
        try:
            await asyncio.to_thread(cleanup_attachments)
        except Exception:
            logging.getLogger(__name__).exception("Temporary attachment cleanup failed")
        await asyncio.sleep(3600)


if __name__ == "__main__":
    print(f"Removed {cleanup_attachments()} temporary attachments.")
