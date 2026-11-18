"""Transactional ticket notifications, with permission checks at queue and send time."""
import json
import logging
import time
from email.message import EmailMessage
from uuid import UUID

from cryptography.fernet import Fernet
from markdown_it import MarkdownIt
from sqlalchemy import exists, or_, select

from app.config import get_settings
from app.db import SessionLocal
from app.models import Activity, Comment, Project, ProjectMember, TicketNotification, User, WorkItem

parser = MarkdownIt("commonmark")


def mentioned_users(text):
    result = set()
    for token in parser.parse(text):
        for child in token.children or []:
            if child.type != "link_open":
                continue
            href = child.attrGet("href") or ""
            if href.startswith("/users/"):
                try:
                    result.add(str(UUID(href.removeprefix("/users/"))))
                except ValueError:
                    pass
    return result


def eligible_users(project_id):
    return select(User).where(
        User.active.is_(True), User.is_bot.is_(False), User.role.in_(["administrator", "member"]),
        User.email != "",
        or_(User.role == "administrator", exists().where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == User.id)))


def enqueue_notification(db, item, actor, summary, *, created=False, previous_assignee_id=None):
    settings = get_settings()
    if not settings.notifications_enabled:
        return
    # Flush the comment/activity and relationship changes before finding participants.
    db.flush()
    ids = {item.author_id, item.assignee_id, previous_assignee_id}
    ids.update(db.scalars(select(Comment.author_id).where(Comment.item_id == item.id)))
    ids.update(db.scalars(select(Activity.author_id).where(Activity.item_id == item.id)))
    ids.update(mentioned_users(item.description))
    for body in db.scalars(select(Comment.body).where(Comment.item_id == item.id)):
        ids.update(mentioned_users(body))
    if created:
        ids.update(db.scalars(select(ProjectMember.user_id).where(
            ProjectMember.project_id == item.project_id, ProjectMember.role == "owner")))
        ids.update(db.scalars(select(User.id).where(User.role == "administrator")))
    project = db.get(Project, item.project_id)
    reference = f"{project.key}-{item.number}"
    subject = f"[{reference}] {'New ticket' if created else 'Ticket updated'}: {item.title}"
    # Keep headers single-line even when a title contains line breaks.
    subject = " ".join(subject.splitlines())
    body = (f"{reference}: {item.title}\nProject: {project.name}\n\n{actor.name} {summary}.\n\n"
            f"Open ticket: {settings.app_base_url.rstrip('/')}/{project.key}/{item.number}\n")
    encrypted = Fernet(settings.mail_encryption_key.encode()).encrypt(
        json.dumps({"subject": subject, "body": body}).encode()).decode()
    for person in db.scalars(eligible_users(item.project_id).where(User.id.in_(ids - {None}))):
        db.add(TicketNotification(item_id=item.id, user_id=person.id, encrypted_body=encrypted,
                                 next_attempt_at=int(time.time())))


def deliver_notifications():
    from app.mail import send_message

    settings = get_settings()
    if not settings.notifications_enabled:
        return
    now = int(time.time())
    with SessionLocal() as db:
        # Commit each delivery separately; competing API workers skip claimed rows.
        while row := db.scalar(select(TicketNotification).where(
                TicketNotification.delivery_status == "queued", TicketNotification.next_attempt_at <= now)
                .order_by(TicketNotification.next_attempt_at, TicketNotification.id)
                .with_for_update(skip_locked=True).limit(1)):
            item = db.get(WorkItem, row.item_id)
            user = db.scalar(eligible_users(item.project_id).where(User.id == row.user_id)) if item else None
            if not user:
                row.delivery_status, row.encrypted_body = "canceled", None
            else:
                row.attempts += 1
                try:
                    payload = json.loads(Fernet(settings.mail_encryption_key.encode()).decrypt(row.encrypted_body.encode()))
                    message = EmailMessage()
                    message["Subject"] = payload["subject"]
                    message["From"], message["To"] = settings.smtp_from, user.email
                    message["Message-ID"] = f"<{row.id}@issue-tracker>"
                    message.set_content(payload["body"])
                    send_message(message)
                    row.delivery_status, row.encrypted_body = "sent", None
                except Exception as exc:
                    logging.getLogger(__name__).warning("Ticket email failed for notification %s (%s)", row.id, type(exc).__name__)
                    row.next_attempt_at = now + min(3600, 30 * 2 ** row.attempts)
                    if row.attempts >= 8:
                        row.delivery_status, row.encrypted_body = "failed", None
            db.commit()
