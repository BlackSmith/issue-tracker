import hashlib
import copy
import secrets
import time

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.db import SessionLocal, get_db
from app.models import ApiToken, BrowserSession, User

bearer_scheme = HTTPBearer(auto_error=False, scheme_name="ApiToken",
                          description="Tracker API token. Use read for queries or write for mutations; project permissions still apply.")


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class ServerSessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        settings = get_settings()
        if "authorization" in request.headers:
            # Bearer requests never inherit or mint a browser session.
            request.scope["session"] = {}
            request.state.rotate_session = False
            response = await call_next(request)
            response.headers["Cache-Control"] = "no-store"
            return response
        token = request.cookies.get(settings.session_cookie, "")
        old_hash = token_hash(token) if token else None
        with SessionLocal() as db:
            row = db.get(BrowserSession, old_hash) if old_hash else None
            valid = row is not None and row.expires_at > int(time.time())
            request.scope["session"] = dict(row.data) if valid else {}
            original = copy.deepcopy(request.scope["session"])
        request.state.rotate_session = False
        response = await call_next(request)
        data = request.scope["session"]
        response.headers["Cache-Control"] = "no-store"
        if (data and not valid) or data != original or request.state.rotate_session:
            rotate = not valid or request.state.rotate_session
            if rotate:
                token = secrets.token_urlsafe(48)
            with SessionLocal() as db:
                # Expired sessions are removed opportunistically, without a separate queue.
                db.execute(delete(BrowserSession).where(BrowserSession.expires_at <= int(time.time())))
                if rotate and old_hash:
                    db.execute(delete(BrowserSession).where(BrowserSession.token_hash == old_hash))
                if rotate:
                    db.add(BrowserSession(token_hash=token_hash(token), data=data,
                                          expires_at=int(time.time()) + settings.session_ttl))
                else:
                    # An in-flight request cannot resurrect a session revoked by logout.
                    db.execute(update(BrowserSession).where(BrowserSession.token_hash == old_hash)
                               .values(data=data))
                db.commit()
            if rotate:
                response.set_cookie(settings.session_cookie, token, httponly=True,
                                    secure=settings.cookie_secure, samesite="lax",
                                    max_age=settings.session_ttl, path="/")
        return response


def authentication_required(detail="Authentication required"):
    return HTTPException(401, detail, headers={"WWW-Authenticate": "Bearer"})


def resolve_user(request: Request, db: Session) -> User | None:
    if getattr(request.state, "authentication_checked", False):
        return request.state.authenticated_user
    request.state.api_token = None
    if "authorization" in request.headers:
        authorization = request.headers.get("authorization", "")
        scheme, _, secret = authorization.partition(" ")
        if (len(request.headers.getlist("authorization")) != 1 or scheme.lower() != "bearer"
                or not secret.startswith("itr_") or not 40 <= len(secret) <= 100):
            raise authentication_required("Invalid API token")
        token = db.scalar(select(ApiToken).where(ApiToken.secret_hash == token_hash(secret)))
        now = int(time.time())
        if not token or token.revoked_at is not None or token.expires_at <= now:
            raise authentication_required("Invalid or expired API token")
        user = db.get(User, token.user_id)
        if not user or not user.active or not user.role:
            raise authentication_required("Token owner is inactive or has no organization membership")
        read_only = request.method in {"GET", "HEAD", "OPTIONS"} or (
            request.method == "POST" and request.url.path == "/api/v1/references/resolve")
        required = "read" if read_only else "write"
        if required not in token.scopes:
            raise HTTPException(403, f"API token requires the {required} scope")
        if user.is_bot and request.url.path.startswith("/api/v1/users/me") and not read_only:
            raise HTTPException(403, "Bot profiles are managed by administrators")
        request.state.api_token = token
        token.last_used_at = now
        db.commit()
    else:
        user = db.get(User, request.session.get("user_id", ""))
        if user and (not user.active or user.is_bot):
            user = None
    request.state.authentication_checked = True
    request.state.authenticated_user = user
    return user


def maybe_user(request: Request, db: Session = Depends(get_db),
               _bearer: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> User | None:
    return resolve_user(request, db)


def current_user(user: User | None = Depends(maybe_user)) -> User:
    if not user:
        raise authentication_required()
    return user


def organization_user(user: User = Depends(current_user)) -> User:
    if not user.role:
        raise HTTPException(403, "Organization membership required")
    return user


def browser_user(request: Request, user: User = Depends(current_user)) -> User:
    if getattr(request.state, "api_token", None) is not None:
        raise HTTPException(403, "A browser session is required to manage credentials")
    return user


def browser_member(user: User = Depends(browser_user)) -> User:
    if not user.role:
        raise HTTPException(403, "Organization membership required")
    return user


def browser_administrator(user: User = Depends(browser_member)) -> User:
    if user.role != "administrator":
        raise HTTPException(403, "Administrator required")
    return user


def csrf(request: Request, db: Session = Depends(get_db)):
    if "authorization" in request.headers:
        # Only successfully authenticated scoped bearer requests bypass CSRF.
        resolve_user(request, db)
        return
    expected = request.session.get("csrf")
    actual = request.headers.get("x-csrf-token", "")
    if not expected or not secrets.compare_digest(expected, actual):
        raise HTTPException(403, "Invalid CSRF token")
    origin = request.headers.get("origin")
    settings = get_settings()
    if origin and origin not in {settings.app_base_url, settings.api_base_url}:
        raise HTTPException(403, "Invalid request origin")
