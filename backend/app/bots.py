import time
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ApiToken, Project, ProjectMember, User
from app.profiles import avatar_url, read_avatar
from app.security import browser_administrator, csrf
from app.tokens import TokenCreate, create_token, list_tokens, revoke_token

router = APIRouter(prefix="/api/v1/bots", tags=["Bot accounts"])


class BotCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    role: Literal["reader", "member"] = "reader"

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Bot name cannot be blank")
        return value.strip()


class BotUpdate(BotCreate):
    active: StrictBool


class BotProjectAccess(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["reader", "member"]


def bot_json(bot: User):
    return {"id": bot.id, "name": bot.name, "role": bot.role, "active": bot.active, "is_bot": True,
            "avatar_url": avatar_url(bot)}


def get_bot(db: Session, bot_id: str, lock=False):
    query = select(User).where(User.id == bot_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    bot = db.scalar(query)
    if not bot or not bot.is_bot:
        raise HTTPException(404, "Bot account not found")
    return bot


@router.get("")
def bots(user: User = Depends(browser_administrator), db: Session = Depends(get_db)):
    return [bot_json(bot) for bot in db.scalars(select(User).where(User.is_bot.is_(True)).order_by(User.name, User.id))]


@router.post("", status_code=201, dependencies=[Depends(csrf)])
def create_bot(payload: BotCreate, user: User = Depends(browser_administrator), db: Session = Depends(get_db)):
    bot = User(name=payload.name, email="", role=payload.role, is_bot=True)
    db.add(bot)
    db.commit()
    return bot_json(bot)


@router.put("/{bot_id}", dependencies=[Depends(csrf)])
def edit_bot(bot_id: str, payload: BotUpdate, user: User = Depends(browser_administrator), db: Session = Depends(get_db)):
    bot = get_bot(db, bot_id, lock=True)
    bot.name, bot.role, bot.active = payload.name, payload.role, payload.active
    if not payload.active:
        db.execute(update(ApiToken).where(ApiToken.user_id == bot.id, ApiToken.revoked_at.is_(None))
                   .values(revoked_at=int(time.time())))
    db.commit()
    return bot_json(bot)


@router.put("/{bot_id}/avatar", dependencies=[Depends(csrf)])
async def upload_bot_avatar(bot_id: str, file: UploadFile = File(),
                            user: User = Depends(browser_administrator), db: Session = Depends(get_db)):
    bot = get_bot(db, bot_id)
    bot.avatar = await read_avatar(file)
    db.commit()
    return bot_json(bot)


@router.delete("/{bot_id}/avatar", dependencies=[Depends(csrf)])
def delete_bot_avatar(bot_id: str, user: User = Depends(browser_administrator), db: Session = Depends(get_db)):
    bot = get_bot(db, bot_id)
    bot.avatar = None
    db.commit()
    return bot_json(bot)


@router.get("/{bot_id}/projects")
def bot_projects(bot_id: str, user: User = Depends(browser_administrator), db: Session = Depends(get_db)):
    bot = get_bot(db, bot_id)
    rows = db.execute(select(Project, ProjectMember).join(ProjectMember).where(ProjectMember.user_id == bot.id).order_by(Project.name))
    return [{"project_id": project.id, "name": project.name, "key": project.key, "slug": project.slug,
             "role": member.role, "effective_role": "reader" if bot.role == "reader" else member.role}
            for project, member in rows]


@router.put("/{bot_id}/projects/{project_id}", dependencies=[Depends(csrf)])
def grant_project(bot_id: str, project_id: str, payload: BotProjectAccess,
                  user: User = Depends(browser_administrator), db: Session = Depends(get_db)):
    bot = get_bot(db, bot_id)
    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    if bot.role == "reader" and payload.role == "member":
        raise HTTPException(403, "A read-only bot cannot receive project write access")
    db.merge(ProjectMember(project_id=project_id, user_id=bot.id, role=payload.role))
    db.commit()
    return {"ok": True}


@router.delete("/{bot_id}/projects/{project_id}", dependencies=[Depends(csrf)])
def remove_project(bot_id: str, project_id: str, user: User = Depends(browser_administrator), db: Session = Depends(get_db)):
    bot = get_bot(db, bot_id)
    db.execute(delete(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == bot.id))
    db.commit()
    return {"ok": True}


@router.get("/{bot_id}/tokens")
def bot_tokens(bot_id: str, user: User = Depends(browser_administrator), db: Session = Depends(get_db)):
    return list_tokens(db, get_bot(db, bot_id))


@router.post("/{bot_id}/tokens", status_code=201, dependencies=[Depends(csrf)])
def issue_bot_token(bot_id: str, payload: TokenCreate, user: User = Depends(browser_administrator), db: Session = Depends(get_db)):
    return create_token(db, get_bot(db, bot_id, lock=True), user, payload)


@router.delete("/{bot_id}/tokens/{token_id}", dependencies=[Depends(csrf)])
def revoke_bot_token(bot_id: str, token_id: str, user: User = Depends(browser_administrator), db: Session = Depends(get_db)):
    return revoke_token(db, get_bot(db, bot_id), token_id)
