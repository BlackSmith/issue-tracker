import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ApiToken, User
from app.security import browser_member, csrf, token_hash

router = APIRouter(prefix="/api/v1/tokens", tags=["API tokens"])


class TokenCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    scopes: list[Literal["read", "write"]] = Field(default_factory=lambda: ["read"], min_length=1, max_length=2)
    expires_at: AwareDatetime = Field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=30))

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Token name cannot be blank")
        return value.strip()

    @field_validator("scopes")
    @classmethod
    def normalize_scopes(cls, value):
        return ["read", "write"] if "write" in value else ["read"]

    @field_validator("expires_at")
    @classmethod
    def valid_expiry(cls, value):
        now = datetime.now(timezone.utc)
        if value <= now or value > now + timedelta(days=365):
            raise ValueError("Expiration must be in the future and within one year")
        return value


def token_json(token: ApiToken):
    def iso(value):
        return datetime.fromtimestamp(value, timezone.utc) if value is not None else None
    status = "revoked" if token.revoked_at is not None else "expired" if token.expires_at <= int(time.time()) else "active"
    return {"id": token.id, "user_id": token.user_id, "name": token.name,
            "prefix": token.token_prefix, "scopes": token.scopes, "status": status,
            "created_at": iso(token.created_at), "expires_at": iso(token.expires_at),
            "last_used_at": iso(token.last_used_at), "revoked_at": iso(token.revoked_at)}


def create_token(db: Session, owner: User, issuer: User, payload: TokenCreate):
    if not owner.active or not owner.role:
        raise HTTPException(409, "The token owner must be an active organization member")
    if owner.role == "reader" and "write" in payload.scopes:
        raise HTTPException(403, "Read-only accounts can only create read tokens")
    secret = "itr_" + secrets.token_urlsafe(40)
    token = ApiToken(user_id=owner.id, created_by_id=issuer.id, name=payload.name,
                     scopes=payload.scopes, expires_at=int(payload.expires_at.timestamp()),
                     token_prefix=secret[:12], secret_hash=token_hash(secret))
    db.add(token)
    db.commit()
    return {**token_json(token), "token": secret}


def list_tokens(db: Session, owner: User):
    return [token_json(token) for token in db.scalars(select(ApiToken).where(
        ApiToken.user_id == owner.id).order_by(ApiToken.created_at.desc(), ApiToken.id))]


def revoke_token(db: Session, owner: User, token_id: str):
    token = db.scalar(select(ApiToken).where(ApiToken.id == token_id, ApiToken.user_id == owner.id))
    if not token:
        raise HTTPException(404, "API token not found")
    if token.revoked_at is None:
        token.revoked_at = int(time.time())
        db.commit()
    return token_json(token)


@router.get("")
def my_tokens(user: User = Depends(browser_member), db: Session = Depends(get_db)):
    return list_tokens(db, user)


@router.post("", status_code=201, dependencies=[Depends(csrf)])
def issue_personal_token(payload: TokenCreate, user: User = Depends(browser_member), db: Session = Depends(get_db)):
    return create_token(db, user, user, payload)


@router.delete("/{token_id}", dependencies=[Depends(csrf)])
def revoke_personal_token(token_id: str, user: User = Depends(browser_member), db: Session = Depends(get_db)):
    return revoke_token(db, user, token_id)
