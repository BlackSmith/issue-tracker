"""Browser-only local credentials and administrator-controlled recovery."""
import logging
import secrets
import time
from typing import Literal

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import ExternalIdentity, LoginThrottle, PasswordCredential, PasswordLink, User, utcnow
from app.security import browser_administrator, browser_user, csrf, token_hash

router = APIRouter(prefix="/api/v1", tags=["Password authentication"])
hasher = PasswordHasher()
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))
logger = logging.getLogger(__name__)


def enabled():
    if not get_settings().password_enabled:
        raise HTTPException(404, "Password authentication is not configured")


def anonymous_browser(request: Request):
    if "authorization" in request.headers:
        raise HTTPException(403, "Use a browser session without an API token")


def establish_session(request: Request, user: User):
    request.session.clear()
    request.session.update(user_id=user.id, csrf=secrets.token_urlsafe(32), auth_version=user.auth_version)
    request.state.rotate_session = True


def verify_password(encoded, password):
    try:
        return hasher.verify(encoded or DUMMY_HASH, password) and bool(encoded)
    except (VerificationError, InvalidHashError):
        return False


def throttle(db: Session, key: str, limit: int):
    now = int(time.time())
    key = token_hash(key)
    # INSERT conflict handling also serializes the first concurrent attempts.
    try:
        with db.begin_nested():
            if not db.get(LoginThrottle, key):
                db.add(LoginThrottle(key=key, attempts=0, expires_at=now + 900))
                db.flush()
    except IntegrityError:
        pass
    row = db.scalar(select(LoginThrottle).where(LoginThrottle.key == key).with_for_update())
    if row.expires_at <= now:
        row.attempts, row.expires_at = 0, now + 900
    if row.attempts >= limit:
        db.commit()
        raise HTTPException(429, "Too many attempts. Please try again later.", headers={"Retry-After": str(max(1, row.expires_at - now))})
    row.attempts += 1
    db.execute(delete(LoginThrottle).where(LoginThrottle.expires_at < now - 86400))
    db.commit()


def queue_link(db: Session, user: User, credential: PasswordCredential, reset: bool):
    settings = get_settings()
    now = int(time.time())
    # Lock the user before calling this function to serialize reset/send/consumption.
    db.execute(update(PasswordLink).where(PasswordLink.user_id == user.id, PasswordLink.used.is_(False))
               .values(used=True, encrypted_body=None, delivery_status="superseded"))
    if reset:
        credential.password_hash = None
        user.auth_version += 1
    secret = secrets.token_urlsafe(48)
    ttl = settings.password_reset_ttl if reset else settings.invitation_ttl
    body = (f"Hello {user.name},\n\nYour administrator requested that you set your Issue Tracker password.\n\n"
            f"{settings.app_base_url.rstrip('/')}/?password_setup=1#token={secret}\n\n"
            f"This single-use link expires in {ttl // 60} minutes. If you did not expect this email, contact your administrator.\n")
    db.add(PasswordLink(secret_hash=token_hash(secret), user_id=user.id, recipient=credential.login_email,
                        encrypted_body=Fernet(settings.mail_encryption_key.encode()).encrypt(body.encode()).decode(),
                        expires_at=now + ttl, next_attempt_at=now))
    logger.info("Password %s queued for user %s", "reset" if reset else "invitation", user.id)


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)


class SetPasswordInput(BaseModel):
    token: str = Field(min_length=40, max_length=100)
    password: str = Field(min_length=12, max_length=128)


class ChangePasswordInput(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024)
    password: str = Field(min_length=12, max_length=128)


class CreateLocalUser(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    role: Literal["administrator", "member"] = "member"


class EmailInput(BaseModel):
    email: EmailStr


@router.post("/auth/password/login", dependencies=[Depends(enabled), Depends(anonymous_browser), Depends(csrf)])
def login(payload: LoginInput, request: Request, db: Session = Depends(get_db)):
    email = str(payload.email).casefold()
    throttle(db, "ip:" + (request.client.host if request.client else "unknown"), 100)
    throttle(db, "login:" + email, 10)
    credential = db.scalar(select(PasswordCredential).where(PasswordCredential.login_email == email))
    user = db.scalar(select(User).where(User.id == credential.user_id).with_for_update()) if credential else None
    # Re-read after the user lock, so an overlapping reset cannot admit the old password.
    if credential:
        db.refresh(credential)
    valid = verify_password(credential.password_hash if credential else None, payload.password)
    if not valid or not user or not user.active or user.is_bot or not user.role or credential.login_email != email:
        raise HTTPException(401, "Invalid email or password")
    if hasher.check_needs_rehash(credential.password_hash):
        credential.password_hash = hasher.hash(payload.password)
    user.last_login_at = utcnow()
    db.commit()
    establish_session(request, user)
    logger.info("Password sign-in succeeded for user %s", user.id)
    return {"ok": True}


@router.post("/auth/password/setup", dependencies=[Depends(enabled), Depends(anonymous_browser), Depends(csrf)])
def setup(payload: SetPasswordInput, request: Request, db: Session = Depends(get_db)):
    throttle(db, "setup:" + (request.client.host if request.client else "unknown"), 30)
    link = db.get(PasswordLink, token_hash(payload.token))
    if not link:
        raise HTTPException(400, "Invalid or expired password link")
    user = db.scalar(select(User).where(User.id == link.user_id).with_for_update())
    db.refresh(link)
    credential = db.get(PasswordCredential, link.user_id)
    if link.used or link.expires_at <= int(time.time()) or not user.active or user.is_bot or not credential:
        raise HTTPException(400, "Invalid or expired password link")
    credential.password_hash = hasher.hash(payload.password)
    user.auth_version += 1
    link.used, link.encrypted_body = True, None
    if link.delivery_status == "queued":
        link.delivery_status = "consumed"
    db.commit()
    logger.info("Password set for user %s", user.id)
    return {"ok": True}


@router.get("/auth/password/account")
def account(user: User = Depends(browser_user), db: Session = Depends(get_db)):
    credential = db.get(PasswordCredential, user.id)
    return {"enabled": get_settings().password_enabled, "login_email": credential.login_email if credential else None}


@router.post("/auth/password/change", dependencies=[Depends(enabled), Depends(csrf)])
def change(payload: ChangePasswordInput, request: Request, user: User = Depends(browser_user), db: Session = Depends(get_db)):
    throttle(db, "change:" + user.id, 10)
    user = db.scalar(select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True))
    credential = db.get(PasswordCredential, user.id)
    if not credential or not verify_password(credential.password_hash, payload.current_password):
        raise HTTPException(400, "Current password is incorrect")
    credential.password_hash = hasher.hash(payload.password)
    user.auth_version += 1
    db.execute(update(PasswordLink).where(PasswordLink.user_id == user.id).values(used=True, encrypted_body=None))
    db.commit()
    establish_session(request, user)
    logger.info("Password changed for user %s", user.id)
    return {"ok": True}


@router.post("/admin/users", dependencies=[Depends(enabled), Depends(csrf)])
def create(payload: CreateLocalUser, actor: User = Depends(browser_administrator), db: Session = Depends(get_db)):
    user = User(name=payload.name, email=str(payload.email), role=payload.role)
    db.add(user)
    db.flush()
    credential = PasswordCredential(user_id=user.id, login_email=str(payload.email).casefold())
    db.add(credential)
    try:
        db.flush()
        queue_link(db, user, credential, False)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A local account already uses this login email")
    logger.info("Local user %s created by %s", user.id, actor.id)
    return {"id": user.id}


def local_user(db, user_id):
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    credential = db.get(PasswordCredential, user_id)
    if not user or user.is_bot or not credential:
        raise HTTPException(404, "Local user not found")
    return user, credential


@router.post("/admin/users/{user_id}/password/{action}", dependencies=[Depends(enabled), Depends(csrf)])
def send(user_id: str, action: Literal["invite", "reset"], actor: User = Depends(browser_administrator), db: Session = Depends(get_db)):
    user, credential = local_user(db, user_id)
    if not user.active:
        raise HTTPException(409, "Enable the account before sending a password link")
    if action == "invite" and credential.password_hash:
        raise HTTPException(409, "Password already set; use Reset password")
    queue_link(db, user, credential, action == "reset")
    db.commit()
    logger.info("Password %s for user %s requested by %s", action, user.id, actor.id)
    return {"ok": True}


@router.put("/admin/users/{user_id}/login-email", dependencies=[Depends(enabled), Depends(csrf)])
def email(user_id: str, payload: EmailInput, actor: User = Depends(browser_administrator), db: Session = Depends(get_db)):
    user, credential = local_user(db, user_id)
    if not user.active:
        raise HTTPException(409, "Enable the account before changing the login email")
    credential.login_email = str(payload.email).casefold()
    try:
        db.flush()
        queue_link(db, user, credential, True)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A local account already uses this login email")
    logger.info("Login email changed for user %s by %s", user.id, actor.id)
    return {"ok": True}


def auth_details(db: Session, user: User):
    credential = db.get(PasswordCredential, user.id)
    identities = db.scalars(select(ExternalIdentity).where(ExternalIdentity.user_id == user.id)).all()
    link = db.scalar(select(PasswordLink).where(PasswordLink.user_id == user.id).order_by(PasswordLink.created_at.desc()))
    return {"login_method": "password" if credential else ("facebook" if identities and identities[0].issuer.startswith("https://www.facebook.com/") else "oidc"),
            "login_email": credential.login_email if credential else None,
            "password_set": bool(credential and credential.password_hash),
            "mail_status": ("expired" if not link.used and link.expires_at <= int(time.time()) else link.delivery_status) if link else None}
