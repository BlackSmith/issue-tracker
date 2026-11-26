"""Authenticated, account-scoped notification settings and ticket participants."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StrictBool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ProjectNotificationPreference, TicketNotificationPreference, User
from app.permissions import project_user_access
from app.profiles import avatar_url
from app.security import browser_user, csrf
from app.notifications import can_subscribe_project, direct_recipients, ticket_participants, ticket_subscribers

router = APIRouter(prefix="/api/v1", tags=["Notifications"])


class PreferenceUpdate(BaseModel):
    enabled: StrictBool | None


def preference_json(db, user, project, item=None):
    preference = db.get(ProjectNotificationPreference, (project.id, user.id))
    project_enabled = preference.enabled if preference else True
    if item is None:
        return {"enabled": project_enabled}
    ticket = db.get(TicketNotificationPreference, (item.id, user.id))
    direct_ids = direct_recipients(db, item)
    ids = ticket_participants(db, item, direct_ids)
    default_enabled = user.id == item.author_id or user.id in direct_ids or (project_enabled and user.id in ids)
    ids.update(ticket_subscribers(db, item))
    participants = db.scalars(select(User).where(User.id.in_(ids), User.active.is_(True),
                                                project_user_access(project.id)).order_by(User.name, User.id))
    from app.permissions import can_view_item
    return {"enabled": ticket.enabled if ticket else None, "project_enabled": project_enabled,
            "default_enabled": default_enabled,
            "participants": [{"id": person.id, "name": person.name, "avatar_url": avatar_url(person)}
                             for person in participants if can_view_item(db, item, person)]}


@router.get("/projects/{project_id}/notifications")
def project_preference(project_id: str, user=Depends(browser_user), db: Session = Depends(get_db)):
    from app.main import project_access
    project = project_access(db, project_id, user)
    if not can_subscribe_project(db, project, user):
        raise HTTPException(403, "Project owner required")
    return preference_json(db, user, project)


@router.put("/projects/{project_id}/notifications", dependencies=[Depends(csrf)])
def set_project_preference(project_id: str, payload: PreferenceUpdate,
                           user=Depends(browser_user), db: Session = Depends(get_db)):
    from app.main import project_access
    project = project_access(db, project_id, user)
    if not can_subscribe_project(db, project, user):
        raise HTTPException(403, "Project owner required")
    row = db.get(ProjectNotificationPreference, (project.id, user.id))
    if row is None:
        row = ProjectNotificationPreference(project_id=project.id, user_id=user.id)
        db.add(row)
    row.enabled = payload.enabled if payload.enabled is not None else True
    db.commit()
    return preference_json(db, user, project)


@router.get("/items/{item_id}/notifications")
def ticket_preference(item_id: str, user=Depends(browser_user), db: Session = Depends(get_db)):
    from app.main import item_access
    item, project = item_access(db, item_id, user)
    return preference_json(db, user, project, item)


@router.put("/items/{item_id}/notifications", dependencies=[Depends(csrf)])
def set_ticket_preference(item_id: str, payload: PreferenceUpdate,
                          user=Depends(browser_user), db: Session = Depends(get_db)):
    from app.main import item_access
    item, project = item_access(db, item_id, user)
    row = db.get(TicketNotificationPreference, (item.id, user.id))
    if payload.enabled is None:
        if row:
            db.delete(row)
    elif row:
        row.enabled = payload.enabled
    else:
        db.add(TicketNotificationPreference(item_id=item.id, user_id=user.id, enabled=payload.enabled))
    db.commit()
    return preference_json(db, user, project, item)
