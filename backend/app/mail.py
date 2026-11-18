"""Encrypted, database-backed email outboxes with bounded retries."""
import asyncio
import logging
import smtplib
import ssl
import time
from email.message import EmailMessage

from cryptography.fernet import Fernet
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import PasswordLink, User


def send_message(message):
    settings = get_settings()
    connection = smtplib.SMTP_SSL if settings.smtp_security == "tls" else smtplib.SMTP
    kwargs = {"context": ssl.create_default_context()} if settings.smtp_security == "tls" else {}
    with connection(settings.smtp_host, settings.smtp_port, timeout=15, **kwargs) as smtp:
        if settings.smtp_security == "starttls":
            smtp.starttls(context=ssl.create_default_context())
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


def deliver_pending():
    settings = get_settings()
    if not settings.password_enabled:
        return
    now = int(time.time())
    with SessionLocal() as db:
        # Lock users first, matching invitation/reset/consumption lock ordering.
        ids = db.scalars(select(PasswordLink.user_id).where(
            PasswordLink.delivery_status == "queued", PasswordLink.next_attempt_at <= now).distinct()).all()
        for user_id in ids:
            user = db.scalar(select(User).where(User.id == user_id).with_for_update(skip_locked=True))
            if not user:
                continue
            links = db.scalars(select(PasswordLink).where(PasswordLink.user_id == user_id,
                               PasswordLink.delivery_status == "queued", PasswordLink.next_attempt_at <= now)).all()
            for link in links:
                if link.used or link.expires_at <= now or not user.active:
                    link.delivery_status, link.encrypted_body = "canceled", None
                    continue
                link.attempts += 1
                try:
                    message = EmailMessage()
                    message["Subject"] = "Set your Issue Tracker password"
                    message["From"], message["To"] = settings.smtp_from, link.recipient
                    message.set_content(Fernet(settings.mail_encryption_key.encode()).decrypt(link.encrypted_body.encode()).decode())
                    send_message(message)
                    link.delivery_status, link.encrypted_body = "sent", None
                except Exception as exc:
                    logging.getLogger(__name__).warning("Password email failed for user %s (%s)", user_id, type(exc).__name__)
                    link.next_attempt_at = now + min(3600, 30 * 2 ** link.attempts)
                    if link.attempts >= 8:
                        link.delivery_status, link.encrypted_body = "failed", None
            db.commit()


async def mail_loop():
    from app.notifications import deliver_notifications

    while True:
        for deliver in (deliver_pending, deliver_notifications):
            try:
                await asyncio.to_thread(deliver)
            except Exception as exc:
                logging.getLogger(__name__).warning("Email outbox unavailable (%s)", type(exc).__name__)
        await asyncio.sleep(15)
