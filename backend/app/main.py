import asyncio
import json
import logging
import mimetypes
import secrets
from contextlib import asynccontextmanager, suppress
from datetime import timezone
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import Field
from sqlalchemy import and_, case, exists, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.attachments import cleanup_loop, confirm_attachments
from app.checklists import content_version, set_checklist_item
from app.db import get_db
from app.labels import available_labels, label_json, lock_catalog, validate_labels
from app.models import (Activity, Attachment, Comment, ExternalIdentity, Project,
                        ProjectMember, User, WorkItem, Label, new_id, utcnow)
from app.providers import OIDCProvider
from app.profiles import avatar_url, profile_json, router as profile_router
from app.references import router as references_router
from app.tokens import router as tokens_router
from app.bots import router as bots_router
from app.schemas import ApplicationUserUpdate, ChecklistUpdate, CommentCreate, ItemCreate, ItemUpdate, ItemType, LabelCreate, MemberCreate, Priority, ProjectCreate, ProjectUpdate, Status
from app.security import ServerSessionMiddleware, browser_user, csrf, maybe_user, organization_user

settings = get_settings()


@asynccontextmanager
async def lifespan(app):
    app.state.provider = OIDCProvider(settings) if settings.oidc_issuer and settings.oidc_client_id else None
    cleanup = asyncio.create_task(cleanup_loop())
    try:
        yield
    finally:
        cleanup.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup


app = FastAPI(title="Issue Tracker API", version="0.1.0", lifespan=lifespan,
              docs_url="/api/v1/docs", openapi_url="/api/v1/openapi.json")
app.add_middleware(ServerSessionMiddleware)
app.include_router(profile_router)
app.include_router(references_router)
app.include_router(tokens_router)
app.include_router(bots_router)
api = "/api/v1"


def can_manage_project(user, member):
    return not user.is_bot and (user.role == "administrator" or (
        user.role == "member" and member is not None and member.role == "owner"))


def project_access(db: Session, project_id: str, user: User, write=False, manage=False) -> Project:
    project = db.get(Project, project_id)
    member = db.get(ProjectMember, (project_id, user.id))
    if not project or ((user.role != "administrator" or user.is_bot) and not member):
        raise HTTPException(404, "Project not found")
    effective = "owner" if user.role == "administrator" and not user.is_bot else member.role
    if write and effective not in {"owner", "reporter"}:
        raise HTTPException(403, "Read-only access")
    if manage and not can_manage_project(user, member):
        raise HTTPException(403, "Project owner required")
    return project


def item_access(db, item_id, user, write=False):
    item = db.get(WorkItem, item_id)
    if not item:
        raise HTTPException(404, "Work item not found")
    project = project_access(db, item.project_id, user, write)
    return item, project


def project_json(project, user, db):
    member = db.get(ProjectMember, (project.id, user.id))
    can_write = (user.role == "administrator" and not user.is_bot) or (member is not None and member.role in {"owner", "reporter"})
    return {"id": project.id, "key": project.key, "slug": project.key, "legacy_slug": project.slug if project.slug != project.key else None, "name": project.name,
            "description": project.description, "visibility": project.visibility, "can_write": can_write,
            "can_manage": can_manage_project(user, member)}


def item_json(item, project):
    return {"id": item.id, "project_id": item.project_id, "project_slug": project.key,
            "number": item.number, "web_url": f"/{project.key}/{item.number}", "reference": f"{project.key}-{item.number}",
             "description_version": content_version(item.description),
            "assignee_id": item.assignee_id, "assignee": assignee_json(item.assignee) if item.assignee else None,
             **{key: getattr(item, key) for key in ("title", "description", "type", "status", "priority", "labels", "due_date", "created_at", "updated_at")}}


def assignee_json(user):
    return {"id": user.id, "name": user.name, "avatar_url": avatar_url(user), "is_bot": user.is_bot}


def assignable_users(project):
    return (select(User).outerjoin(ProjectMember, and_(ProjectMember.user_id == User.id,
                                                      ProjectMember.project_id == project.id))
            .where(User.active.is_(True), User.role.in_(["administrator", "member"]),
                   or_(and_(User.role == "administrator", User.is_bot.is_(False)),
                        ProjectMember.role.in_(["owner", "reporter"]))))


def resolve_assignee(db, project, user_id):
    if user_id is None:
        return None
    target = db.scalar(assignable_users(project).where(User.id == user_id))
    if not target:
        raise HTTPException(422, "Choose an active member with write access to this project")
    return target


@app.get(api + "/health", tags=["System"])
def health():
    return {"status": "ok"}


@app.get(api + "/auth/providers", tags=["Authentication"])
def providers():
    return [{"id": "oidc", "name": settings.oidc_name, "url": api + "/auth/oidc/login"}] if settings.oidc_issuer and settings.oidc_client_id else []


@app.get(api + "/auth/me", tags=["Authentication"])
def me(request: Request, user: User | None = Depends(maybe_user)):
    token = getattr(request.state, "api_token", None)
    if not token:
        request.session.setdefault("csrf", secrets.token_urlsafe(32))
    return {"user": profile_json(user) if user and user.active else None,
            "csrf_token": request.session.get("csrf") if not token else None,
            "auth_method": "token" if token else "session", "token_scopes": token.scopes if token else None}


@app.get(api + "/auth/oidc/login", tags=["Authentication"])
async def login(request: Request):
    if "authorization" in request.headers:
        raise HTTPException(403, "Use the browser login flow without an API token")
    if not app.state.provider:
        raise HTTPException(404, "Provider is not configured")
    return await app.state.provider.authorize(request)


@app.get(api + "/auth/oidc/callback", tags=["Authentication"])
async def callback(request: Request, db: Session = Depends(get_db)):
    if "authorization" in request.headers:
        raise HTTPException(403, "API tokens cannot create browser sessions")
    if not app.state.provider:
        raise HTTPException(404, "Provider is not configured")
    try:
        profile = await app.state.provider.identity(request)
    except Exception as exc:
        logging.getLogger(__name__).warning("OIDC authentication rejected (%s)", type(exc).__name__)
        return RedirectResponse(settings.app_base_url + "/?auth_error=1", status_code=303)
    identity = db.scalar(select(ExternalIdentity).where(ExternalIdentity.issuer == profile.issuer,
                                                       ExternalIdentity.subject == profile.subject))
    if identity:
        user = db.get(User, identity.user_id)
    else:
        user = User(name=profile.name, email=profile.email, role=None)
        db.add(user)
        db.flush()
        db.add(ExternalIdentity(user_id=user.id, issuer=profile.issuer, subject=profile.subject))
        db.commit()
    if not user.active:
        raise HTTPException(403, "Account disabled")
    if user.is_bot:
        raise HTTPException(403, "Bot accounts cannot sign in through OIDC")
    user.last_login_at = utcnow()
    db.commit()
    request.session.clear()
    request.session.update(user_id=user.id, csrf=secrets.token_urlsafe(32))
    request.state.rotate_session = True
    return RedirectResponse(settings.app_base_url, status_code=303)


@app.post(api + "/auth/logout", dependencies=[Depends(csrf)], tags=["Authentication"])
def logout(request: Request, user: User = Depends(browser_user)):
    request.session.clear()
    request.session["csrf"] = secrets.token_urlsafe(32)
    request.state.rotate_session = True
    return {"ok": True}


@app.get(api + "/projects", tags=["Projects"])
def projects(user: User = Depends(organization_user), db: Session = Depends(get_db)):
    query = select(Project).order_by(Project.name)
    if user.is_bot or user.role != "administrator":
        query = query.where(exists().where(ProjectMember.project_id == Project.id, ProjectMember.user_id == user.id))
    return [project_json(p, user, db) for p in db.scalars(query)]


@app.post(api + "/projects", status_code=201, dependencies=[Depends(csrf)], tags=["Projects"])
def create_project(payload: ProjectCreate, user: User = Depends(organization_user), db: Session = Depends(get_db)):
    if user.role != "administrator":
        raise HTTPException(403, "Administrator required")
    project = Project(**payload.model_dump(exclude={"slug"}), slug=payload.key)
    db.add(project)
    try:
        db.flush()
        db.add(ProjectMember(project_id=project.id, user_id=user.id, role="owner"))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Project key or URL slug already exists")
    return project_json(project, user, db)


@app.put(api + "/projects/{project_id}", dependencies=[Depends(csrf)], tags=["Projects"])
def update_project(project_id: str, payload: ProjectUpdate, user: User = Depends(organization_user), db: Session = Depends(get_db)):
    project = project_access(db, project_id, user, manage=True)
    for field, value in payload.model_dump().items():
        setattr(project, field, value)
    db.commit()
    return project_json(project, user, db)


@app.get(api + "/users", tags=["Projects"])
@app.get(api + "/projects/{project_id}/member-candidates", tags=["Projects"])
def users(project_id: str | None = None, user: User = Depends(organization_user), db: Session = Depends(get_db)):
    if project_id:
        project_access(db, project_id, user, manage=True)
    elif user.role != "administrator":
        raise HTTPException(403, "Administrator required")
    return [{"id": u.id, "name": u.name, "email": u.email, "role": u.role, "is_bot": u.is_bot} for u in db.scalars(select(User).where(User.active.is_(True)).order_by(User.name))]


@app.get(api + "/admin/users", tags=["Application settings"])
def application_users(user: User = Depends(organization_user), db: Session = Depends(get_db)):
    if user.role != "administrator" or user.is_bot:
        raise HTTPException(403, "Application administrator required")
    return [{"id": target.id, "name": target.name, "email": target.email,
             "role": target.role, "active": target.active, "avatar_url": avatar_url(target) if target.active and target.role else None,
             "last_login_at": target.last_login_at.replace(tzinfo=target.last_login_at.tzinfo or timezone.utc).isoformat() if target.last_login_at else None}
            for target in db.scalars(select(User).where(User.is_bot.is_(False)).order_by(User.name, User.id))]


@app.get(api + "/projects/{project_id}/members", tags=["Projects"])
def project_members(project_id: str, user: User = Depends(organization_user), db: Session = Depends(get_db)):
    project_access(db, project_id, user, manage=True)
    rows = db.execute(select(ProjectMember, User).select_from(User).outerjoin(ProjectMember, and_(
        User.id == ProjectMember.user_id, ProjectMember.project_id == project_id))
        .where(or_(ProjectMember.user_id.is_not(None), and_(User.role == "administrator", User.is_bot.is_(False))))
        .order_by(User.name, User.id))
    return [{"user_id": target.id, "name": target.name, "email": target.email, "avatar_url": avatar_url(target),
             "role": "owner" if target.role == "administrator" and not target.is_bot else member.role,
             "inherited": target.role == "administrator" and not target.is_bot, "organization_role": target.role,
               "active": target.active, "is_bot": target.is_bot} for member, target in rows]


@app.put(api + "/admin/users/{user_id}", dependencies=[Depends(csrf)], tags=["Application settings"])
def update_application_user(user_id: str, payload: ApplicationUserUpdate,
                            user: User = Depends(organization_user), db: Session = Depends(get_db)):
    if user.role != "administrator" or user.is_bot:
        raise HTTPException(403, "Application administrator required")
    # Serialize administrator changes to preserve at least one active admin.
    db.scalars(select(User).where(User.role == "administrator").order_by(User.id).with_for_update()).all()
    target = db.get(User, user_id)
    if not target or target.is_bot:
        raise HTTPException(404, "User not found")
    if target.role == "administrator" and target.active and (payload.role != "administrator" or not payload.active):
        others = db.scalar(select(func.count()).select_from(User).where(
            User.role == "administrator", User.active.is_(True), User.is_bot.is_(False), User.id != target.id))
        if not others:
            raise HTTPException(409, "At least one active application administrator is required")
    target.role, target.active = payload.role, payload.active
    db.commit()
    return {"ok": True}


@app.get(api + "/projects/{project_id}/assignees", tags=["Work items"])
def project_assignees(project_id: str, user: User = Depends(organization_user), db: Session = Depends(get_db)):
    project = project_access(db, project_id, user, True)
    return [assignee_json(target) for target in db.scalars(assignable_users(project).order_by(User.name, User.id))]


@app.delete(api + "/projects/{project_id}/members/{user_id}", dependencies=[Depends(csrf)], tags=["Projects"])
def remove_member(project_id: str, user_id: str, user: User = Depends(organization_user), db: Session = Depends(get_db)):
    project_access(db, project_id, user, manage=True)
    target = db.get(User, user_id)
    if target and target.role == "administrator" and not target.is_bot:
        raise HTTPException(403, "Application administrators are permanent project owners")
    if target and target.is_bot and user.role != "administrator":
        raise HTTPException(403, "Bot access is managed by application administrators")
    member = db.get(ProjectMember, (project_id, user_id))
    if not member:
        raise HTTPException(404, "Project member not found")
    db.delete(member)
    db.commit()
    return {"ok": True}


@app.put(api + "/projects/{project_id}/members", dependencies=[Depends(csrf)], tags=["Projects"])
def set_member(project_id: str, payload: MemberCreate, user: User = Depends(organization_user), db: Session = Depends(get_db)):
    project_access(db, project_id, user, manage=True)
    target = db.get(User, payload.user_id)
    if not target or not target.active or not target.role:
        raise HTTPException(404, "Organization member not found")
    if target.role == "administrator" and not target.is_bot:
        raise HTTPException(403, "Application administrators are permanent project owners")
    if target.is_bot and (not user.role == "administrator" or payload.role == "owner"):
        raise HTTPException(403, "Bot access is managed by application administrators; bots cannot be owners")
    db.merge(ProjectMember(project_id=project_id, **payload.model_dump()))
    db.commit()
    return {"ok": True}


def label_scope(db, user, project_id=None, write=False):
    if project_id:
        project_access(db, project_id, user, manage=write)
    elif write and user.role != "administrator":
        raise HTTPException(403, "Administrator required")


@app.get(api + "/organization/labels", tags=["Labels"])
def organization_labels(user: User = Depends(organization_user), db: Session = Depends(get_db)):
    if user.role != "administrator":
        raise HTTPException(403, "Application administrator required")
    return [label_json(label) for label in db.scalars(select(Label).where(Label.project_id.is_(None)).order_by(Label.name))]


@app.get(api + "/projects/{project_id}/labels", tags=["Labels"])
def project_labels(project_id: str, user: User = Depends(organization_user), db: Session = Depends(get_db)):
    label_scope(db, user, project_id)
    return [label_json(label) for label in available_labels(db, project_id)]


def save_label(db, user, payload, project_id=None, label_id=None):
    label_scope(db, user, project_id, True)
    lock_catalog(db)
    label = db.get(Label, label_id) if label_id else None
    if label_id and (not label or label.project_id != project_id):
        raise HTTPException(404, "Label not found")
    conflicts = select(Label).where(Label.name == payload.name)
    if project_id:
        conflicts = conflicts.where(or_(Label.project_id.is_(None), Label.project_id == project_id))
    if label_id:
        conflicts = conflicts.where(Label.id != label_id)
    if db.scalar(conflicts):
        raise HTTPException(409, "A label with this name already exists in this scope")
    if label and label.name != payload.name:
        query = select(WorkItem).order_by(WorkItem.id).with_for_update()
        if project_id:
            query = query.where(WorkItem.project_id == project_id)
        for item in db.scalars(query):
            if label.name in item.labels:
                item.labels = [payload.name if name == label.name else name for name in item.labels]
    if label is None:
        label = Label(project_id=project_id)
        db.add(label)
    for field, value in payload.model_dump().items():
        setattr(label, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A label with this name already exists in this scope")
    return label_json(label)


@app.post(api + "/organization/labels", status_code=201, dependencies=[Depends(csrf)], tags=["Labels"])
@app.post(api + "/projects/{project_id}/labels", status_code=201, dependencies=[Depends(csrf)], tags=["Labels"])
def create_label(payload: LabelCreate, project_id: str | None = None, user: User = Depends(organization_user), db: Session = Depends(get_db)):
    return save_label(db, user, payload, project_id)


@app.put(api + "/organization/labels/{label_id}", dependencies=[Depends(csrf)], tags=["Labels"])
@app.put(api + "/projects/{project_id}/labels/{label_id}", dependencies=[Depends(csrf)], tags=["Labels"])
def edit_label(label_id: str, payload: LabelCreate, project_id: str | None = None, user: User = Depends(organization_user), db: Session = Depends(get_db)):
    return save_label(db, user, payload, project_id, label_id)


@app.delete(api + "/organization/labels/{label_id}", dependencies=[Depends(csrf)], tags=["Labels"])
@app.delete(api + "/projects/{project_id}/labels/{label_id}", dependencies=[Depends(csrf)], tags=["Labels"])
def delete_label(label_id: str, project_id: str | None = None, user: User = Depends(organization_user), db: Session = Depends(get_db)):
    label_scope(db, user, project_id, True)
    lock_catalog(db)
    label = db.get(Label, label_id)
    if not label or label.project_id != project_id:
        raise HTTPException(404, "Label not found")
    query = select(WorkItem)
    if project_id:
        query = query.where(WorkItem.project_id == project_id)
    if any(label.name in item.labels for item in db.scalars(query)):
        raise HTTPException(409, "Remove this label from work items before deleting it")
    db.delete(label)
    db.commit()
    return {"ok": True}


@app.get(api + "/projects/{project_id}/item-assignees", tags=["Work items"])
def item_assignees(project_id: str, user: User = Depends(organization_user), db: Session = Depends(get_db)):
    project_access(db, project_id, user)
    assigned = select(WorkItem.assignee_id).where(WorkItem.project_id == project_id)
    return [assignee_json(person) for person in db.scalars(
        select(User).where(User.id.in_(assigned)).order_by(User.name, User.id))]


@app.get(api + "/projects/{project_id}/items", tags=["Work items"])
def items(project_id: str, q: str = Query("", max_length=200), status: list[Status] | None = Query(None, max_length=100),
          label: list[Annotated[str, Field(max_length=50)]] | None = Query(None, max_length=100),
          priority: list[Priority] | None = Query(None, max_length=100),
          type: list[ItemType] | None = Query(None, max_length=100),
          assignee: list[UUID | Literal["me", "none"]] | None = Query(None, max_length=100),
          sort: str = Query("updated", pattern="^(updated|created|title|priority|due_date)$"),
          direction: Literal["asc", "desc"] | None = Query(None),
          page: int = Query(1, ge=1), per_page: int = Query(25, ge=1, le=100),
          user: User = Depends(organization_user), db: Session = Depends(get_db)):
    project = project_access(db, project_id, user)
    query = select(WorkItem).where(WorkItem.project_id == project_id)
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(or_(WorkItem.title.ilike(f"%{escaped}%", escape="\\"), WorkItem.description.ilike(f"%{escaped}%", escape="\\")))
    if status:
        query = query.where(WorkItem.status.in_(status))
    if priority:
        query = query.where(WorkItem.priority.in_(priority))
    if type:
        query = query.where(WorkItem.type.in_(type))
    if assignee:
        ids = [user.id if value == "me" else str(value) for value in assignee if value != "none"]
        conditions = [WorkItem.assignee_id.in_(ids)] if ids else []
        if "none" in assignee:
            conditions.append(WorkItem.assignee_id.is_(None))
        query = query.where(or_(*conditions))
    if label:
        # Match any selected label without duplicating items in counts/pagination.
        from sqlalchemy import cast
        from sqlalchemy.dialects.postgresql import JSONB
        query = query.where(or_(*(cast(WorkItem.labels, JSONB).contains([name]) for name in set(label))))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    column = {"updated": WorkItem.updated_at, "created": WorkItem.created_at, "title": WorkItem.title,
              "priority": case({"Low": 0, "Medium": 1, "High": 2, "Urgent": 3}, value=WorkItem.priority),
              "due_date": WorkItem.due_date}[sort]
    direction = direction or ("asc" if sort in {"title", "due_date"} else "desc")
    order = (column.asc() if direction == "asc" else column.desc()).nulls_last()
    rows = db.scalars(query.order_by(order, WorkItem.id).offset((page - 1) * per_page).limit(per_page))
    return {"items": [item_json(i, project) for i in rows], "total": total, "page": page, "per_page": per_page}


@app.post(api + "/projects/{project_id}/items", status_code=201, dependencies=[Depends(csrf)], tags=["Work items"])
def create_item(project_id: str, payload: ItemCreate, user: User = Depends(organization_user), db: Session = Depends(get_db)):
    project = project_access(db, project_id, user, True)
    lock_catalog(db)
    validate_labels(db, project_id, payload.labels)
    assignee = resolve_assignee(db, project, payload.assignee_id)
    number = db.scalar(update(Project).where(Project.id == project_id).values(next_number=Project.next_number + 1).returning(Project.next_number))
    item = WorkItem(project_id=project_id, number=number, author_id=user.id, assignee=assignee, **payload.model_dump())
    db.add(item)
    db.flush()
    confirm_attachments(db, item.description, item, user)
    db.add(Activity(item_id=item.id, author_id=user.id, message="created this work item"))
    db.commit()
    return item_json(item, project)


@app.get(api + "/items/{item_id}", tags=["Work items"])
def get_item(item_id: str, user: User = Depends(organization_user), db: Session = Depends(get_db)):
    item, project = item_access(db, item_id, user)
    return item_json(item, project)


@app.get(api + "/projects/by-slug/{project_slug}/items/{number}", tags=["Work items"])
def get_item_by_number(project_slug: str, number: int, user: User = Depends(organization_user), db: Session = Depends(get_db)):
    project = db.scalar(select(Project).where(Project.key == project_slug))
    if not project:
        project = db.scalar(select(Project).where(Project.slug == project_slug))
    if not project:
        raise HTTPException(404, "Work item not found")
    try:
        project_access(db, project.id, user)
    except HTTPException as exc:
        if exc.status_code == 404:
            raise HTTPException(404, "Work item not found") from exc
        raise
    item = db.scalar(select(WorkItem).where(WorkItem.project_id == project.id, WorkItem.number == number))
    if not item:
        raise HTTPException(404, "Work item not found")
    return item_json(item, project)


@app.put(api + "/items/{item_id}", dependencies=[Depends(csrf)], tags=["Work items"])
def edit_item(item_id: str, payload: ItemCreate, user: User = Depends(organization_user), db: Session = Depends(get_db)):
    return update_item(item_id, payload.model_dump(), user, db)


@app.patch(api + "/items/{item_id}", dependencies=[Depends(csrf)], tags=["Work items"])
def patch_item(item_id: str, payload: ItemUpdate, user: User = Depends(organization_user), db: Session = Depends(get_db)):
    return update_item(item_id, payload.model_dump(exclude_unset=True), user, db)


def metadata_change(field, previous, current):
    empty = {"assignee": "Unassigned", "labels": "No labels"}.get(field, "Not set")

    def display(value):
        if not value:
            return empty
        return json.dumps(value if isinstance(value, list) else str(value), ensure_ascii=False)

    before = f" from {display(previous)}" if previous else ""
    return f"{field}{before} to {display(current)}"


def update_item(item_id, values, user, db):
    item, project = item_access(db, item_id, user, True)
    if "labels" in values:
        lock_catalog(db)
        validate_labels(db, project.id, values["labels"])
    item = db.scalar(select(WorkItem).where(WorkItem.id == item_id).with_for_update()
                     .execution_options(populate_existing=True))
    if "description" in values:
        confirm_attachments(db, values["description"], item, user)
    changed = []
    for key, value in values.items():
        if getattr(item, key) != value:
            if key == "assignee_id":
                previous = item.assignee.name if item.assignee else None
                item.assignee = resolve_assignee(db, project, value)
                changed.append(metadata_change("assignee", previous, item.assignee.name if item.assignee else None))
            else:
                previous = getattr(item, key)
                setattr(item, key, value)
                field = key.replace("_", " ")
                changed.append(metadata_change(field, previous, value)
                               if key in {"status", "type", "priority", "due_date", "labels"} else field)
    if changed:
        item.updated_at = utcnow()
        db.add(Activity(item_id=item.id, author_id=user.id, message="updated " + ", ".join(changed)))
    db.commit()
    return item_json(item, project)


def change_checklist(db: Session, user: User, item: WorkItem, task_index: int,
                     payload: ChecklistUpdate, comment: Comment | None = None):
    text = comment.body if comment else item.description
    if content_version(text) != payload.version:
        raise HTTPException(409, "This content has changed. Refresh and try again.")
    try:
        updated, label, changed = set_checklist_item(text, task_index, payload.checked)
    except IndexError:
        raise HTTPException(404, "Checklist item not found")
    if changed:
        if comment:
            comment.body = updated
        else:
            item.description = updated
        item.updated_at = utcnow()
        source = "a comment" if comment else "the description"
        action = "checked" if payload.checked else "unchecked"
        db.add(Activity(item_id=item.id, author_id=user.id,
                        message=f'{action} checklist item #{task_index + 1} "{label}" in {source}'))
        db.commit()
    return {"text": updated, "version": content_version(updated), "changed": changed}


@app.patch(api + "/items/{item_id}/checklist/{task_index}", dependencies=[Depends(csrf)], tags=["Work items"])
def toggle_description_checklist(item_id: str, task_index: int, payload: ChecklistUpdate,
                                 user: User = Depends(organization_user), db: Session = Depends(get_db)):
    item_access(db, item_id, user, True)
    item = db.scalar(select(WorkItem).where(WorkItem.id == item_id).with_for_update()
                     .execution_options(populate_existing=True))
    return change_checklist(db, user, item, task_index, payload)


@app.patch(api + "/items/{item_id}/comments/{comment_id}/checklist/{task_index}", dependencies=[Depends(csrf)], tags=["Comments"])
def toggle_comment_checklist(item_id: str, comment_id: str, task_index: int, payload: ChecklistUpdate,
                            user: User = Depends(organization_user), db: Session = Depends(get_db)):
    item_access(db, item_id, user, True)
    item = db.scalar(select(WorkItem).where(WorkItem.id == item_id).with_for_update()
                     .execution_options(populate_existing=True))
    comment = db.scalar(select(Comment).where(Comment.id == comment_id, Comment.item_id == item_id)
                        .with_for_update().execution_options(populate_existing=True))
    if not comment:
        raise HTTPException(404, "Comment not found")
    return change_checklist(db, user, item, task_index, payload, comment)


@app.get(api + "/items/{item_id}/discussion", tags=["Comments"])
def discussion(item_id: str, user: User = Depends(organization_user), db: Session = Depends(get_db)):
    item_access(db, item_id, user)
    result = []
    for model, kind in [(Comment, "comment"), (Activity, "activity")]:
        rows = db.execute(select(model, User).join(User, User.id == model.author_id).where(model.item_id == item_id))
        for row, author in rows:
            result.append({"id": row.id, "kind": kind, "author": author.name, "avatar_url": avatar_url(author),
                           "author_is_bot": author.is_bot,
                           "body_version": content_version(row.body) if kind == "comment" else None,
                           "body": row.body if kind == "comment" else row.message, "created_at": row.created_at})
    return sorted(result, key=lambda r: r["created_at"])


@app.post(api + "/items/{item_id}/comments", status_code=201, dependencies=[Depends(csrf)], tags=["Comments"])
def comment(item_id: str, payload: CommentCreate, user: User = Depends(organization_user), db: Session = Depends(get_db)):
    item, _ = item_access(db, item_id, user, True)
    row = Comment(item_id=item_id, author_id=user.id, body=payload.body)
    confirm_attachments(db, payload.body, item, user)
    item.updated_at = utcnow()
    db.add(row)
    db.commit()
    return {"id": row.id}


@app.post(api + "/items/{item_id}/attachments", status_code=201, dependencies=[Depends(csrf)], tags=["Attachments"])
async def upload(item_id: str, file: UploadFile = File(), pending: bool = False,
                 user: User = Depends(organization_user), db: Session = Depends(get_db)):
    item, _ = item_access(db, item_id, user, True)
    return await store_attachment(db, file, user, item.project_id, item_id, pending)


@app.post(api + "/projects/{project_id}/attachments", status_code=201, dependencies=[Depends(csrf)], tags=["Attachments"])
async def upload_draft(project_id: str, file: UploadFile = File(),
                       user: User = Depends(organization_user), db: Session = Depends(get_db)):
    project_access(db, project_id, user, True)
    return await store_attachment(db, file, user, project_id, None, True)


async def store_attachment(db, file, user, project_id, item_id, pending):
    filename = Path((file.filename or "file").replace("\\", "/")).name[:250] or "file"
    attachment = Attachment(id=new_id(), item_id=item_id, project_id=project_id, pending=pending,
                            filename=filename, size=0, uploader_id=user.id)
    settings.attachment_dir.mkdir(parents=True, exist_ok=True)
    path = settings.attachment_dir / attachment.id
    try:
        with path.open("xb") as destination:
            while chunk := await file.read(64 * 1024):
                attachment.size += len(chunk)
                if attachment.size > settings.max_upload_bytes:
                    raise HTTPException(413, "File exceeds the 20 MB limit")
                destination.write(chunk)
        db.add(attachment)
        if not pending:
            db.add(Activity(item_id=item_id, author_id=user.id, message="uploaded " + filename))
        db.commit()
    except BaseException:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    return {"id": attachment.id, "filename": filename, "size": attachment.size,
            "url": f"{api}/attachments/{attachment.id}/download"}


@app.get(api + "/items/{item_id}/attachments", tags=["Attachments"])
def attachments(item_id: str, user: User = Depends(organization_user), db: Session = Depends(get_db)):
    item_access(db, item_id, user)
    return [{"id": a.id, "filename": a.filename, "size": a.size, "url": f"{api}/attachments/{a.id}/download"} for a in db.scalars(select(Attachment).where(Attachment.item_id == item_id, Attachment.pending.is_(False)).order_by(Attachment.created_at))]


@app.get(api + "/attachments/{attachment_id}/download", tags=["Attachments"])
def download(attachment_id: str, user: User = Depends(organization_user), db: Session = Depends(get_db)):
    attachment = db.get(Attachment, attachment_id)
    if not attachment:
        raise HTTPException(404, "Attachment not found")
    if attachment.pending:
        if attachment.uploader_id != user.id:
            raise HTTPException(404, "Attachment not found")
        project_access(db, attachment.project_id, user)
    else:
        item_access(db, attachment.item_id, user)
    path = settings.attachment_dir / attachment.id
    if not path.is_file():
        raise HTTPException(404, "Attachment file not found")
    mime = mimetypes.guess_type(attachment.filename)[0] or "application/octet-stream"
    inline = mime in {"image/png", "image/jpeg", "image/gif", "image/webp"}
    return FileResponse(path, media_type=mime if inline else "application/octet-stream",
                        filename=attachment.filename, content_disposition_type="inline" if inline else "attachment",
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})
