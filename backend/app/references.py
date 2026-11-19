import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import String, cast, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Project, User, WorkItem
from app.profiles import avatar_url
from app.permissions import project_user_access, visible_item, visible_project
from app.security import organization_user

router = APIRouter(prefix="/api/v1/references", tags=["References"])


def context_project(db: Session, user: User, project_id: str | None):
    if not project_id:
        return None
    project = db.scalar(select(Project).where(Project.id == project_id, visible_project(user)))
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def user_reference(user: User):
    return {"kind": "user", "id": user.id, "name": user.name, "role": user.role, "is_bot": user.is_bot,
            "avatar_url": avatar_url(user), "href": f"/users/{user.id}"}


def ticket_reference(item: WorkItem, project: Project):
    return {"kind": "ticket", "id": item.id, "project_id": project.id, "number": item.number,
            "reference": f"{project.key}-{item.number}", "title": item.title,
             "status": item.status, "href": f"/{project.key}/{item.number}"}


def literal_search(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/users")
def suggest_users(q: str = Query("", max_length=200), project_id: str | None = None,
                  user: User = Depends(organization_user), db: Session = Depends(get_db)):
    project = context_project(db, user, project_id)
    query = select(User).where(User.active.is_(True), User.role.is_not(None))
    if project:
        query = query.where(project_user_access(project.id))
    term = literal_search(q.lstrip("@").strip())
    if term:
        query = query.where(User.name.ilike(f"%{term}%", escape="\\"))
    return [user_reference(person) for person in db.scalars(query.order_by(User.name, User.id).limit(10))]


@router.get("/users/{user_id}")
def get_user_reference(user_id: UUID, user: User = Depends(organization_user), db: Session = Depends(get_db)):
    target = db.get(User, str(user_id))
    if not target or not target.active or not target.role:
        raise HTTPException(404, "User not found")
    return user_reference(target)


@router.get("/tickets")
def suggest_tickets(q: str = Query("", max_length=200), project_id: str | None = None,
                    user: User = Depends(organization_user), db: Session = Depends(get_db)):
    project = context_project(db, user, project_id)
    query = select(WorkItem, Project).join(Project).where(visible_project(user), visible_item(user))
    term = q.lstrip("#").strip()
    full_reference = re.fullmatch(r"([a-zA-Z][a-zA-Z0-9]{1,9})-([0-9]+)", term)
    if (term.isascii() and term.isdigit()) or full_reference:
        number = int(full_reference[2] if full_reference else term)
        if not 1 <= number <= 2147483647:
            return []
        query = query.where(WorkItem.number == number)
        if full_reference:
            query = query.where(Project.key == full_reference[1].upper())
        elif project:
            query = query.where(Project.id == project.id)
    elif term:
        escaped = literal_search(term)
        reference = Project.key + "-" + cast(WorkItem.number, String)
        query = query.where(or_(WorkItem.title.ilike(f"%{escaped}%", escape="\\"),
                                reference.ilike(f"%{escaped}%", escape="\\")))
    if project:
        query = query.order_by((Project.id == project.id).desc())
    rows = db.execute(query.order_by(WorkItem.updated_at.desc(), WorkItem.id).limit(10))
    return [ticket_reference(item, project) for item, project in rows]


class ResolveReferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tickets: list[UUID] = Field(default_factory=list, max_length=50)
    users: list[UUID] = Field(default_factory=list, max_length=50)


@router.post("/resolve")
def resolve_references(payload: ResolveReferences, user: User = Depends(organization_user), db: Session = Depends(get_db)):
    # Store only stable reference IDs in Markdown. Resolve live labels and states
    # under the viewer's permissions instead of persisting private ticket titles.
    tickets = db.execute(select(WorkItem, Project).join(Project).where(
        WorkItem.id.in_([str(value) for value in payload.tickets]), visible_project(user), visible_item(user))) if payload.tickets else []
    people = db.scalars(select(User).where(User.id.in_([str(value) for value in payload.users]),
                                         User.active.is_(True), User.role.is_not(None))) if payload.users else []
    return {"tickets": [ticket_reference(item, project) for item, project in tickets],
            "users": [user_reference(person) for person in people]}
